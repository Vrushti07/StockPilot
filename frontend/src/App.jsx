import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard   from './pages/Dashboard'
import Inventory   from './pages/Inventory'
import Reservations from './pages/Reservations'
import Ledger      from './pages/Ledger'
import Allocation  from './pages/Allocation'    // ← add this
import './App.css'

export default function App() {
  return (
    <div className="app">
      <nav className="sidebar">
        <div className="logo">
          <span className="logo-icon">⬡</span>
          <span className="logo-text">StockPilot</span>
        </div>
        <NavLink to="/"             end>Dashboard</NavLink>
        <NavLink to="/inventory"       >Inventory</NavLink>
        <NavLink to="/reservations"    >Reservations</NavLink>
        <NavLink to="/allocation"      >Allocation</NavLink>    {/* ← add this */}
        <NavLink to="/ledger"          >Ledger</NavLink>
      </nav>
      <main className="content">
        <Routes>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/inventory"    element={<Inventory />} />
          <Route path="/reservations" element={<Reservations />} />
          <Route path="/allocation"   element={<Allocation />} />    {/* ← add this */}
          <Route path="/ledger"       element={<Ledger />} />
        </Routes>
      </main>
    </div>
  )
}   