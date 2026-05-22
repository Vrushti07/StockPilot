from rest_framework import serializers
from .models import (
    Warehouse, Item, Inventory,
    Reservation, StockMovementLedger, ReservationEventLog
)


class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = '__all__'
    
class InventorySerializer(serializers.ModelSerializer):
    # Read-only derived field — computed from total - reserved
    quantity_available = serializers.DecimalField(
        max_digits=14, decimal_places=4, read_only=True
    )
    # Nested readable names instead of raw UUIDs
    item_name      = serializers.CharField(source='item.name', read_only=True)
    item_sku       = serializers.CharField(source='item.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'inventory_id',
            'item', 'item_name', 'item_sku',
            'warehouse', 'warehouse_name', 'warehouse_code',
            'quantity_total',
            'quantity_reserved',
            'quantity_available',
            'reorder_point',
            'version',
            'last_updated',
        ]
        read_only_fields = ['inventory_id', 'version', 'last_updated']

class ReservationSerializer(serializers.ModelSerializer):
    # Computed field — not stored in DB
    is_expired     = serializers.BooleanField(read_only=True)
    item_sku       = serializers.CharField(source='item.sku', read_only=True)
    item_name      = serializers.CharField(source='item.name', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)

    class Meta:
        model = Reservation
        fields = [
            'reservation_id',
            'item', 'item_sku', 'item_name',
            'warehouse', 'warehouse_code',
            'reserved_qty',
            'source_type',
            'source_id',
            'priority_score',
            'status',
            'expires_at',
            'notes',
            'created_by',
            'customer_priority',
            'delivery_deadline',
            'order_value',
            'is_manufacturing',
            'is_expired',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['reservation_id', 'priority_score', 'created_at', 'updated_at']

    def validate_reserved_qty(self, value):
        if value <= 0:
            raise serializers.ValidationError("Reserved quantity must be greater than zero.")
        return value

    def validate(self, data):
        """
        Check that available stock can cover the reservation.
        Only runs on creation (not updates).
        """
        if self.instance is None:  # creation only
            item      = data.get('item')
            warehouse = data.get('warehouse')
            qty       = data.get('reserved_qty')
            try:
                inventory = Inventory.objects.get(item=item, warehouse=warehouse)
                if qty > inventory.quantity_available:
                    raise serializers.ValidationError(
                        f"Insufficient stock. Available: {inventory.quantity_available}, Requested: {qty}"
                    )
            except Inventory.DoesNotExist:
                raise serializers.ValidationError(
                    "No inventory record found for this item and warehouse."
                )
        return data


class StockMovementLedgerSerializer(serializers.ModelSerializer):
    item_sku       = serializers.CharField(source='item.sku', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)

    class Meta:
        model = StockMovementLedger
        fields = [
            'movement_id',
            'item', 'item_sku',
            'warehouse', 'warehouse_code',
            'movement_type',
            'quantity',
            'reference_type',
            'reference_id',
            'performed_by',
            'notes',
            'timestamp',
        ]
        # Ledger is append-only — all fields read-only after creation
        read_only_fields = ['movement_id', 'timestamp']


class ReservationEventLogSerializer(serializers.ModelSerializer):
    item_sku       = serializers.CharField(source='item.sku', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)

    class Meta:
        model = ReservationEventLog
        fields = [
            'event_id',
            'reservation',
            'event_type',
            'item', 'item_sku',
            'warehouse', 'warehouse_code',
            'triggered_by',
            'metadata',
            'timestamp',
        ]
        read_only_fields = ['event_id', 'timestamp']
        