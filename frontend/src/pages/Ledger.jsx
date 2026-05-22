import { useEffect, useState } from 'react'
import api from '../api'

export default function Ledger() {
  const [movements, setMovements] = useState([])
  const [loading, setLoading]     = useState(true)

  useEffect(() => {
    api.get('/ledger/').then(r => {
      setMovements(r.data)
      setLoading(false)
    })
  }, [])

  const typeColor = {
    RECEIPT:   'var(--green)',
    RESERVE:   'var(--yellow)',
    UNRESERVE: 'var(--muted)',
    ALLOCATE:  'var(--accent)',
    ISSUE:     'var(--red)',
    ADJUST:    'var(--text)',
    RETURN:    'var(--text)',
  }

  return (
    <div>
      <div className="page-header">
        <h1>Stock Ledger</h1>
        <p>Immutable transaction history — every stock movement ever recorded</p>
      </div>

      <div className="table-wrap">
        <h2>Movement Log</h2>
        {loading ? <div className="loading">Loading...</div> : (
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Item</th>
                <th>Warehouse</th>
                <th>Quantity</th>
                <th>Reference</th>
                <th>Performed By</th>
                <th>Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {movements.map(m => (
                <tr key={m.movement_id}>
                  <td style={{ color: typeColor[m.movement_type], fontFamily: 'var(--font-mono)', fontSize: 12 }}>
                    {m.movement_type}
                  </td>
                  <td>{m.item_sku}</td>
                  <td>{m.warehouse_code}</td>
                  <td className="mono">{m.quantity}</td>
                  <td className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{m.reference_type} {m.reference_id?.slice(0,8)}</td>
                  <td>{m.performed_by}</td>
                  <td className="mono" style={{ fontSize: 11 }}>{new Date(m.timestamp).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}