import { useEffect, useState } from 'react'
import api from '../api'

export default function Dashboard() {
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/dashboard/').then(r => {
      setData(r.data)
      setLoading(false)
    })
  }, [])

  if (loading) return <div className="loading">Loading dashboard...</div>

  const inv   = data.inventory
  const available = (parseFloat(inv.total_stock) - parseFloat(inv.total_reserved)).toFixed(0)
  const byStatus  = Object.fromEntries(data.reservations_by_status.map(r => [r.status, r.count]))

  return (
    <div>
      <div className="page-header">
        <h1>Dashboard</h1>
        <p>Real-time inventory & reservation overview</p>
      </div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="label">Total Stock</div>
          <div className="value blue">{parseFloat(inv.total_stock).toFixed(0)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Available</div>
          <div className="value green">{available}</div>
        </div>
        <div className="stat-card">
          <div className="label">Reserved</div>
          <div className="value yellow">{parseFloat(inv.total_reserved).toFixed(0)}</div>
        </div>
        <div className="stat-card">
          <div className="label">Pending</div>
          <div className="value yellow">{byStatus['PENDING'] || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Confirmed</div>
          <div className="value green">{byStatus['CONFIRMED'] || 0}</div>
        </div>
        <div className="stat-card">
          <div className="label">Released</div>
          <div className="value">{byStatus['RELEASED'] || 0}</div>
        </div>
      </div>

      <div className="table-wrap">
        <h2>Recent Events</h2>
        <table>
          <thead>
            <tr>
              <th>Event</th>
              <th>Item</th>
              <th>Warehouse</th>
              <th>Triggered By</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {data.recent_events.map(e => (
              <tr key={e.event_id}>
                <td><span className="mono">{e.event_type}</span></td>
                <td>{e.item_sku}</td>
                <td>{e.warehouse_code}</td>
                <td>{e.triggered_by}</td>
                <td className="mono">{new Date(e.timestamp).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}