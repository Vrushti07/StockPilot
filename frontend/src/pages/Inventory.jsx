import { useEffect, useState } from 'react'
import api from '../api'

export default function Inventory() {
  const [inventory, setInventory] = useState([])
  const [loading, setLoading]     = useState(true)
  const [search, setSearch]       = useState('')

  const load = () => {
    api.get('/inventory/').then(r => {
      setInventory(r.data)
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [])

  const filtered = inventory.filter(i =>
    i.item_sku.toLowerCase().includes(search.toLowerCase()) ||
    i.item_name.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div>
      <div className="page-header">
        <h1>Inventory</h1>
        <p>Current stock levels across all warehouses</p>
      </div>

      <div className="form-card">
        <input
          placeholder="Search by SKU or item name..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--text)', fontSize: 13 }}
        />
      </div>

      <div className="table-wrap">
        <h2>Stock Levels</h2>
        {loading ? <div className="loading">Loading...</div> : (
          <table>
            <thead>
              <tr>
                <th>SKU</th>
                <th>Item</th>
                <th>Warehouse</th>
                <th>Total</th>
                <th>Reserved</th>
                <th>Available</th>
                
              </tr>
            </thead>
            <tbody>
              {filtered.map(i => (
                <tr key={i.inventory_id}>
                  <td className="mono">{i.item_sku}</td>
                  <td>{i.item_name}</td>
                  <td>{i.warehouse_code}</td>
                  <td className="mono">{i.quantity_total}</td>
                  <td className="mono" style={{ color: 'var(--yellow)' }}>{i.quantity_reserved}</td>
                  <td className="mono" style={{ color: parseFloat(i.quantity_available) > 0 ? 'var(--green)' : 'var(--red)' }}>
                    {i.quantity_available}
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