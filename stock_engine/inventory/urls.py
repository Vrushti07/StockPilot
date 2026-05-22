from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/',                              views.DashboardSummaryView.as_view()),

    # Warehouses
    path('warehouses/',                             views.WarehouseListCreateView.as_view()),
    path('warehouses/<str:pk>/',                    views.WarehouseDetailView.as_view()),

    # Items
    path('items/',                                  views.ItemListCreateView.as_view()),
    path('items/<str:pk>/',                         views.ItemDetailView.as_view()),

    # Inventory
    path('inventory/',                              views.InventoryListView.as_view()),
    path('inventory/<str:pk>/',                     views.InventoryDetailView.as_view()),
    path('inventory/receive/',                      views.StockReceiveView.as_view()),

    # Reservations
    path('reservations/',                           views.ReservationListCreateView.as_view()),
    path('reservations/<str:pk>/',                  views.ReservationDetailView.as_view()),
    path('reservations/<str:pk>/confirm/',          views.ReservationConfirmView.as_view()),
    path('reservations/<str:pk>/release/',          views.ReservationReleaseView.as_view()),

    # Ledger & Events (read-only)
    path('ledger/',                                 views.StockMovementLedgerView.as_view()),
    path('events/',                                 views.ReservationEventLogView.as_view()),
    
    path('allocate/',                               views.AllocationPlanView.as_view()),
    path('conflicts/',                              views.ConflictDetectionView.as_view()),
]