import { useEffect, useState } from 'react'
import api from '../api'

export default function Allocation() {
  const [items, setItems]         = useState([])
  const [warehouses, setWarehouses] = useState([])
  const [selectedItem, setSelectedItem]           = useState('')
  const [selectedWarehouse, setSelectedWarehouse] = useState('')
  const [plan, setPlan]           = useState(null)
  const [conflicts, setConflicts] = useState(null)
  const [loading, setLoading]     = useState(false)
  const [error, setError]         = useState('')

  useEffect(() => {
    Promise.all([
      api.get('/items/'),
      api.get('/warehouses/'),
    ]).then(([i, w]) => {
      setItems(i.data)
      setWarehouses(w.data)
    })
  }, [])

  const runAnalysis = () => {
    if (!selectedItem || !selectedWarehouse) {
      setError('Please select both an item and a warehouse.')
      return
    }
    setError('')
    setLoading(true)
    setPlan(null)
    setConflicts(null)

    Promise.all([
      api.get(`/allocate/?item=${selectedItem}&warehouse=${selectedWarehouse}`),
      api.get(`/conflicts/?item=${selectedItem}&warehouse=${selectedWarehouse}`),
    ]).then(([planRes, conflictRes]) => {
      setPlan(planRes.data)
      setConflicts(conflictRes.data)
      setLoading(false)
    }).catch(e => {
      setError(e.response?.data?.error || 'Something went wrong.')
      setLoading(false)
    })
  }

  const totalRequested = plan?.plan.reduce((s, r) => s + parseFloat(r.requested), 0) || 0
  const totalAllocated = plan?.plan.reduce((s, r) => s + parseFloat(r.allocated), 0) || 0
  const fulfilledCount = plan?.plan.filter(r => r.fulfilled).length || 0
  const shortCount     = plan?.plan.filter(r => !r.fulfilled).length || 0

  return (
    <div>
      <div className="page-header">
        <h1>Allocation Engine</h1>
        <p>Preview how stock will be distributed across competing reservations</p>
      </div>

      {/* ── Selector ── */}
      <div className="form-card">
        <h2>Select Item & Warehouse</h2>
        {error && <div className="error">{error}</div>}
        <div className="form-grid">
          <div className="form-group">
            <label>Item</label>
            <select value={selectedItem} onChange={e => setSelectedItem(e.target.value)}>
              <option value="">Select item</option>
              {items.map(i => (
                <option key={i.item_id} value={i.item_id}>
                  {i.sku} — {i.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Warehouse</label>
            <select value={selectedWarehouse} onChange={e => setSelectedWarehouse(e.target.value)}>
              <option value="">Select warehouse</option>
              {warehouses.map(w => (
                <option key={w.warehouse_id} value={w.warehouse_id}>
                  {w.code} — {w.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button
          className="btn btn-primary mt16"
          onClick={runAnalysis}
          disabled={loading}
        >
          {loading ? 'Analysing...' : 'Run Allocation Analysis'}
        </button>
      </div>

      {/* ── Conflict Alerts ── */}
      {conflicts && (
        <div style={{ marginBottom: 24 }}>
          {conflicts.healthy ? (
            <div style={styles.alertGreen}>
              <span style={styles.alertIcon}>✓</span>
              No conflicts detected — inventory is healthy.
            </div>
          ) : (
            conflicts.conflicts.map((c, i) => (
              <div
                key={i}
                style={c.severity === 'CRITICAL' ? styles.alertRed : styles.alertYellow}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={styles.alertIcon}>
                    {c.severity === 'CRITICAL' ? '✕' : '⚠'}
                  </span>
                  <span style={styles.severityBadge(c.severity)}>{c.severity}</span>
                </div>
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, marginBottom: 4 }}>
                  {c.type}
                </div>
                <div style={{ fontSize: 13 }}>{c.message}</div>
              </div>
            ))
          )}
        </div>
      )}

      {/* ── Allocation Summary Cards ── */}
      {plan && (
        <>
          <div style={{ marginBottom: 8, fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
            STRATEGY: {plan.strategy}
          </div>

          <div className="stat-grid" style={{ marginBottom: 24 }}>
            <div className="stat-card">
              <div className="label">Total Requested</div>
              <div className="value blue">{totalRequested.toFixed(2)}</div>
            </div>
            <div className="stat-card">
              <div className="label">Total Allocated</div>
              <div className="value green">{totalAllocated.toFixed(2)}</div>
            </div>
            <div className="stat-card">
              <div className="label">Shortfall</div>
              <div className="value red">{(totalRequested - totalAllocated).toFixed(2)}</div>
            </div>
            <div className="stat-card">
              <div className="label">Fully Fulfilled</div>
              <div className="value green">{fulfilledCount}</div>
            </div>
            <div className="stat-card">
              <div className="label">Partial / Unmet</div>
              <div className="value yellow">{shortCount}</div>
            </div>
          </div>

          {/* ── Allocation Plan Table ── */}
          <div className="table-wrap">
            <h2>Allocation Plan — {plan.item} @ {plan.warehouse}</h2>
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Reservation</th>
                  <th>Source</th>
                  <th>Priority</th>
                  <th>Score</th>
                  <th>Requested</th>
                  <th>Allocated</th>
                  <th>Shortfall</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {plan.plan.map((entry, index) => (
                  <tr key={entry.reservation_id}>
                    <td className="mono" style={{ color: 'var(--muted)' }}>
                      #{index + 1}
                    </td>
                    <td className="mono" style={{ fontSize: 11 }}>
                      {entry.reservation_id.slice(0, 8)}
                    </td>
                    <td>
                      <div className="mono" style={{ fontSize: 11 }}>{entry.source_type}</div>
                      <div style={{ color: 'var(--muted)', fontSize: 11 }}>{entry.source_id}</div>
                    </td>
                    <td>
                      <PriorityBadge level={entry.customer_priority} />
                      {entry.is_manufacturing && (
                        <span style={styles.mfgTag}>MFG</span>
                      )}
                    </td>
                    <td className="mono" style={{ color: 'var(--accent)' }}>
                      {entry.score}
                    </td>
                    <td className="mono">{entry.requested}</td>
                    <td className="mono" style={{ color: 'var(--green)' }}>
                      {entry.allocated}
                    </td>
                    <td className="mono" style={{
                      color: parseFloat(entry.shortfall) > 0 ? 'var(--red)' : 'var(--muted)'
                    }}>
                      {parseFloat(entry.shortfall) > 0 ? entry.shortfall : '—'}
                    </td>
                    <td>
                      {entry.fulfilled
                        ? <span style={styles.fulfilledBadge}>Fulfilled</span>
                        : <span style={styles.partialBadge}>
                            {parseFloat(entry.allocated) === 0 ? 'Unmet' : 'Partial'}
                          </span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* ── Visual allocation bars ── */}
          <div className="table-wrap" style={{ marginTop: 24 }}>
            <h2>Allocation Visualizer</h2>
            <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>
              {plan.plan.map((entry, index) => {
                const pct = totalRequested > 0
                  ? (parseFloat(entry.allocated) / totalRequested) * 100
                  : 0
                return (
                  <div key={entry.reservation_id}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>
                        #{index + 1} {entry.source_id}
                      </span>
                      <span style={{ fontSize: 12, color: 'var(--muted)' }}>
                        {entry.allocated} / {entry.requested}
                      </span>
                    </div>
                    <div style={styles.barTrack}>
                      {/* Allocated portion */}
                      <div style={{
                        ...styles.barFill,
                        width: `${pct}%`,
                        background: entry.fulfilled
                          ? 'var(--green)'
                          : 'var(--accent)',
                      }} />
                      {/* Shortfall portion */}
                      {!entry.fulfilled && (
                        <div style={{
                          ...styles.barFill,
                          width: `${(parseFloat(entry.shortfall) / totalRequested) * 100}%`,
                          background: 'var(--red)',
                          opacity: 0.3,
                        }} />
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────

function PriorityBadge({ level }) {
  const map = {
    1: { label: 'Low',    color: 'var(--muted)' },
    2: { label: 'Medium', color: 'var(--text)' },
    3: { label: 'High',   color: 'var(--yellow)' },
    4: { label: 'VIP',    color: 'var(--green)' },
  }
  const { label, color } = map[level] || map[1]
  return (
    <span style={{ color, fontFamily: 'var(--font-mono)', fontSize: 11 }}>
      {label}
    </span>
  )
}

// ── Inline styles ─────────────────────────────────────────────

const styles = {
  alertGreen: {
    background: '#0d2a1a',
    border: '1px solid #22c55e44',
    borderRadius: 8,
    padding: '14px 18px',
    color: 'var(--green)',
    fontSize: 13,
    marginBottom: 16,
    display: 'flex',
    alignItems: 'center',
    gap: 10,
  },
  alertRed: {
    background: '#2a0d0d',
    border: '1px solid #ef444444',
    borderRadius: 8,
    padding: '14px 18px',
    marginBottom: 12,
  },
  alertYellow: {
    background: '#2a2008',
    border: '1px solid #eab30844',
    borderRadius: 8,
    padding: '14px 18px',
    marginBottom: 12,
  },
  alertIcon: {
    fontSize: 16,
    marginRight: 8,
  },
  severityBadge: (severity) => ({
    fontSize: 10,
    fontFamily: 'var(--font-mono)',
    padding: '2px 8px',
    borderRadius: 4,
    background: severity === 'CRITICAL' ? '#ef444422' : '#eab30822',
    color: severity === 'CRITICAL' ? 'var(--red)' : 'var(--yellow)',
  }),
  mfgTag: {
    marginLeft: 6,
    fontSize: 10,
    fontFamily: 'var(--font-mono)',
    padding: '1px 5px',
    borderRadius: 3,
    background: '#1d3a6e',
    color: 'var(--accent)',
  },
  fulfilledBadge: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    background: '#0d2a1a',
    color: 'var(--green)',
    fontFamily: 'var(--font-mono)',
  },
  partialBadge: {
    fontSize: 11,
    padding: '2px 8px',
    borderRadius: 4,
    background: '#2a2008',
    color: 'var(--yellow)',
    fontFamily: 'var(--font-mono)',
  },
  barTrack: {
    height: 8,
    background: 'var(--border)',
    borderRadius: 4,
    overflow: 'hidden',
    display: 'flex',
  },
  barFill: {
    height: '100%',
    borderRadius: 4,
    transition: 'width 0.4s ease',
  },
}