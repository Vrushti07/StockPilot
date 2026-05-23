# StockPilot

Intelligent stock reservation and allocation engine for manufacturing and distribution operations.

Most ERP systems track inventory. StockPilot decides **who gets it** — atomically reserving stock, enforcing lifecycle rules through a state machine, and distributing limited inventory across competing demands using configurable priority-based strategies.

---

## The Problem

| Demand | Quantity |
|--------|----------|
| Sales Order A | 50 units |
| Sales Order B | 40 units |
| Manufacturing Work Order | 60 units |
| **Total Demand** | **150 units** |
| **Available Stock** | **100 units** |

Traditional ERP answers *"how much stock exists?"*
StockPilot answers *"who should get it, how much, and why?"*

---

## Features

- **Atomic Reservations** — row-level locking prevents double-booking under concurrent load
- **Priority Scoring** — weighted score per reservation based on customer tier, urgency, order value, and aging
- **5 Allocation Strategies** — FIFO, Priority-Based, Deadline-First, Manufacturing-First, Proportional Split — switchable via database config, no redeployment needed
- **Reservation State Machine** — enforces legal lifecycle transitions, rejects invalid ones
- **Conflict Detection** — scans for over-reservation, ghost reservations, and stock below reorder point
- **Immutable Ledger** — append-only stock movement history, full reconstruction possible at any point in time
- **Event Audit Trail** — every reservation lifecycle event recorded with full metadata

---

## Tech Stack

- **Backend** — Django, Django REST Framework, SQLite3
- **Frontend** — React 18, Vite, Axios

---

## Setup

### Backend
```bash
cd stock_engine
python -m venv venv && source venv/bin/activate
pip install django djangorestframework django-cors-headers
python manage.py migrate
python manage.py shell < inventory/seed.py
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install && npm run dev
```

---

## Roadmap
- [ ] Auto-expiry background job for stale reservations
- [ ] Warehouse management UI
- [ ] Stock movement trend charts
- [ ] PostgreSQL support for production
- [ ] Role-based access control

---