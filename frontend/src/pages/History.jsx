import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import ItemPicker from '../components/ItemPicker.jsx'
import {
  Chip, EmptyState, ErrorNote, Field, Icon, Modal, PageHeader, Section, Spinner,
  titleCase, useConfirm, useToast,
} from '../components/ui.jsx'

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

const TODAY = () => new Date().toISOString().slice(0, 10)

const OCCASIONS = ['everyday', 'work', 'smart', 'sport', 'date', 'formal', 'lounge']

/**
 * Log an outfit worn on a past day, or edit one already logged.
 *
 * The same sheet either way, in the outfit builder's format: date with that
 * day's weather previewed, occasion, the shared item picker with its category
 * filter, notes. Editing replaces the items — counters follow the diff, so a
 * removed piece gets its wear back and an added one is counted.
 */
function WearSheet({ existing, onClose, onDone }) {
  const toast = useToast()
  const [day, setDay] = useState(existing?.worn_on || TODAY())
  const [occasion, setOccasion] = useState(existing?.occasion || 'everyday')
  const [notes, setNotes] = useState(existing?.notes || '')
  const [picked, setPicked] = useState(() => (existing?.items || []).map((i) => i.id))
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const wardrobe = useAsync(() => api.items({ limit: 500 }), [])

  const toggle = (id) =>
    setPicked((sel) => sel.includes(id) ? sel.filter((x) => x !== id) : [...sel, id])

  useEffect(() => {
    let live = true
    const unchanged = existing ? day === existing.worn_on : day === TODAY()
    if (!day || unchanged) { setPreview(null); return }
    api.weatherOn(day)
      .then((w) => { if (live) setPreview(w) })
      .catch(() => { if (live) setPreview(null) })
    return () => { live = false }
  }, [day, existing])

  const save = async () => {
    setBusy(true)
    try {
      let res
      if (existing) {
        res = await api.updateWear(existing.id, {
          worn_on: day, occasion, notes: notes.trim() || null, item_ids: picked,
        })
        toast(day !== existing.worn_on && res.wear.apparent_c != null
          ? `Moved to ${res.wear.worn_on}, scored against that day at ${Math.round(res.wear.apparent_c)} °C.`
          : 'Wear updated.', 'success')
      } else {
        res = await api.logWear({
          item_ids: picked, worn_on: day, occasion, notes: notes.trim() || undefined,
        })
        const felt = res.wear.apparent_c
        toast(felt != null
          ? `Logged for ${res.wear.worn_on} — that day felt like ${Math.round(felt)} °C.`
          : `Logged for ${res.wear.worn_on}. No weather record for that day.`, 'success')
      }
      onDone()
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <Modal
      open onClose={busy ? () => {} : onClose} wide
      title={existing ? 'Edit wear' : 'Log a past outfit'}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={save}
                  disabled={busy || !picked.length || !day}>
            {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />}
            {existing ? 'Save' : `Log ${picked.length || ''} item${picked.length === 1 ? '' : 's'}`}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-end gap-x-4 gap-y-2">
          <Field label="Worn on">
            <input className="input !w-auto" type="date" value={day} max={TODAY()}
                   onChange={(e) => setDay(e.target.value)} />
          </Field>
          <p className="pb-2 text-xs" style={{ color: 'var(--muted)' }}>
            {preview
              ? preview.available
                ? `That day: ${preview.condition?.label || '—'}, felt like ${Math.round(preview.apparent_c)} °C`
                : preview.reason
              : existing
                ? existing.apparent_c != null
                  ? `Logged against ${Math.round(existing.apparent_c)} °C`
                  : ''
                : day === TODAY() ? "Today — the live weather will be attached." : 'Looking that day up…'}
          </p>
        </div>

        <Field label="Occasion">
          <div className="rail">
            {OCCASIONS.map((o) => (
              <Chip key={o} active={occasion === o} onClick={() => setOccasion(o)}>
                {titleCase(o)}
              </Chip>
            ))}
          </div>
        </Field>

        <Field label="What was worn">
          <ItemPicker items={wardrobe.data?.items || []} picked={picked}
                      onToggle={toggle} loading={wardrobe.loading && !wardrobe.data} />
        </Field>

        <Field label="Notes" hint="Anything worth remembering. The AI stylist reads these.">
          <textarea className="textarea" rows={2} value={notes}
                    placeholder="Rained on the way back · this worked well"
                    onChange={(e) => setNotes(e.target.value)} />
        </Field>
      </div>
    </Modal>
  )
}

const COMFORT_CHOICES = [
  { verdict: -1, label: 'Too cold' },
  { verdict: 0, label: 'Just right' },
  { verdict: 1, label: 'Too hot' },
]

/**
 * How the outfit actually went.
 *
 * Comfort and rating could only be set at the moment of logging, which is the
 * one moment you cannot know how the day turned out — so in practice neither
 * was ever set, and the calibration that reads them had nothing to learn from.
 *
 * Comfort is the one that does work: it feeds the personal warmth offset, so
 * the suggestions shift towards how you experience a temperature rather than
 * how an average body does. The stars are for you.
 */
function Feedback({ wear, onSave, busy }) {
  const comfort = wear.comfort_rating
  const rating = wear.rating || 0

  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-3"
         style={{ borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2">
        <span className="text-2xs font-semibold uppercase tracking-wide"
              style={{ color: 'var(--muted)' }}>
          How did it feel
        </span>
        <div className="flex gap-1">
          {COMFORT_CHOICES.map((c) => (
            <button
              key={c.verdict} type="button" disabled={busy}
              className={`chip ${comfort === c.verdict ? 'chip-on' : ''}`}
              onClick={() => onSave({ comfort_rating: comfort === c.verdict ? null : c.verdict })}
              aria-pressed={comfort === c.verdict}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-2">
        <span className="text-2xs font-semibold uppercase tracking-wide"
              style={{ color: 'var(--muted)' }}>
          Rate it
        </span>
        <div className="flex items-center gap-0.5">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n} type="button" disabled={busy}
              className="rounded p-0.5"
              aria-label={`${n} star${n === 1 ? '' : 's'}`}
              // Tapping the star you already gave clears it, so a mis-tap is
              // undoable without a separate control.
              onClick={() => onSave({ rating: rating === n ? null : n })}
              style={{ color: n <= rating ? 'var(--accent)' : 'var(--border)' }}
            >
              <Icon name="star" size={16}
                    style={{ fill: n <= rating ? 'var(--accent)' : 'none' }} />
            </button>
          ))}
        </div>
      </div>

      {comfort != null && wear.apparent_c == null && (
        <span className="text-2xs" style={{ color: 'var(--muted)' }}>
          Saved, but with no weather on this wear it cannot calibrate.
        </span>
      )}
    </div>
  )
}


function WearCard({ wear, busy, onDeleteWear, onEdit, onFeedback }) {
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
            {wear.rating ? <span>{'★'.repeat(wear.rating)}</span> : null}
          </p>
        </div>
        <button
          className="btn btn-ghost btn-icon" disabled={working}
          title="Edit this wear — date, items, occasion, notes"
          onClick={() => onEdit(wear)}
        >
          <Icon name="edit" size={16} />
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
            <Link key={item.id} to={`/wardrobe/${item.id}`} className="w-20 shrink-0">
              <div className="aspect-[3/4] overflow-hidden rounded-lg">
                <ItemPhoto item={item} rounded="rounded-lg" />
              </div>
              <p className="mt-1 truncate text-2xs">{item.name}</p>
            </Link>
          ))}
        </div>
      )}

      {wear.notes && (
        <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>{wear.notes}</p>
      )}

      <Feedback wear={wear} busy={working} onSave={(patch) => onFeedback(wear, patch)} />
    </div>
  )
}

