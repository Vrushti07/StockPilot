from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import F
from .models import (
    Inventory, Reservation, ReservationStatus,
    StockMovementLedger, ReservationEventLog,
    MovementType, EventType, AllocationStrategy
)


class InsufficientStockError(Exception):
    """Raised when available stock cannot cover the reservation request."""
    pass


class InvalidTransitionError(Exception):
    """Raised when an illegal reservation state transition is attempted."""
    pass


class PriorityScorer:
    """
    Computes a weighted priority score for a reservation request.

    Formula:
        Score = 0.4 * customer_priority
              + 0.3 * urgency
              + 0.2 * order_value_score
              + 0.1 * aging_score

    All inputs normalized to 0-100 range before weighting.
    """

    WEIGHT_CUSTOMER  = 0.40
    WEIGHT_URGENCY   = 0.30
    WEIGHT_ORDER_VAL = 0.20
    WEIGHT_AGING     = 0.10

    @classmethod
    def compute(cls, customer_priority, delivery_deadline, order_value, created_at=None):
        customer_score = cls._score_customer(customer_priority)
        urgency_score  = cls._score_urgency(delivery_deadline)
        value_score    = cls._score_order_value(order_value)
        aging_score    = cls._score_aging(created_at)

        final = (
            cls.WEIGHT_CUSTOMER  * customer_score +
            cls.WEIGHT_URGENCY   * urgency_score  +
            cls.WEIGHT_ORDER_VAL * value_score     +
            cls.WEIGHT_AGING     * aging_score
        )
        return round(final, 4)

    @classmethod
    def _score_customer(cls, priority):
        # 1=Low, 2=Medium, 3=High, 4=VIP → normalize to 0-100
        mapping = {1: 25, 2: 50, 3: 75, 4: 100}
        return mapping.get(priority, 25)

    @classmethod
    def _score_urgency(cls, deadline):
        if not deadline:
            return 0
        now        = timezone.now()
        hours_left = (deadline - now).total_seconds() / 3600
        if hours_left <= 0:
            return 100   # already overdue
        elif hours_left <= 24:
            return 90
        elif hours_left <= 72:
            return 70
        elif hours_left <= 168:
            return 40    # within a week
        else:
            return 10

    @classmethod
    def _score_order_value(cls, value):
        value = float(value or 0)
        if value >= 100000:
            return 100
        elif value >= 50000:
            return 80
        elif value >= 10000:
            return 60
        elif value >= 1000:
            return 40
        else:
            return 20

    @classmethod
    def _score_aging(cls, created_at):
        # Older pending reservations get slightly higher score (fairness)
        if not created_at:
            return 0
        hours_waiting = (timezone.now() - created_at).total_seconds() / 3600
        if hours_waiting >= 48:
            return 100
        elif hours_waiting >= 24:
            return 60
        elif hours_waiting >= 8:
            return 30
        else:
            return 10

class ReservationStateMachine:
    """
    Enforces valid state transitions.
    Any attempt at an illegal transition raises InvalidTransitionError.

    Valid transitions:
        PENDING   → CONFIRMED, CANCELLED, EXPIRED
        CONFIRMED → ALLOCATED, RELEASED, CANCELLED
        ALLOCATED → RELEASED
    """

    TRANSITIONS = {
        ReservationStatus.PENDING: [
            ReservationStatus.CONFIRMED,
            ReservationStatus.CANCELLED,
            ReservationStatus.EXPIRED,
        ],
        ReservationStatus.CONFIRMED: [
            ReservationStatus.ALLOCATED,
            ReservationStatus.RELEASED,
            ReservationStatus.CANCELLED,
        ],
        ReservationStatus.ALLOCATED: [
            ReservationStatus.RELEASED,
        ],
        # Terminal states — no transitions allowed
        ReservationStatus.RELEASED:  [],
        ReservationStatus.EXPIRED:   [],
        ReservationStatus.CANCELLED: [],
    }

    @classmethod
    def transition(cls, reservation, new_status):
        allowed = cls.TRANSITIONS.get(reservation.status, [])
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from '{reservation.status}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )
        reservation.status = new_status
        reservation.save(update_fields=['status', 'updated_at'])
        return reservation

