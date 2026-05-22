"""
Run with:
    python manage.py shell < inventory/seed.py
"""

from django.utils import timezone
from datetime import timedelta
from inventory.models import (
    Warehouse, Item, Inventory, AllocationRule, AllocationStrategy
)
from inventory.services import ReservationService

print("Seeding database...")

# ── Warehouses ────────────────────────────────────────────────
wh_main   = Warehouse.objects.create(code='WH-MAIN',  name='Main Warehouse',       location='Mumbai, India')
wh_north  = Warehouse.objects.create(code='WH-NORTH', name='North Regional Hub',   location='Delhi, India')
wh_south  = Warehouse.objects.create(code='WH-SOUTH', name='South Regional Hub',   location='Chennai, India')

print(f"  Created {Warehouse.objects.count()} warehouses")

# ── Items ─────────────────────────────────────────────────────
steel_rod   = Item.objects.create(sku='STL-ROD-001',  name='Steel Rod 12mm',         category='Raw Material',  unit_of_measure='kg')
copper_wire = Item.objects.create(sku='CPR-WIR-002',  name='Copper Wire 2.5mm',      category='Raw Material',  unit_of_measure='meters')
bearing     = Item.objects.create(sku='BRG-6204-003', name='Ball Bearing 6204',      category='Component',     unit_of_measure='units')
motor       = Item.objects.create(sku='MTR-AC-004',   name='AC Motor 1HP',           category='Component',     unit_of_measure='units')
paint       = Item.objects.create(sku='PNT-RED-005',  name='Industrial Red Paint',   category='Consumable',    unit_of_measure='liters')

print(f"  Created {Item.objects.count()} items")

# ── Inventory (receive stock via service) ─────────────────────
ReservationService.receive_stock(steel_rod,   wh_main,  quantity=500,  performed_by='seed', notes='Opening stock')
ReservationService.receive_stock(copper_wire, wh_main,  quantity=1000, performed_by='seed', notes='Opening stock')
ReservationService.receive_stock(bearing,     wh_main,  quantity=200,  performed_by='seed', notes='Opening stock')
ReservationService.receive_stock(bearing,     wh_north, quantity=80,   performed_by='seed', notes='Opening stock')
ReservationService.receive_stock(motor,       wh_main,  quantity=50,   performed_by='seed', notes='Opening stock')
ReservationService.receive_stock(paint,       wh_main,  quantity=300,  performed_by='seed', notes='Opening stock')
ReservationService.receive_stock(paint,       wh_south, quantity=120,  performed_by='seed', notes='Opening stock')

print(f"  Created {Inventory.objects.count()} inventory records")

# ── Reservations ──────────────────────────────────────────────
# Sales order — VIP customer, urgent
r1 = ReservationService.create_reservation(
    item=bearing, warehouse=wh_main, reserved_qty=30,
    source_type='SALES_ORDER',  source_id='SO-2025-001',
    customer_priority=4,
    delivery_deadline=timezone.now() + timedelta(hours=20),
    order_value=85000,
    created_by='seed',
    notes='VIP customer — urgent delivery'
)

# Sales order — regular customer
r2 = ReservationService.create_reservation(
    item=bearing, warehouse=wh_main, reserved_qty=20,
    source_type='SALES_ORDER',  source_id='SO-2025-002',
    customer_priority=2,
    delivery_deadline=timezone.now() + timedelta(days=5),
    order_value=12000,
    created_by='seed',
)

# Manufacturing work order — production critical
r3 = ReservationService.create_reservation(
    item=steel_rod, warehouse=wh_main, reserved_qty=150,
    source_type='WORK_ORDER',   source_id='WO-2025-010',
    customer_priority=3,
    delivery_deadline=timezone.now() + timedelta(days=2),
    order_value=45000,
    is_manufacturing=True,
    created_by='seed',
    notes='Production line — cannot be delayed'
)

# Internal transfer
r4 = ReservationService.create_reservation(
    item=paint, warehouse=wh_main, reserved_qty=50,
    source_type='TRANSFER',     source_id='TRF-2025-003',
    customer_priority=1,
    delivery_deadline=timezone.now() + timedelta(days=7),
    order_value=5000,
    created_by='seed',
)

# Confirm the VIP reservation
ReservationService.confirm_reservation(r1, confirmed_by='seed')

print(f"  Created 4 reservations")

# ── Allocation Rules ──────────────────────────────────────────
AllocationRule.objects.create(
    name='VIP Priority Rule',
    strategy=AllocationStrategy.PRIORITY,
    priority=10,
    weight_customer_priority=0.50,
    weight_urgency=0.30,
    weight_order_value=0.15,
    weight_aging=0.05,
)

AllocationRule.objects.create(
    name='Manufacturing First Rule',
    strategy=AllocationStrategy.MFG_FIRST,
    priority=9,
    weight_customer_priority=0.20,
    weight_urgency=0.40,
    weight_order_value=0.20,
    weight_aging=0.20,
)

AllocationRule.objects.create(
    name='Default FIFO Rule',
    strategy=AllocationStrategy.FIFO,
    priority=1,
    weight_customer_priority=0.25,
    weight_urgency=0.25,
    weight_order_value=0.25,
    weight_aging=0.25,
)

print(f"  Created {AllocationRule.objects.count()} allocation rules")
print("Done. Database seeded successfully.")