export default function History() {
  const toast = useToast()
  const confirm = useConfirm()
  const [limit, setLimit] = useState(60)
  const [busy, setBusy] = useState(null)
  const [adding, setAdding] = useState(false)
  const [editingWear, setEditingWear] = useState(null)
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

  const saveFeedback = async (wear, patch) => {
    setBusy(wear.id)
    try {
      const res = await api.updateWear(wear.id, patch)
      if ('worn_on' in patch) {
        const felt = res.wear.apparent_c
        toast(felt != null
          ? `Moved to ${res.wear.worn_on}, scored against that day at ${Math.round(felt)} °C.`
          : `Moved to ${res.wear.worn_on}. No weather record for that day.`, 'success')
      } else if ('comfort_rating' in patch && patch.comfort_rating !== null) {
        toast(res.calibrated
          ? `Noted. Your warmth offset is now ${res.personal_offset > 0 ? '+' : ''}${res.personal_offset}.`
          : 'Noted.', 'success')
      }
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
        action={
          <button className="btn btn-primary" onClick={() => setAdding(true)}>
            <Icon name="plus" size={16} /> Log a past outfit
          </button>
        }
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
                    onDeleteWear={deleteWear} onEdit={setEditingWear}
                    onFeedback={saveFeedback}
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

      {adding && (
        <WearSheet onClose={() => setAdding(false)} onDone={() => reload(true)} />
      )}
      {editingWear && (
        <WearSheet existing={editingWear} onClose={() => setEditingWear(null)}
                   onDone={() => reload(true)} />
      )}
    </div>
  )
}