from django.db import models

# Create your models here.
import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


#Choices Option
class ReservationStatus(models.TextChoices):
    PENDING   = 'PENDING',   'Pending'
    CONFIRMED = 'CONFIRMED', 'Confirmed'
    ALLOCATED = 'ALLOCATED', 'Allocated'
    RELEASED  = 'RELEASED',  'Released'
    EXPIRED   = 'EXPIRED',   'Expired'
    CANCELLED = 'CANCELLED', 'Cancelled'


class SourceType(models.TextChoices):
    SALES_ORDER      = 'SALES_ORDER',      'Sales Order'
    WORK_ORDER       = 'WORK_ORDER',       'Work Order'
    PRODUCTION_ORDER = 'PRODUCTION_ORDER', 'Production Order'
    TRANSFER         = 'TRANSFER',         'Internal Transfer'
    SERVICE_REQUEST  = 'SERVICE_REQUEST',  'Service Request'
    MANUAL           = 'MANUAL',           'Manual'


class AllocationStrategy(models.TextChoices):
    FIFO         = 'FIFO',         'First In First Out'
    PRIORITY     = 'PRIORITY',     'Priority-Based'
    DEADLINE     = 'DEADLINE',     'Deadline-First'
    PROPORTIONAL = 'PROPORTIONAL', 'Proportional Split'
    MFG_FIRST    = 'MFG_FIRST',    'Manufacturing First'


class EventType(models.TextChoices):
    RESERVATION_CREATED   = 'RESERVATION_CREATED',   'Reservation Created'
    RESERVATION_CONFIRMED = 'RESERVATION_CONFIRMED', 'Reservation Confirmed'
    RESERVATION_RELEASED  = 'RESERVATION_RELEASED',  'Reservation Released'
    RESERVATION_EXPIRED   = 'RESERVATION_EXPIRED',   'Reservation Expired'
    RESERVATION_CANCELLED = 'RESERVATION_CANCELLED', 'Reservation Cancelled'
    ALLOCATION_TRIGGERED  = 'ALLOCATION_TRIGGERED',  'Allocation Triggered'
    STOCK_RECEIVED        = 'STOCK_RECEIVED',         'Stock Received'
    ORDER_CANCELLED       = 'ORDER_CANCELLED',        'Order Cancelled'
    CONFLICT_DETECTED     = 'CONFLICT_DETECTED',      'Conflict Detected'


class MovementType(models.TextChoices):
    RECEIPT   = 'RECEIPT',   'Stock Receipt'
    ISSUE     = 'ISSUE',     'Stock Issue'
    RESERVE   = 'RESERVE',   'Reserve'
    UNRESERVE = 'UNRESERVE', 'Unreserve'
    ALLOCATE  = 'ALLOCATE',  'Allocate'
    ADJUST    = 'ADJUST',    'Manual Adjustment'
    RETURN    = 'RETURN',    'Return'
    
    
    
#Model 1 Warehouse
class Warehouse(models.Model):
    warehouse_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=200)
    code         = models.CharField(max_length=50, unique=True)
    location     = models.CharField(max_length=300, blank=True)
    is_active    = models.BooleanField(default=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'warehouse'
        ordering = ['name']

    def __str__(self):
        return f"{self.code} — {self.name}"


#Model 2 items
class Item(models.Model):
    item_id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sku             = models.CharField(max_length=100, unique=True)
    name            = models.CharField(max_length=300)
    description     = models.TextField(blank=True)
    unit_of_measure = models.CharField(max_length=50, default='units')
    category        = models.CharField(max_length=100, blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'item'
        ordering = ['sku']

    def __str__(self):
        return f"{self.sku} — {self.name}"
  
    
#Model 3 Inventory
class Inventory(models.Model):
    """
    Tracks physical stock per item per warehouse.
    quantity_available is always derived: total - reserved.
    version field enables optimistic locking against race conditions.
    """
    inventory_id      = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item              = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='inventories')
    warehouse         = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='inventories')
    quantity_total    = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    quantity_reserved = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    reorder_point     = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    version           = models.PositiveIntegerField(default=1)
    last_updated      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory'
        unique_together = [('item', 'warehouse')]

    @property
    def quantity_available(self):
        return self.quantity_total - self.quantity_reserved

    def clean(self):
        if self.quantity_reserved > self.quantity_total:
            raise ValidationError("Reserved quantity cannot exceed total quantity.")
        if self.quantity_total < 0:
            raise ValidationError("Total quantity cannot be negative.")

    def __str__(self):
        return (
            f"{self.item.sku} @ {self.warehouse.code} | "
            f"Total:{self.quantity_total} Reserved:{self.quantity_reserved} "
            f"Available:{self.quantity_available}"
        )


