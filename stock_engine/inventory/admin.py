from django.contrib import admin

# Register your models here.
from .models import (
    Warehouse, Item, Inventory,
    Reservation, StockMovementLedger,
    ReservationEventLog, AllocationRule
)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display  = ['code', 'name', 'location', 'is_active', 'created_at']
    search_fields = ['code', 'name']
    list_filter   = ['is_active']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display  = ['sku', 'name', 'category', 'unit_of_measure', 'is_active']
    search_fields = ['sku', 'name']
    list_filter   = ['category', 'is_active']


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display  = [
        'item', 'warehouse', 'quantity_total',
        'quantity_reserved', 'quantity_available', 'version', 'last_updated'
    ]
    search_fields = ['item__sku', 'item__name', 'warehouse__code']
    readonly_fields = ['quantity_available', 'version', 'last_updated']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display  = [
        'reservation_id', 'item', 'warehouse',
        'reserved_qty', 'source_type', 'source_id',
        'status', 'priority_score', 'created_at'
    ]
    search_fields = ['source_id', 'item__sku']
    list_filter   = ['status', 'source_type', 'customer_priority']
    readonly_fields = ['reservation_id', 'priority_score', 'created_at', 'updated_at']


@admin.register(StockMovementLedger)
class StockMovementLedgerAdmin(admin.ModelAdmin):
    list_display  = [
        'movement_id', 'item', 'warehouse',
        'movement_type', 'quantity', 'performed_by', 'timestamp'
    ]
    search_fields = ['item__sku', 'reference_id']
    list_filter   = ['movement_type']
    readonly_fields = [
    'movement_id', 'item', 'warehouse', 'movement_type',
    'quantity', 'reference_type', 'reference_id',
    'performed_by', 'notes', 'timestamp'
]

    def has_change_permission(self, request, obj=None):
        return False  # Ledger is immutable — no editing in admin either

    def has_delete_permission(self, request, obj=None):
        return False  # Cannot delete ledger entries


@admin.register(ReservationEventLog)
class ReservationEventLogAdmin(admin.ModelAdmin):
    list_display  = ['event_id', 'event_type', 'item', 'warehouse', 'triggered_by', 'timestamp']
    search_fields = ['event_type', 'item__sku']
    list_filter   = ['event_type']
    readonly_fields = ['event_id', 'timestamp']

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AllocationRule)
class AllocationRuleAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'strategy', 'priority', 'is_active',
        'weight_customer_priority', 'weight_urgency',
        'weight_order_value', 'weight_aging'
    ]
    list_filter  = ['strategy', 'is_active']