class ReservationService:
    """
    All reservation operations go through here.
    Views never touch Inventory or Reservation models directly.

    Every method that mutates stock:
        1. Opens a transaction
        2. Locks the inventory row (SELECT FOR UPDATE)
        3. Validates business rules
        4. Writes to Inventory
        5. Writes to StockMovementLedger (immutable)
        6. Writes to ReservationEventLog
        7. Commits — or rolls back entirely on any failure
    """

    @staticmethod
    @transaction.atomic
    def create_reservation(
        item, warehouse, reserved_qty,
        source_type, source_id,
        customer_priority=1,
        delivery_deadline=None,
        order_value=0,
        is_manufacturing=False,
        expires_at=None,
        notes='',
        created_by='system',
    ):
        """
        Atomically creates a reservation if stock is available.
        Uses SELECT FOR UPDATE to prevent race conditions.
        """
        # Step 1 — Lock the inventory row so no concurrent request
        #           can read stale available qty
        try:
            inventory = Inventory.objects.select_for_update().get(
                item=item, warehouse=warehouse
            )
        except Inventory.DoesNotExist:
            raise InsufficientStockError(
                f"No inventory record for item '{item.sku}' "
                f"at warehouse '{warehouse.code}'."
            )

        # Step 2 — Business rule: is there enough available stock?
        if inventory.quantity_available < Decimal(str(reserved_qty)):
            raise InsufficientStockError(
                f"Insufficient stock. "
                f"Available: {inventory.quantity_available}, "
                f"Requested: {reserved_qty}"
            )

        # Step 3 — Compute priority score
        priority_score = PriorityScorer.compute(
            customer_priority=customer_priority,
            delivery_deadline=delivery_deadline,
            order_value=order_value,
        )

        # Step 4 — Create the reservation
        reservation = Reservation.objects.create(
            item=item,
            warehouse=warehouse,
            reserved_qty=reserved_qty,
            source_type=source_type,
            source_id=source_id,
            priority_score=priority_score,
            status=ReservationStatus.PENDING,
            expires_at=expires_at,
            notes=notes,
            created_by=created_by,
            customer_priority=customer_priority,
            delivery_deadline=delivery_deadline,
            order_value=order_value,
            is_manufacturing=is_manufacturing,
        )

        # Step 5 — Update inventory reserved quantity atomically
        Inventory.objects.filter(
            inventory_id=inventory.inventory_id
        ).update(
            quantity_reserved=F('quantity_reserved') + Decimal(str(reserved_qty)),
            version=F('version') + 1
        )

        # Step 6 — Write immutable ledger entry
        StockMovementLedger.objects.create(
            item=item,
            warehouse=warehouse,
            movement_type=MovementType.RESERVE,
            quantity=reserved_qty,
            reference_type='Reservation',
            reference_id=str(reservation.reservation_id),
            performed_by=created_by,
            notes=f"Reserved for {source_type}:{source_id}",
        )

        # Step 7 — Log the event
        ReservationEventLog.objects.create(
            reservation=reservation,
            event_type=EventType.RESERVATION_CREATED,
            item=item,
            warehouse=warehouse,
            triggered_by=created_by,
            metadata={
                'reserved_qty': str(reserved_qty),
                'source_type': source_type,
                'source_id': source_id,
                'priority_score': priority_score,
            }
        )

        return reservation

    @staticmethod
    @transaction.atomic
    def release_reservation(reservation, released_by='system'):
        """
        Releases a reservation — frees the stock back to available.
        Enforces state machine rules before releasing.
        """
        # Validate transition is legal
        ReservationStateMachine.transition(reservation, ReservationStatus.RELEASED)

        # Free the reserved quantity back
        Inventory.objects.filter(
            item=reservation.item,
            warehouse=reservation.warehouse
        ).update(
            quantity_reserved=F('quantity_reserved') - reservation.reserved_qty,
            version=F('version') + 1
        )

        # Immutable ledger entry
        StockMovementLedger.objects.create(
            item=reservation.item,
            warehouse=reservation.warehouse,
            movement_type=MovementType.UNRESERVE,
            quantity=reservation.reserved_qty,
            reference_type='Reservation',
            reference_id=str(reservation.reservation_id),
            performed_by=released_by,
            notes=f"Released reservation for {reservation.source_type}:{reservation.source_id}",
        )

        # Event log
        ReservationEventLog.objects.create(
            reservation=reservation,
            event_type=EventType.RESERVATION_RELEASED,
            item=reservation.item,
            warehouse=reservation.warehouse,
            triggered_by=released_by,
            metadata={'released_qty': str(reservation.reserved_qty)}
        )

        return reservation

    @staticmethod
    @transaction.atomic
    def confirm_reservation(reservation, confirmed_by='system'):
        """Moves reservation from PENDING to CONFIRMED."""
        ReservationStateMachine.transition(reservation, ReservationStatus.CONFIRMED)

        ReservationEventLog.objects.create(
            reservation=reservation,
            event_type=EventType.RESERVATION_CONFIRMED,
            item=reservation.item,
            warehouse=reservation.warehouse,
            triggered_by=confirmed_by,
            metadata={'status': ReservationStatus.CONFIRMED}
        )
        return reservation

    @staticmethod
    @transaction.atomic
    def receive_stock(item, warehouse, quantity, performed_by='system', notes=''):
        """
        Records new stock arriving at a warehouse.
        Increases total quantity — available increases automatically.
        """
        inventory, created = Inventory.objects.select_for_update().get_or_create(
            item=item,
            warehouse=warehouse,
            defaults={'quantity_total': 0, 'quantity_reserved': 0}
        )

        Inventory.objects.filter(
            inventory_id=inventory.inventory_id
        ).update(
            quantity_total=F('quantity_total') + Decimal(str(quantity)),
            version=F('version') + 1
        )

        StockMovementLedger.objects.create(
            item=item,
            warehouse=warehouse,
            movement_type=MovementType.RECEIPT,
            quantity=quantity,
            reference_type='StockReceipt',
            performed_by=performed_by,
            notes=notes or f"Stock received: {quantity} units",
        )

        ReservationEventLog.objects.create(
            event_type=EventType.STOCK_RECEIVED,
            item=item,
            warehouse=warehouse,
            triggered_by=performed_by,
            metadata={'quantity_received': str(quantity)}
        )

        return Inventory.objects.get(inventory_id=inventory.inventory_id)
    
