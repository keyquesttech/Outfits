import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import {
  Chip, EmptyState, ErrorNote, Field, Icon, Modal, Section, Spinner, titleCase, useToast,
} from '../components/ui.jsx'

const OCCASIONS = ['everyday', 'work', 'smart', 'sport', 'date', 'formal', 'lounge']

function Builder({ open, onClose, onSaved, existing }) {
  const meta = useMeta()
  const toast = useToast()
  const { data } = useAsync(() => api.items({ limit: 500 }), [])
  const [name, setName] = useState(existing?.name || '')
  const [occasion, setOccasion] = useState(existing?.occasion || 'everyday')
  const [picked, setPicked] = useState(() => (existing?.items || []).map((i) => i.id))
  const [layer, setLayer] = useState('top')
  const [busy, setBusy] = useState(false)

  const items = data?.items || []
  const byLayer = useMemo(() => {
    const map = {}
    items.forEach((i) => { (map[i.layer] ||= []).push(i) })
    return map
  }, [items])
  const chosen = items.filter((i) => picked.includes(i.id))
  const warmth = chosen
    .filter((i) => ['bottom', 'top', 'mid', 'outer', 'footwear'].includes(i.layer))
    .reduce((a, i) => a + (i.warmth || 0), 0)

  const toggle = (id) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]))

  const save = async () => {
    if (!name.trim()) return toast('Give the outfit a name.', 'error')
    if (!picked.length) return toast('Pick at least one item.', 'error')
    setBusy(true)
    try {
      const body = { name: name.trim(), occasion, item_ids: picked, is_favourite: !!existing?.is_favourite }
      existing ? await api.updateOutfit(existing.id, body) : await api.createOutfit(body)
      toast(existing ? 'Outfit updated.' : 'Outfit saved.', 'success')
      onSaved()
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title={existing ? 'Edit outfit' : 'Build an outfit'} wide
      footer={<>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save
        </button>
      </>}>
      <div className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name"><input className="input" value={name} onChange={(e) => setName(e.target.value)}
                                     placeholder="Friday work fit" /></Field>
          <Field label="Occasion">
            <select className="select" value={occasion} onChange={(e) => setOccasion(e.target.value)}>
              {OCCASIONS.map((o) => <option key={o} value={o}>{titleCase(o)}</option>)}
            </select>
          </Field>
        </div>

        {chosen.length > 0 && (
          <div className="card px-3 py-3">
            <div className="flex items-center justify-between">
              <p className="label">Picked · {chosen.length}</p>
              <p className="text-xs tabular-nums" style={{ color: 'var(--muted)' }}>total warmth {warmth}</p>
            </div>
            <div className="scroll-x mt-2 flex gap-2">
              {chosen.map((i) => (
                <button key={i.id} onClick={() => toggle(i.id)} className="relative w-16 shrink-0" title="Remove">
                  <div className="aspect-[3/4] overflow-hidden rounded-lg"><ItemPhoto item={i} rounded="rounded-lg" /></div>
                  <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full text-white"
                        style={{ background: 'var(--bad)' }}><Icon name="close" size={11} /></span>
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="scroll-x flex gap-2">
          {(meta.layers || []).map((l) => (
            <Chip key={l} active={layer === l} onClick={() => setLayer(l)}>
              {titleCase(l)} {byLayer[l]?.length ? `(${byLayer[l].length})` : ''}
            </Chip>
          ))}
        </div>

        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {(byLayer[layer] || []).map((i) => (
            <button key={i.id} onClick={() => toggle(i.id)}
                    className="card overflow-hidden text-left"
                    style={picked.includes(i.id) ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 2px var(--accent)' } : undefined}>
              <div className="relative aspect-[3/4] overflow-hidden">
                <ItemPhoto item={i} rounded="" />
                {i.needs_wash && <span className="absolute left-1 top-1 h-2 w-2 rounded-full" style={{ background: 'var(--bad)' }} />}
              </div>
              <p className="truncate px-1.5 py-1 text-[0.7rem] font-medium">{i.name}</p>
            </button>
          ))}
          {!(byLayer[layer] || []).length && (
            <p className="col-span-full py-6 text-center text-sm" style={{ color: 'var(--muted)' }}>
              Nothing in {titleCase(layer)} yet.
            </p>
          )}
        </div>
      </div>
    </Modal>
  )
}

export default function Outfits() {
  const toast = useToast()
  const { data, loading, error, reload } = useAsync(() => api.outfits(), [])
  const [building, setBuilding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(null)

  const outfits = data?.outfits || []

  const wear = async (outfit) => {
    setBusy(outfit.id)
    try {
      const res = await api.logWear({ outfit_id: outfit.id, occasion: outfit.occasion })
      const dirty = res.now_needing_wash?.length
      toast(dirty ? `Logged. ${dirty} item${dirty === 1 ? '' : 's'} now need washing.` : 'Outfit logged.', 'success')
      reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(null) }
  }

  const remove = async (outfit) => {
    if (!confirm(`Delete “${outfit.name}”?`)) return
    await api.deleteOutfit(outfit.id)
    toast('Outfit deleted.', 'success')
    reload(true)
  }

  return (
    <div className="space-y-5">
      <Section
        title="Saved outfits"
        action={<button className="btn btn-primary" onClick={() => setBuilding(true)}>
          <Icon name="plus" size={16} /> Build outfit
        </button>}
      >
        <ErrorNote error={error} onRetry={reload} />
        {loading && !data && <div className="space-y-3">{[0, 1].map((i) => <div key={i} className="skeleton h-40 rounded-2xl" />)}</div>}

        {!loading && !outfits.length && (
          <EmptyState
            icon="layers" title="No outfits saved yet"
            hint="Save the combinations you keep coming back to, then log them in one tap."
            action={<button className="btn btn-primary" onClick={() => setBuilding(true)}>
              <Icon name="plus" size={15} /> Build your first outfit
            </button>}
          />
        )}

        <div className="grid gap-3 md:grid-cols-2">
          {outfits.map((o) => (
            <div key={o.id} className="card overflow-hidden">
              <div className="flex items-start justify-between gap-2 px-4 pt-3.5">
                <div className="min-w-0">
                  <p className="truncate font-semibold">{o.name}</p>
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>
                    {titleCase(o.occasion || 'any')} · warmth {o.total_warmth} · worn {o.times_worn}×
                  </p>
                </div>
                <button className="btn btn-ghost !p-1.5" title="Favourite"
                        onClick={async () => { await api.favouriteOutfit(o.id); reload(true) }}>
                  <Icon name="star" size={17} style={{ color: o.is_favourite ? 'var(--accent)' : 'var(--muted)',
                                                       fill: o.is_favourite ? 'var(--accent)' : 'none' }} />
                </button>
              </div>

              <div className="scroll-x flex gap-2 px-4 py-3">
                {o.items.map((i) => (
                  <Link key={i.id} to={`/wardrobe/${i.id}`} className="w-16 shrink-0" title={i.name}>
                    <div className="aspect-[3/4] overflow-hidden rounded-lg"><ItemPhoto item={i} rounded="rounded-lg" /></div>
                  </Link>
                ))}
              </div>

              {o.needs_wash && (
                <p className="px-4 pb-2 text-xs font-medium" style={{ color: 'var(--bad)' }}>
                  Something in this outfit needs washing
                </p>
              )}

              <div className="flex gap-2 px-4 pb-3">
                <button className="btn btn-primary flex-1" onClick={() => wear(o)} disabled={busy === o.id}>
                  {busy === o.id ? <Spinner size={15} /> : <Icon name="check" size={15} />} Wear today
                </button>
                <button className="btn" onClick={() => setEditing(o)}><Icon name="edit" size={15} /></button>
                <button className="btn btn-ghost" onClick={() => remove(o)}><Icon name="trash" size={15} /></button>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {building && <Builder open onClose={() => setBuilding(false)} onSaved={() => reload(true)} />}
      {editing && <Builder open existing={editing} onClose={() => setEditing(null)} onSaved={() => reload(true)} />}
    </div>
  )
}
