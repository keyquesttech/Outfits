import { createContext, useContext } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ConfirmHost, Icon, Spinner, ToastHost } from './components/ui.jsx'
import { useAsync } from './hooks.js'
import { api } from './api.js'

import Today from './pages/Today.jsx'
import Wardrobe from './pages/Wardrobe.jsx'
import ItemDetail from './pages/ItemDetail.jsx'
import Outfits from './pages/Outfits.jsx'
import Laundry from './pages/Laundry.jsx'
import Insights from './pages/Insights.jsx'
import Settings from './pages/Settings.jsx'

const MetaCtx = createContext({})
export const useMeta = () => useContext(MetaCtx)

const NAV = [
  { to: '/', label: 'Today', icon: 'sun', end: true },
  { to: '/wardrobe', label: 'Wardrobe', icon: 'hanger' },
  { to: '/outfits', label: 'Outfits', icon: 'layers' },
  { to: '/laundry', label: 'Laundry', icon: 'drop' },
  { to: '/insights', label: 'Insights', icon: 'chart' },
]

function TopBar() {
  return (
    <header
      className="sticky top-0 z-30 border-b backdrop-blur"
      style={{ background: 'color-mix(in srgb, var(--bg) 88%, transparent)', borderColor: 'var(--border)' }}
    >
      <div className="mx-auto flex w-full max-w-[100rem] items-center gap-3 px-[var(--page-pad)] py-3">
        <NavLink to="/" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg"
                style={{ background: 'var(--accent)', color: '#fff' }}>
            <Icon name="hanger" size={18} />
          </span>
          <span className="text-lg font-bold tracking-tight">Outfits</span>
        </NavLink>

        <nav className="ml-4 hidden items-center gap-1 lg:flex">
          {NAV.map((n) => (
            <NavLink
              key={n.to} to={n.to} end={n.end}
              className={({ isActive }) => `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`}
            >
              <Icon name={n.icon} size={16} /> {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto">
          <NavLink to="/settings" className={({ isActive }) => `btn ${isActive ? 'btn-primary' : 'btn-ghost'}`}
                   aria-label="Settings">
            <Icon name="gear" size={17} />
            <span className="hidden sm:inline">Settings</span>
          </NavLink>
        </div>
      </div>
    </header>
  )
}

function BottomNav() {
  const { pathname } = useLocation()
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t lg:hidden"
      style={{
        background: 'color-mix(in srgb, var(--bg) 94%, transparent)',
        borderColor: 'var(--border)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
        backdropFilter: 'blur(12px)',
      }}
    >
      <div className="flex items-stretch">
        {NAV.map((n) => {
          const active = n.end ? pathname === n.to : pathname.startsWith(n.to)
          return (
            <NavLink
              key={n.to} to={n.to} end={n.end}
              className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[0.65rem] font-semibold"
              style={{ color: active ? 'var(--accent)' : 'var(--muted)' }}
            >
              <Icon name={n.icon} size={20} />
              {n.label}
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}

export default function App() {
  const { data: meta, loading } = useAsync(() => api.meta(), [])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center" style={{ color: 'var(--muted)' }}>
        <Spinner size={26} />
      </div>
    )
  }

  return (
    <MetaCtx.Provider value={meta || {}}>
      <ToastHost>
        <ConfirmHost>
        <TopBar />
        <main className="safe-bottom mx-auto w-full max-w-[100rem] px-[var(--page-pad)] py-5 lg:pb-10">
          <Routes>
            <Route path="/" element={<Today />} />
            <Route path="/wardrobe" element={<Wardrobe />} />
            <Route path="/wardrobe/:id" element={<ItemDetail />} />
            <Route path="/outfits" element={<Outfits />} />
            <Route path="/laundry" element={<Laundry />} />
            <Route path="/insights" element={<Insights />} />
            <Route path="/settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
        <BottomNav />
        </ConfirmHost>
      </ToastHost>
    </MetaCtx.Provider>
  )
}
