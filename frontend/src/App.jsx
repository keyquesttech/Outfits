import { createContext, useContext, useEffect, useMemo } from 'react'
import { NavLink, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { ConfirmHost, Icon, Spinner, ToastHost } from './components/ui.jsx'
import { useAsync } from './hooks.js'
import { api } from './api.js'

import Today from './pages/Today.jsx'
import Wardrobe from './pages/Wardrobe.jsx'
import ItemDetail from './pages/ItemDetail.jsx'
import Outfits from './pages/Outfits.jsx'
import History from './pages/History.jsx'
import Insights from './pages/Insights.jsx'
import Settings from './pages/Settings.jsx'

const MetaCtx = createContext({})
export const useMeta = () => useContext(MetaCtx)

const NAV = [
  { to: '/', label: 'Today', icon: 'sun', end: true },
  { to: '/wardrobe', label: 'Wardrobe', icon: 'hanger' },
  { to: '/outfits', label: 'Outfits', icon: 'layers' },
  { to: '/history', label: 'History', icon: 'history' },
  { to: '/insights', label: 'Insights', icon: 'chart' },
]

function TopBar() {
  return (
    <header className="chrome sticky top-0 z-30 border-b" style={{ borderColor: 'var(--border)' }}>
      <div className="mx-auto flex w-full max-w-[90rem] items-center gap-3 px-[var(--page-pad)]"
           style={{ minHeight: 'var(--header-h)' }}>
        <NavLink to="/" className="flex items-center gap-2.5">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl"
                style={{
                  background: 'linear-gradient(160deg, color-mix(in srgb, var(--accent) 82%, #fff) 0%, var(--accent) 60%)',
                  color: 'var(--accent-ink)',
                  boxShadow: '0 2px 8px color-mix(in srgb, var(--accent) 40%, transparent)',
                }}>
            <Icon name="hanger" size={19} />
          </span>
          <span className="font-display text-[1.35rem] font-semibold leading-none">Outfits</span>
        </NavLink>

        <nav className="ml-3 hidden items-center gap-1 lg:flex xl:ml-6">
          {NAV.map((n) => (
            <NavLink
              key={n.to} to={n.to} end={n.end}
              className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold transition-colors xl:px-3.5"
              style={({ isActive }) => isActive
                ? { background: 'var(--accent-soft)', color: 'var(--accent)' }
                : { color: 'var(--muted)' }}
            >
              <Icon name={n.icon} size={16} /> {n.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto">
          <NavLink
            to="/settings" aria-label="Settings"
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-semibold transition-colors"
            style={({ isActive }) => isActive
              ? { background: 'var(--accent-soft)', color: 'var(--accent)' }
              : { color: 'var(--muted)' }}
          >
            <Icon name="gear" size={18} />
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
      className="chrome fixed inset-x-0 bottom-0 z-40 border-t lg:hidden"
      style={{
        borderColor: 'var(--border)',
        paddingBottom: 'env(safe-area-inset-bottom, 0px)',
      }}
    >
      <div className="mx-auto flex max-w-xl items-stretch">
        {NAV.map((n) => {
          const active = n.end ? pathname === n.to : pathname.startsWith(n.to)
          return (
            <NavLink key={n.to} to={n.to} end={n.end} aria-label={n.label}
                     className="nav-tab" data-active={active}>
              <span className="nav-pill"><Icon name={n.icon} size={19} /></span>
              <span className="max-w-full truncate px-0.5">{n.label}</span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}

export default function App() {
  const { data: meta, loading, reload } = useAsync(() => api.meta(), [])
  const { pathname } = useLocation()

  // Categories are the user's to change, so meta is no longer fixed for the
  // life of the session. Anything that edits them calls this, and every form
  // reading `meta.categories` picks the change up without a page reload.
  const value = useMemo(
    () => ({ ...(meta || {}), reloadMeta: () => reload(true) }),
    [meta, reload],
  )

  // Each page starts at its top. Without this, arriving on a long page keeps
  // the previous page's scroll position.
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center" style={{ color: 'var(--muted)' }}>
        <Spinner size={24} />
      </div>
    )
  }

  return (
    <MetaCtx.Provider value={value}>
      <ToastHost>
        <ConfirmHost>
        <TopBar />
        <main key={pathname} className="safe-bottom page-fade mx-auto w-full max-w-[90rem] px-[var(--page-pad)] py-5 sm:py-7">
          <Routes>
            <Route path="/" element={<Today />} />
            <Route path="/wardrobe" element={<Wardrobe />} />
            <Route path="/wardrobe/:id" element={<ItemDetail />} />
            <Route path="/outfits" element={<Outfits />} />
            <Route path="/history" element={<History />} />
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
