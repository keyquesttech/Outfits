import { createContext, useCallback, useContext, useEffect, useState } from 'react'

/* ---------- icons (inline, so there is no icon package to ship) ---------- */

const paths = {
  hanger: 'M12 3a2.5 2.5 0 0 0-2.5 2.5c0 1 .6 1.7 1.4 2.1L4 12.6c-.9.5-1.4 1.3-1.4 2.2 0 1.4 1.2 2.2 2.6 2.2h13.6c1.4 0 2.6-.8 2.6-2.2 0-.9-.5-1.7-1.4-2.2L13 7.6',
  sparkle: 'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z',
  drop: 'M12 3s6 6.4 6 10.5a6 6 0 0 1-12 0C6 9.4 12 3 12 3Z',
  chart: 'M4 20V10M10 20V4M16 20v-7M22 20H2',
  gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z M19.4 15a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-1.8-.3 1.6 1.6 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1A1.6 1.6 0 0 0 9 19.4a1.6 1.6 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0 .3-1.8 1.6 1.6 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.6 1.6 0 0 0 4.6 9a1.6 1.6 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 1.8.3H9a1.6 1.6 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.6 1.6 0 0 0 1 1.5 1.6 1.6 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0-.3 1.8V9a1.6 1.6 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.6 1.6 0 0 0-1.5 1Z',
  plus: 'M12 5v14M5 12h14',
  close: 'M18 6 6 18M6 6l12 12',
  check: 'M20 6 9 17l-5-5',
  back: 'M19 12H5M12 19l-7-7 7-7',
  camera: 'M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2Z M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16ZM21 21l-4.3-4.3',
  trash: 'M3 6h18M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2m3 0v14a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V6',
  star: 'M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1L12 2Z',
  sun: 'M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10ZM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4',
  cloud: 'M18 10h-1.3A7 7 0 1 0 6 16h12a4 4 0 0 0 0-8Z',
  rain: 'M18 9h-1.3A7 7 0 1 0 6 15h12a3.5 3.5 0 0 0 0-7ZM8 19l-1 2M12 19l-1 2M16 19l-1 2',
  snow: 'M18 9h-1.3A7 7 0 1 0 6 15h12a3.5 3.5 0 0 0 0-7ZM8 19h.01M12 20h.01M16 19h.01',
  storm: 'M18 9h-1.3A7 7 0 1 0 6 15h12a3.5 3.5 0 0 0 0-7ZM13 14l-3 5h4l-2 4',
  fog: 'M4 9h16M3 13h18M5 17h14',
  wind: 'M3 8h11a3 3 0 1 0-3-3M3 16h14a3 3 0 1 1-3 3M3 12h18',
  edit: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z',
  refresh: 'M23 4v6h-6M1 20v-6h6M3.5 9a9 9 0 0 1 14.9-3.4L23 10M1 14l4.6 4.4A9 9 0 0 0 20.5 15',
  calendar: 'M19 4H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2ZM16 2v4M8 2v4M3 10h18',
  layers: 'M12 2 2 7l10 5 10-5-10-5ZM2 17l10 5 10-5M2 12l10 5 10-5',
}

export function Icon({ name, size = 20, className = '', ...rest }) {
  return (
    <svg
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
      className={className} aria-hidden="true" {...rest}
    >
      {(paths[name] || '').split(' M').map((d, i) => (
        <path key={i} d={i === 0 ? d : 'M' + d} />
      ))}
    </svg>
  )
}

export function WeatherIcon({ group, size = 20, className = '' }) {
  const map = { clear: 'sun', cloud: 'cloud', rain: 'rain', snow: 'snow', storm: 'storm', fog: 'fog' }
  return <Icon name={map[group] || 'cloud'} size={size} className={className} />
}

/* ---------- feedback ---------- */

export function Spinner({ size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" className="animate-spin" aria-label="Loading">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" fill="none" opacity=".2" />
      <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" fill="none" strokeLinecap="round" />
    </svg>
  )
}

const ToastCtx = createContext(() => {})
export const useToast = () => useContext(ToastCtx)

export function ToastHost({ children }) {
  const [toasts, setToasts] = useState([])
  const push = useCallback((message, tone = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts((t) => [...t, { id, message, tone }])
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200)
  }, [])
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="fixed inset-x-0 bottom-24 z-50 flex flex-col items-center gap-2 px-4 pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="card fade-up pointer-events-auto max-w-md px-4 py-2.5 text-sm font-medium"
            style={{ borderColor: t.tone === 'error' ? 'var(--bad)' : t.tone === 'success' ? 'var(--good)' : 'var(--border)' }}
          >
            {t.message}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  )
}

