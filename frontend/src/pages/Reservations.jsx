import { useEffect, useState } from 'react'
import api from '../api'

export default function Reservations() {
  const [reservations, setReservations] = useState([])
  const [items, setItems]               = useState([])
  const [warehouses, setWarehouses]     = useState([])
  const [loading, setLoading]           = useState(true)
  const [msg, setMsg]                   = useState('')

  const [form, setForm] = useState({
    item: '', warehouse: '', reserved_qty: '',
    source_type: 'SALES_ORDER', source_id: '',
    customer_priority: 1, order_value: 0,
    is_manufacturing: false, notes: '',
  })

  const load = () => {
    Promise.all([
      api.get('/reservations/'),
      api.get('/items/'),
      api.get('/warehouses/'),
    ]).then(([r, it, wh]) => {
      setReservations(r.data)
      setItems(it.data)
      setWarehouses(wh.data)
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [])

  const handleSubmit = () => {
    api.post('/reservations/', form)
      .then(() => { setMsg('Reservation created.'); load() })
      .catch(e  => setMsg(e.response?.data?.error || 'Error'))
  }

  const handleConfirm = (id) => {
    api.post(`/reservations/${id}/confirm/`)
      .then(() => load())
      .catch(e => alert(e.response?.data?.error))
  }

  const handleRelease = (id) => {
    api.post(`/reservations/${id}/release/`)
      .then(() => load())
      .catch(e => alert(e.response?.data?.error))
  }

  return (
    <div>
      <div className="page-header">
        <h1>Reservations</h1>
        <p>Create and manage stock reservations</p>
      </div>

      <div className="form-card">
        <h2>New Reservation</h2>
        {msg && <div style={{ color: 'var(--accent)', marginBottom: 12 }}>{msg}</div>}
        <div className="form-grid">
          <div className="form-group">
            <label>Item</label>
            <select value={form.item} onChange={e => setForm({...form, item: e.target.value})}>
              <option value="">Select item</option>
              {items.map(i => <option key={i.item_id} value={i.item_id}>{i.sku} — {i.name}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Warehouse</label>
            <select value={form.warehouse} onChange={e => setForm({...form, warehouse: e.target.value})}>
              <option value="">Select warehouse</option>
              {warehouses.map(w => <option key={w.warehouse_id} value={w.warehouse_id}>{w.code}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Quantity</label>
            <input type="number" value={form.reserved_qty} onChange={e => setForm({...form, reserved_qty: e.target.value})} />
          </div>
          <div className="form-group">
            <label>Source Type</label>
            <select value={form.source_type} onChange={e => setForm({...form, source_type: e.target.value})}>
              <option value="SALES_ORDER">Sales Order</option>
              <option value="WORK_ORDER">Work Order</option>
              <option value="PRODUCTION_ORDER">Production Order</option>
              <option value="TRANSFER">Transfer</option>
              <option value="MANUAL">Manual</option>
            </select>
          </div>
          <div className="form-group">
            <label>Source ID</label>
            <input value={form.source_id} onChange={e => setForm({...form, source_id: e.target.value})} placeholder="e.g. SO-2025-005" />
          </div>
          <div className="form-group">
            <label>Customer Priority</label>
            <select value={form.customer_priority} onChange={e => setForm({...form, customer_priority: parseInt(e.target.value)})}>
              <option value={1}>1 — Low</option>
              <option value={2}>2 — Medium</option>
              <option value={3}>3 — High</option>
              <option value={4}>4 — VIP</option>
            </select>
          </div>
          <div className="form-group">
            <label>Order Value (₹)</label>
            <input type="number" value={form.order_value} onChange={e => setForm({...form, order_value: e.target.value})} />
          </div>
          <div className="form-group">
            <label>Notes</label>
            <input value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} />
          </div>
        </div>
        <button className="btn btn-primary mt16" onClick={handleSubmit}>Create Reservation</button>
      </div>

      <div className="table-wrap">
        <h2>All Reservations</h2>
        {loading ? <div className="loading">Loading...</div> : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Item</th>
                <th>Warehouse</th>
                <th>Qty</th>
                <th>Source</th>
                <th>Priority Score</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {reservations.map(r => (
                <tr key={r.reservation_id}>
                  <td className="mono">{r.reservation_id.slice(0,8)}</td>
                  <td>{r.item_sku}</td>
                  <td>{r.warehouse_code}</td>
                  <td className="mono">{r.reserved_qty}</td>
                  <td className="mono">{r.source_type}:{r.source_id}</td>
                  <td className="mono">{r.priority_score}</td>
                  <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                  <td style={{ display: 'flex', gap: 6 }}>
                    {r.status === 'PENDING' && (
                      <button className="btn btn-success" style={{padding:'4px 10px',fontSize:11}} onClick={() => handleConfirm(r.reservation_id)}>Confirm</button>
                    )}
                    {(r.status === 'PENDING' || r.status === 'CONFIRMED') && (
                      <button className="btn btn-danger" style={{padding:'4px 10px',fontSize:11}} onClick={() => handleRelease(r.reservation_id)}>Release</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}