class AllocationEngine:
    """
    Decides how to distribute limited stock across competing reservations.

    When available stock < total demand, the engine:
        1. Fetches all PENDING/CONFIRMED reservations for the item
        2. Scores and ranks them
        3. Applies the active allocation strategy
        4. Returns an allocation plan (who gets how much)

    Does NOT mutate any data — returns a plan for the caller to execute.
    This makes it testable and inspectable before committing.
    """

    @staticmethod
    def get_active_strategy():
        """Load the highest priority active rule from DB."""
        from .models import AllocationRule
        rule = AllocationRule.objects.filter(is_active=True).order_by('-priority').first()
        if not rule:
            return AllocationStrategy.FIFO, None
        return rule.strategy, rule

    @staticmethod
    def build_allocation_plan(item, warehouse):
        """
        Core method. Returns a list of dicts:
        [
            {
                'reservation': <Reservation>,
                'requested':   Decimal,
                'allocated':   Decimal,
                'fulfilled':   bool,
            },
            ...
        ]
        """
        from .models import AllocationRule

        # Step 1 — How much stock is actually free right now?
        try:
            inventory = Inventory.objects.get(item=item, warehouse=warehouse)
        except Inventory.DoesNotExist:
            return []

        available_stock = inventory.quantity_available

        # Step 2 — Get all active reservations for this item+warehouse
        reservations = Reservation.objects.filter(
            item=item,
            warehouse=warehouse,
            status__in=[ReservationStatus.PENDING, ReservationStatus.CONFIRMED]
        ).order_by('-priority_score', 'created_at')

        if not reservations.exists():
            return []

        # Step 3 — Determine strategy
        strategy, rule = AllocationEngine.get_active_strategy()

        # Step 4 — Recompute priority scores with fresh data
        scored = []
        for r in reservations:
            score = PriorityScorer.compute(
                customer_priority=r.customer_priority,
                delivery_deadline=r.delivery_deadline,
                order_value=r.order_value,
                created_at=r.created_at,
            )
            scored.append((score, r))

        # Step 5 — Apply strategy to produce ranked list
        ranked = AllocationEngine._apply_strategy(strategy, scored)

        # Step 6 — Distribute stock down the ranked list
        plan = []
        remaining = available_stock

        for score, reservation in ranked:
            requested  = reservation.reserved_qty
            allocated  = min(requested, remaining)
            remaining -= allocated
            plan.append({
                'reservation': reservation,
                'requested':   requested,
                'allocated':   allocated,
                'fulfilled':   allocated >= requested,
                'score':       round(score, 4),
                'shortfall':   requested - allocated,
            })

        return plan

    @staticmethod
    def _apply_strategy(strategy, scored_reservations):
        """
        Returns a ranked list based on the chosen strategy.
        Each strategy answers: who should get stock first?
        """

        if strategy == AllocationStrategy.FIFO:
            # Oldest reservation first — pure fairness
            return sorted(
                scored_reservations,
                key=lambda x: x[1].created_at
            )

        elif strategy == AllocationStrategy.PRIORITY:
            # Highest priority score first
            return sorted(
                scored_reservations,
                key=lambda x: x[0],
                reverse=True
            )

        elif strategy == AllocationStrategy.DEADLINE:
            # Closest deadline first — SLA protection
            def deadline_key(item):
                dl = item[1].delivery_deadline
                if dl is None:
                    return timezone.now() + timezone.timedelta(days=9999)
                return dl
            return sorted(scored_reservations, key=deadline_key)

        elif strategy == AllocationStrategy.MFG_FIRST:
            # Manufacturing orders always go first, then by priority score
            return sorted(
                scored_reservations,
                key=lambda x: (not x[1].is_manufacturing, -x[0])
            )

        elif strategy == AllocationStrategy.PROPORTIONAL:
            # Everyone gets a fair share proportional to their request
            # (handled differently — see below)
            return sorted(
                scored_reservations,
                key=lambda x: x[0],
                reverse=True
            )

        # Default fallback
        return scored_reservations

    @staticmethod
    def build_proportional_plan(item, warehouse):
        """
        Special case for PROPORTIONAL strategy.
        Instead of first-come-first-served, everyone gets
        a share proportional to what they asked for.

        Example:
            Available: 60 units
            SO-001 wants 50  → gets 50/(50+40) * 60 = 33.3
            SO-002 wants 40  → gets 40/(50+40) * 60 = 26.7
        """
        try:
            inventory = Inventory.objects.get(item=item, warehouse=warehouse)
        except Inventory.DoesNotExist:
            return []

        available = inventory.quantity_available

        reservations = Reservation.objects.filter(
            item=item,
            warehouse=warehouse,
            status__in=[ReservationStatus.PENDING, ReservationStatus.CONFIRMED]
        )

        total_demanded = sum(r.reserved_qty for r in reservations)

        if total_demanded == 0:
            return []

        plan = []
        for r in reservations:
            share     = (r.reserved_qty / total_demanded) * available
            share     = round(share, 4)
            plan.append({
                'reservation': r,
                'requested':   r.reserved_qty,
                'allocated':   share,
                'fulfilled':   share >= r.reserved_qty,
                'shortfall':   max(r.reserved_qty - share, 0),
            })

        return plan