export function EmptyState({ icon = 'hanger', title, hint, action }) {
  return (
    <div className="card flex flex-col items-center gap-3 px-6 py-12 text-center">
      <div className="rounded-full p-3" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
        <Icon name={icon} size={26} />
      </div>
      <p className="text-base font-semibold">{title}</p>
      {hint && <p className="max-w-sm text-sm" style={{ color: 'var(--muted)' }}>{hint}</p>}
      {action}
    </div>
  )
}

export function ErrorNote({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="card px-4 py-3 text-sm" style={{ borderColor: 'var(--bad)' }}>
      <p className="font-semibold" style={{ color: 'var(--bad)' }}>{String(error.message || error)}</p>
      {onRetry && <button className="btn mt-2" onClick={onRetry}><Icon name="refresh" size={15} /> Try again</button>}
    </div>
  )
}

/* ---------- layout primitives ---------- */

export function Modal({ open, onClose, title, children, footer, wide = false }) {
  useEffect(() => {
    if (!open) return
    const onKey = (e) => e.key === 'Escape' && onClose?.()
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
    }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
         style={{ background: 'rgb(0 0 0 / 0.5)' }} onClick={onClose}>
      <div
        className={`card fade-up flex max-h-[92vh] w-full flex-col overflow-hidden rounded-b-none sm:rounded-b-2xl ${wide ? 'sm:max-w-3xl' : 'sm:max-w-lg'}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-4 py-3" style={{ borderColor: 'var(--border)' }}>
          <h2 className="text-base font-bold">{title}</h2>
          <button className="btn btn-ghost !p-1.5" onClick={onClose} aria-label="Close">
            <Icon name="close" size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t px-4 py-3" style={{ borderColor: 'var(--border)' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-xs" style={{ color: 'var(--muted)' }}>{hint}</span>}
    </label>
  )
}

export function Section({ title, action, children, className = '' }) {
  return (
    <section className={`space-y-3 ${className}`}>
      {(title || action) && (
        <div className="flex items-center justify-between gap-3">
          {title && <h2 className="text-sm font-bold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function Stat({ label, value, sub, tone }) {
  return (
    <div className="card px-3.5 py-3">
      <p className="text-[0.7rem] font-semibold uppercase tracking-wide" style={{ color: 'var(--muted)' }}>{label}</p>
      <p className="mt-1 text-2xl font-bold tabular-nums" style={tone ? { color: `var(--${tone})` } : undefined}>{value}</p>
      {sub && <p className="text-xs" style={{ color: 'var(--muted)' }}>{sub}</p>}
    </div>
  )
}

export function Chip({ active, children, ...rest }) {
  return <button className={`chip ${active ? 'chip-on' : ''}`} {...rest}>{children}</button>
}

/* ---------- domain bits ---------- */

const STATUS_STYLE = {
  clean: { label: 'Clean', tone: 'good' },
  worn: { label: 'Worn', tone: 'muted' },
  needs_wash: { label: 'Needs wash', tone: 'bad' },
  airing: { label: 'Airing', tone: 'warn' },
  in_wash: { label: 'In the wash', tone: 'accent' },
}

export function StatusPill({ status, size = 'sm' }) {
  const s = STATUS_STYLE[status] || STATUS_STYLE.clean
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full font-semibold ${size === 'sm' ? 'px-2 py-0.5 text-[0.68rem]' : 'px-2.5 py-1 text-xs'}`}
      style={{ background: 'var(--surface-2)', color: `var(--${s.tone})`, border: '1px solid var(--border)' }}
    >
      <span className="h-1.5 w-1.5 rounded-full" style={{ background: `var(--${s.tone})` }} />
      {s.label}
    </span>
  )
}

export function Palette({ palette = [], size = 14, max = 5 }) {
  if (!palette.length) return null
  return (
    <div className="flex items-center gap-1">
      {palette.slice(0, max).map((c, i) => (
        <span
          key={i}
          title={`${c.name} ${c.hex}`}
          className="rounded-full ring-1"
          style={{ background: c.hex, width: size, height: size, '--tw-ring-color': 'var(--border)' }}
        />
      ))}
    </div>
  )
}

export function WarmthBar({ value, max = 10 }) {
  return (
    <div className="flex items-center gap-1.5">
      <div className="h-1.5 flex-1 overflow-hidden rounded-full" style={{ background: 'var(--surface-2)' }}>
        <div className="h-full rounded-full" style={{ width: `${(value / max) * 100}%`, background: 'var(--accent)' }} />
      </div>
      <span className="text-[0.7rem] tabular-nums" style={{ color: 'var(--muted)' }}>{value}</span>
    </div>
  )
}

export const titleCase = (s) =>
  String(s || '').replace(/_/g, ' ').replace(/\b\w/g, (m) => m.toUpperCase())