#Model 4 Reservation
class Reservation(models.Model):
    """
    A soft lock on inventory.
    Lifecycle: PENDING → CONFIRMED → ALLOCATED
                       → RELEASED / EXPIRED / CANCELLED
    """
    reservation_id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item              = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='reservations')
    warehouse         = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='reservations')
    reserved_qty      = models.DecimalField(max_digits=14, decimal_places=4)
    source_type       = models.CharField(max_length=50, choices=SourceType.choices)
    source_id         = models.CharField(max_length=200, help_text="e.g. SO-001, WO-042")
    priority_score    = models.FloatField(default=0.0)
    status            = models.CharField(max_length=20, choices=ReservationStatus.choices, default=ReservationStatus.PENDING)
    expires_at        = models.DateTimeField(null=True, blank=True)
    notes             = models.TextField(blank=True)
    created_by        = models.CharField(max_length=200, default='system')
    created_at        = models.DateTimeField(auto_now_add=True)
    updated_at        = models.DateTimeField(auto_now=True)

    # Raw priority inputs — scored by AllocationEngine
    customer_priority = models.IntegerField(default=1, help_text="1=Low 2=Medium 3=High 4=VIP")
    delivery_deadline = models.DateTimeField(null=True, blank=True)
    order_value       = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    is_manufacturing  = models.BooleanField(default=False)

    class Meta:
        db_table = 'reservation'
        ordering = ['-priority_score', 'created_at']

    @property
    def is_expired(self):
        return bool(self.expires_at and timezone.now() > self.expires_at)

    def __str__(self):
        return f"Reservation {str(self.reservation_id)[:8]} | {self.source_type}:{self.source_id} | {self.status}"
    

#Model 5 Stock Movement Ledger
class StockMovementLedger(models.Model):
    """
    Append-only transaction log.
    NEVER update or delete entries — this is your source of truth.
    Every inventory mutation must produce a ledger entry.
    """
    movement_id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item           = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='movements')
    warehouse      = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='movements')
    movement_type  = models.CharField(max_length=20, choices=MovementType.choices)
    quantity       = models.DecimalField(max_digits=14, decimal_places=4)
    reference_type = models.CharField(max_length=100, blank=True)
    reference_id   = models.CharField(max_length=200, blank=True)
    performed_by   = models.CharField(max_length=200, default='system')
    notes          = models.TextField(blank=True)
    timestamp      = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'stock_movement_ledger'
        ordering = ['-timestamp']

    def save(self, *args, **kwargs):
        if self.pk and StockMovementLedger.objects.filter(pk=self.pk).exists():
            raise ValueError("Ledger entries are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.movement_type}] {self.item.sku} qty={self.quantity} @ {self.timestamp:%Y-%m-%d %H:%M}"
    

#Model 6 Reservation Event Log
class ReservationEventLog(models.Model):
    """
    Event sourcing log for all reservation lifecycle events.
    Powers audit trails and future async event consumers.
    """
    event_id    = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(Reservation, on_delete=models.SET_NULL, null=True, blank=True, related_name='events')
    event_type  = models.CharField(max_length=50, choices=EventType.choices)
    item        = models.ForeignKey(Item, on_delete=models.PROTECT, related_name='events')
    warehouse   = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name='events')
    triggered_by = models.CharField(max_length=200, default='system')
    metadata    = models.JSONField(default=dict, blank=True)
    timestamp   = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'reservation_event_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.event_type}] @ {self.timestamp:%Y-%m-%d %H:%M:%S}"
    
class AllocationRule(models.Model):
    """
    Configurable policy for how stock is distributed when insufficient.
    """
    rule_id   = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name      = models.CharField(max_length=200)
    strategy  = models.CharField(max_length=50, choices=AllocationStrategy.choices)
    is_active = models.BooleanField(default=True)
    priority  = models.IntegerField(default=0, help_text="Higher = evaluated first")

    weight_customer_priority = models.FloatField(default=0.40)
    weight_urgency           = models.FloatField(default=0.30)
    weight_order_value       = models.FloatField(default=0.20)
    weight_aging             = models.FloatField(default=0.10)

    condition  = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'allocation_rule'
        ordering = ['-priority']

    def __str__(self):
        return f"{self.name} ({self.strategy})"