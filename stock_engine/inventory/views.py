from django.shortcuts import render

# Create your views here.
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import (
    Warehouse, Item, Inventory,
    Reservation, ReservationStatus,
    StockMovementLedger, ReservationEventLog
)
from .serializers import (
    WarehouseSerializer, ItemSerializer, InventorySerializer,
    ReservationSerializer, StockMovementLedgerSerializer,
    ReservationEventLogSerializer
)
from .services import ReservationService, InsufficientStockError, InvalidTransitionError


class WarehouseListCreateView(APIView):

    def get(self, request):
        warehouses = Warehouse.objects.filter(is_active=True)
        serializer = WarehouseSerializer(warehouses, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = WarehouseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class WarehouseDetailView(APIView):

    def get(self, request, pk):
        warehouse = get_object_or_404(Warehouse, pk=pk)
        return Response(WarehouseSerializer(warehouse).data)

    def patch(self, request, pk):
        warehouse = get_object_or_404(Warehouse, pk=pk)
        serializer = WarehouseSerializer(warehouse, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemListCreateView(APIView):

    def get(self, request):
        items = Item.objects.filter(is_active=True)
        serializer = ItemSerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ItemDetailView(APIView):

    def get(self, request, pk):
        item = get_object_or_404(Item, pk=pk)
        return Response(ItemSerializer(item).data)

    def patch(self, request, pk):
        item = get_object_or_404(Item, pk=pk)
        serializer = ItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class InventoryListView(APIView):

    def get(self, request):
        inventory = Inventory.objects.select_related('item', 'warehouse').all()
        # Optional filters via query params
        item_sku  = request.query_params.get('sku')
        warehouse = request.query_params.get('warehouse')
        if item_sku:
            inventory = inventory.filter(item__sku__icontains=item_sku)
        if warehouse:
            inventory = inventory.filter(warehouse__code__icontains=warehouse)
        serializer = InventorySerializer(inventory, many=True)
        return Response(serializer.data)


class InventoryDetailView(APIView):

    def get(self, request, pk):
        inv = get_object_or_404(Inventory, pk=pk)
        return Response(InventorySerializer(inv).data)
    
class StockReceiveView(APIView):
    """
    POST /api/inventory/receive/
    Records new stock arriving at a warehouse.
    """

    def post(self, request):
        item_id      = request.data.get('item')
        warehouse_id = request.data.get('warehouse')
        quantity     = request.data.get('quantity')
        performed_by = request.data.get('performed_by', 'system')
        notes        = request.data.get('notes', '')

        if not all([item_id, warehouse_id, quantity]):
            return Response(
                {'error': 'item, warehouse, and quantity are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item      = get_object_or_404(Item, pk=item_id)
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        try:
            inventory = ReservationService.receive_stock(
                item=item,
                warehouse=warehouse,
                quantity=quantity,
                performed_by=performed_by,
                notes=notes,
            )
            return Response(
                InventorySerializer(inventory).data,
                status=status.HTTP_201_CREATED
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
    
class ReservationListCreateView(APIView):
    # """
    # GET  /api/reservations/         — list all reservations
    # POST /api/reservations/         — create a new reservation
    # """

    def get(self, request):
        reservations = Reservation.objects.select_related('item', 'warehouse').all()

        # Optional filters
        status_filter = request.query_params.get('status')
        source_type   = request.query_params.get('source_type')
        item_sku      = request.query_params.get('sku')

        if status_filter:
            reservations = reservations.filter(status=status_filter)
        if source_type:
            reservations = reservations.filter(source_type=source_type)
        if item_sku:
            reservations = reservations.filter(item__sku__icontains=item_sku)

        serializer = ReservationSerializer(reservations, many=True)
        return Response(serializer.data)

    def post(self, request):
        item_id      = request.data.get('item')
        warehouse_id = request.data.get('warehouse')

        if not all([item_id, warehouse_id]):
            return Response(
                {'error': 'item and warehouse are required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item      = get_object_or_404(Item, pk=item_id)
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        try:
            reservation = ReservationService.create_reservation(
                item=item,
                warehouse=warehouse,
                reserved_qty=request.data.get('reserved_qty'),
                source_type=request.data.get('source_type'),
                source_id=request.data.get('source_id'),
                customer_priority=int(request.data.get('customer_priority', 1)),
                delivery_deadline=request.data.get('delivery_deadline'),
                order_value=request.data.get('order_value', 0),
                is_manufacturing=request.data.get('is_manufacturing', False),
                expires_at=request.data.get('expires_at'),
                notes=request.data.get('notes', ''),
                created_by=request.data.get('created_by', 'system'),
            )
            return Response(
                ReservationSerializer(reservation).data,
                status=status.HTTP_201_CREATED
            )
        except InsufficientStockError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ReservationDetailView(APIView):
    """
    GET   /api/reservations/<id>/           — get reservation detail
    """

    def get(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        return Response(ReservationSerializer(reservation).data)


class ReservationConfirmView(APIView):
    """
    POST /api/reservations/<id>/confirm/
    """

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            reservation = ReservationService.confirm_reservation(
                reservation=reservation,
                confirmed_by=request.data.get('confirmed_by', 'system')
            )
            return Response(ReservationSerializer(reservation).data)
        except InvalidTransitionError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)


class ReservationReleaseView(APIView):
    """
    POST /api/reservations/<id>/release/
    """

    def post(self, request, pk):
        reservation = get_object_or_404(Reservation, pk=pk)
        try:
            reservation = ReservationService.release_reservation(
                reservation=reservation,
                released_by=request.data.get('released_by', 'system')
            )
            return Response(ReservationSerializer(reservation).data)
        except InvalidTransitionError as e:
            return Response({'error': str(e)}, status=status.HTTP_409_CONFLICT)
        
class StockMovementLedgerView(APIView):
    """
    GET /api/ledger/
    Read-only — the ledger is never modified through the API.
    """

    def get(self, request):
        movements = StockMovementLedger.objects.select_related('item', 'warehouse').all()

        item_sku = request.query_params.get('sku')
        m_type   = request.query_params.get('movement_type')

        if item_sku:
            movements = movements.filter(item__sku__icontains=item_sku)
        if m_type:
            movements = movements.filter(movement_type=m_type)

        serializer = StockMovementLedgerSerializer(movements[:100], many=True)
        return Response(serializer.data)


class ReservationEventLogView(APIView):
    """
    GET /api/events/
    Full audit trail of all reservation events.
    """

    def get(self, request):
        events = ReservationEventLog.objects.select_related(
            'item', 'warehouse', 'reservation'
        ).all()

        event_type = request.query_params.get('event_type')
        item_sku   = request.query_params.get('sku')

        if event_type:
            events = events.filter(event_type=event_type)
        if item_sku:
            events = events.filter(item__sku__icontains=item_sku)

        serializer = ReservationEventLogSerializer(events[:100], many=True)
        return Response(serializer.data)
    
class DashboardSummaryView(APIView):
    """
    GET /api/dashboard/
    Single endpoint for frontend dashboard stats.
    """

    def get(self, request):
        from django.db.models import Sum, Count

        inventory_stats = Inventory.objects.aggregate(
            total_items=Count('inventory_id'),
            total_stock=Sum('quantity_total'),
            total_reserved=Sum('quantity_reserved'),
        )

        reservation_stats = Reservation.objects.values('status').annotate(count=Count('reservation_id'))

        recent_events = ReservationEventLog.objects.select_related(
            'item', 'warehouse'
        ).order_by('-timestamp')[:10]

        return Response({
            'inventory': {
                'total_items':    inventory_stats['total_items'] or 0,
                'total_stock':    str(inventory_stats['total_stock'] or 0),
                'total_reserved': str(inventory_stats['total_reserved'] or 0),
            },
            'reservations_by_status': list(reservation_stats),
            'recent_events': ReservationEventLogSerializer(recent_events, many=True).data,
        })

class AllocationPlanView(APIView):
    """
    GET /api/allocate/?item=<id>&warehouse=<id>
    Returns the allocation plan without committing anything.
    Frontend can show this as a preview before executing.
    """

    def get(self, request):
        item_id      = request.query_params.get('item')
        warehouse_id = request.query_params.get('warehouse')

        if not all([item_id, warehouse_id]):
            return Response(
                {'error': 'item and warehouse query params required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item      = get_object_or_404(Item, pk=item_id)
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        from .services import AllocationEngine
        strategy, rule = AllocationEngine.get_active_strategy()
        
        if strategy == 'PROPORTIONAL':
            plan = AllocationEngine.build_proportional_plan(item, warehouse)
        else:
            plan = AllocationEngine.build_allocation_plan(item, warehouse)

        # Serialize plan (can't use ModelSerializer directly on a dict)
        result = []
        for entry in plan:
            r = entry['reservation']
            result.append({
                'reservation_id': str(r.reservation_id),
                'source_type':    r.source_type,
                'source_id':      r.source_id,
                'requested':      str(entry['requested']),
                'allocated':      str(entry['allocated']),
                'fulfilled':      entry['fulfilled'],
                'shortfall':      str(entry['shortfall']),
                'score':          entry.get('score', 0),
                'is_manufacturing': r.is_manufacturing,
                'customer_priority': r.customer_priority,
            })

        return Response({
            'item':      item.sku,
            'warehouse': warehouse.code,
            'strategy':  strategy,
            'plan':      result,
        })


class ConflictDetectionView(APIView):
    """
    GET /api/conflicts/?item=<id>&warehouse=<id>
    Scans for inventory conflict states.
    """

    def get(self, request):
        item_id      = request.query_params.get('item')
        warehouse_id = request.query_params.get('warehouse')

        if not all([item_id, warehouse_id]):
            return Response(
                {'error': 'item and warehouse query params required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        item      = get_object_or_404(Item, pk=item_id)
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        from .services import ConflictDetector
        conflicts = ConflictDetector.detect(item, warehouse)

        return Response({
            'item':      item.sku,
            'warehouse': warehouse.code,
            'conflicts': conflicts,
            'healthy':   len(conflicts) == 0,
        })