import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import {
  EmptyState, ErrorNote, Icon, PageHeader, Section, Spinner, titleCase, useConfirm,
  useToast,
} from '../components/ui.jsx'

const COMFORT = {
  '-1': { label: 'Too cold', tone: 'accent' },
  0: { label: 'Just right', tone: 'good' },
  1: { label: 'Too hot', tone: 'warn' },
}

/**
 * Dates as a person reads them. "Today" and "Yesterday" beat an ISO string for
 * the two entries you are most likely to be correcting.
 */
function dayLabel(iso) {
  const today = new Date()
  const midnight = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  const worn = new Date(`${iso}T12:00:00`)
  const days = Math.round((midnight(today) - midnight(worn)) / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return 'Yesterday'
  const label = worn.toLocaleDateString(undefined,
    { weekday: 'short', day: 'numeric', month: 'short' })
  return days < 365 ? label : `${label} ${worn.getFullYear()}`
}

function WearCard({ wear, busy, onDeleteWear, onRemoveItem }) {
  const comfort = wear.comfort_rating != null ? COMFORT[String(wear.comfort_rating)] : null
  const [editing, setEditing] = useState(false)
  const working = busy === wear.id

  return (
    <div className="card px-3.5 py-3">
      <div className="flex items-start gap-2">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">
            {wear.outfit_name || `${wear.items.length} item${wear.items.length === 1 ? '' : 's'}`}
            {wear.occasion && (
              <span className="font-normal" style={{ color: 'var(--muted)' }}>
                {' · '}{titleCase(wear.occasion)}
              </span>
            )}
          </p>
          {/* The date is the group heading directly above, so repeating the raw
              ISO string here was noise. */}
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs"
             style={{ color: 'var(--muted)' }}>
            {wear.apparent_c != null && <span>felt like {Math.round(wear.apparent_c)} °C</span>}
            {wear.condition && <span>{wear.condition}</span>}
            {comfort && (
              <span style={{ color: `var(--${comfort.tone})`, fontWeight: 600 }}>
                {comfort.label}
              </span>
            )}
          </p>
        </div>
        <button
          className="btn btn-ghost btn-icon" disabled={working}
          title="Remove a single item from this wear"
          onClick={() => setEditing((v) => !v)}
        >
          {editing ? <Icon name="check" size={16} /> : <Icon name="edit" size={16} />}
        </button>
        <button
          className="btn btn-ghost btn-icon" disabled={working}
          style={{ color: 'var(--bad)' }} aria-label="Delete this wear"
          onClick={() => onDeleteWear(wear)}
        >
          {working ? <Spinner size={16} /> : <Icon name="trash" size={16} />}
        </button>
      </div>

      {wear.items.length > 0 && (
        <div className="scroll-x mt-2.5 flex gap-2">
          {wear.items.map((item) => (
            <div key={item.id} className="relative w-20 shrink-0">
              <Link to={`/wardrobe/${item.id}`}>
                <div className="aspect-[3/4] overflow-hidden rounded-lg">
                  <ItemPhoto item={item} rounded="rounded-lg" />
                </div>
                <p className="mt-1 truncate text-2xs">{item.name}</p>
              </Link>
              {editing && (
                <button
                  className="absolute -right-1 -top-1 rounded-full p-1"
                  style={{ background: 'var(--bad)', color: '#fff' }}
                  aria-label={`Remove ${item.name} from this wear`}
                  disabled={working}
                  onClick={() => onRemoveItem(wear, item)}
                >
                  <Icon name="close" size={12} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {editing && (
        <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
          Removing one item puts only that item's wear count back. Take the last one out and
          the whole entry goes.
        </p>
      )}

      {wear.notes && (
        <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>{wear.notes}</p>
      )}
    </div>
  )
}

export default function History() {
  const toast = useToast()
  const confirm = useConfirm()
  const [limit, setLimit] = useState(60)
  const [busy, setBusy] = useState(null)
  const { data, loading, error, reload } = useAsync(() => api.wears({ limit }), [limit])

  const wears = data?.wears || []

  const deleteWear = async (wear) => {
    const ok = await confirm({
      title: 'Delete this wear?',
      body: `${wear.items.length} item${wear.items.length === 1 ? '' : 's'} will have their `
            + 'wear counts put back, including progress towards the next wash.',
      detail: 'Any comfort rating on this wear also stops calibrating your suggestions.',
      confirmLabel: 'Delete',
    })
    if (!ok) return
    setBusy(wear.id)
    try {
      await api.deleteWear(wear.id)
      toast('Wear deleted and counters put back.', 'success')
      reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(null) }
  }

  const removeItem = async (wear, item) => {
    setBusy(wear.id)
    try {
      await api.removeWearItem(wear.id, item.id)
      toast(`${item.name} taken out of that wear.`, 'success')
      reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(null) }
  }

  // Grouped by date, because that is how you look for the one you want to fix.
  const days = []
  for (const wear of wears) {
    const last = days[days.length - 1]
    if (last && last.date === wear.worn_on) last.wears.push(wear)
    else days.push({ date: wear.worn_on, wears: [wear] })
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="History"
        description="Everything logged as worn. Deleting an entry puts the wear counters back, so a mis-tap does not leave a shirt waiting to be washed."
      />

      <ErrorNote error={error} onRetry={reload} />

      {loading && !data ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }).map((_, i) =>
            <div key={i} className="skeleton h-28 rounded-2xl" />)}
        </div>
      ) : wears.length === 0 ? (
        <EmptyState
          icon="history"
          title="Nothing logged yet"
          hint="Wear an outfit from Today, or log one from an item's page, and it will show up here."
        />
      ) : (
        <>
          {days.map((day) => (
            <Section key={day.date} title={dayLabel(day.date)}>
              <div className="space-y-2">
                {day.wears.map((wear) => (
                  <WearCard
                    key={wear.id} wear={wear} busy={busy}
                    onDeleteWear={deleteWear} onRemoveItem={removeItem}
                  />
                ))}
              </div>
            </Section>
          ))}

          {wears.length >= limit && (
            <button className="btn w-full" onClick={() => setLimit((l) => l + 60)}>
              <Icon name="chevron" size={16} /> Show older
            </button>
          )}
        </>
      )}
    </div>
  )
}