class ConflictDetector:
    """
    Scans inventory for problem states and raises alerts.
    Run this periodically or after every major stock event.
    """

    @staticmethod
    def detect(item, warehouse):
        """
        Returns a list of conflict dicts. Empty list = no issues.
        """
        conflicts = []

        try:
            inventory = Inventory.objects.get(item=item, warehouse=warehouse)
        except Inventory.DoesNotExist:
            return conflicts

        # ── Check 1: Over-reservation ──────────────────────────
        if inventory.quantity_reserved > inventory.quantity_total:
            conflicts.append({
                'type':    'OVER_RESERVATION',
                'message': f"Reserved ({inventory.quantity_reserved}) exceeds "
                           f"total stock ({inventory.quantity_total}).",
                'severity': 'CRITICAL',
            })

        # ── Check 2: Stale reservations (expired but not released) ──
        from django.utils import timezone
        stale = Reservation.objects.filter(
            item=item,
            warehouse=warehouse,
            status__in=[ReservationStatus.PENDING, ReservationStatus.CONFIRMED],
            expires_at__lt=timezone.now()
        )
        if stale.exists():
            conflicts.append({
                'type':    'STALE_RESERVATIONS',
                'message': f"{stale.count()} reservation(s) are past expiry "
                           f"but still active.",
                'severity': 'WARNING',
                'count':    stale.count(),
            })

        # ── Check 3: Stock below reorder point ────────────────
        if inventory.quantity_available < inventory.reorder_point:
            conflicts.append({
                'type':    'BELOW_REORDER_POINT',
                'message': f"Available stock ({inventory.quantity_available}) "
                           f"is below reorder point ({inventory.reorder_point}).",
                'severity': 'WARNING',
            })

        # ── Check 4: Zero available but active reservations ───
        if inventory.quantity_available <= 0:
            active_count = Reservation.objects.filter(
                item=item,
                warehouse=warehouse,
                status__in=[ReservationStatus.PENDING, ReservationStatus.CONFIRMED]
            ).count()
            if active_count > 0:
                conflicts.append({
                    'type':    'NO_STOCK_FOR_ACTIVE_RESERVATIONS',
                    'message': f"Zero available stock but {active_count} "
                               f"active reservation(s) exist.",
                    'severity': 'CRITICAL',
                })

        return conflicts