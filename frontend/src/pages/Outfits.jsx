import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import ItemPicker from '../components/ItemPicker.jsx'
import {
  Chip, EmptyState, ErrorNote, Field, Icon, Modal, PageHeader, Section, Spinner,
  titleCase, useConfirm, useToast,
} from '../components/ui.jsx'

const OCCASIONS = ['everyday', 'work', 'smart', 'sport', 'date', 'formal', 'lounge']

function Builder({ open, onClose, onSaved, existing, bases = [] }) {
  const meta = useMeta()
  const toast = useToast()
  const { data } = useAsync(() => api.items({ limit: 500 }), [])
  const [name, setName] = useState(existing?.name || '')
  const [occasion, setOccasion] = useState(existing?.occasion || 'everyday')
  const [picked, setPicked] = useState(() => (existing?.items || []).map((i) => i.id))
  const [isBase, setIsBase] = useState(!!existing?.is_base)
  const [busy, setBusy] = useState(false)

  // A base seeds a new outfit: its pieces come in already picked, and the rest
  // is built on top.
  const startFrom = (base) => {
    setPicked(base.items.map((i) => i.id))
    if (base.occasion) setOccasion(base.occasion)
    if (!name.trim()) setName('')
  }

  const items = data?.items || []
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
      const body = { name: name.trim(), occasion, item_ids: picked,
                     is_favourite: !!existing?.is_favourite, is_base: isBase }
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
          {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />} Save
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

        {!existing && bases.length > 0 && (
          <Field label="Start from a base">
            <div className="rail">
              {bases.map((b) => (
                <Chip key={b.id} onClick={() => startFrom(b)}>
                  <Icon name="layers" size={14} /> {b.name}
                </Chip>
              ))}
            </div>
          </Field>
        )}

        <div className="rail">
          <Chip active={isBase} onClick={() => setIsBase(!isBase)}>
            <Icon name="layers" size={14} /> This is a base
          </Chip>
          <span className="self-center text-xs" style={{ color: 'var(--muted)' }}>
            {isBase
              ? 'A starting point — the Today page suggests the rest around these pieces.'
              : 'Pick several tops, bottoms or shoes and they become options: wearing the outfit picks the best one for the day.'}
          </span>
        </div>

        {chosen.length > 0 && (
          <p className="text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
            Total warmth {warmth}
          </p>
        )}

        <ItemPicker items={items} picked={picked} onToggle={toggle} loading={!data} />
      </div>
    </Modal>
  )
}

export default function Outfits() {
  const toast = useToast()
  const confirm = useConfirm()
  const { data, loading, error, reload } = useAsync(() => api.outfits(), [])
  const [building, setBuilding] = useState(false)
  const [editing, setEditing] = useState(null)
  const [busy, setBusy] = useState(null)

  const outfits = data?.outfits || []
  const bases = outfits.filter((o) => o.is_base)

  const wear = async (outfit) => {
    setBusy(outfit.id)
    try {
      const res = await api.logWear({ outfit_id: outfit.id, occasion: outfit.occasion })
      const names = res.resolved ? res.wear.items.map((i) => i.name).join(', ') : null
      toast(names ? `Picked for today: ${names}.` : 'Outfit logged.', 'success')
      reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(null) }
  }

  const remove = async (outfit) => {
    const ok = await confirm({
      title: 'Delete this outfit?',
      body: `“${outfit.name}” will be removed.`,
      detail: 'The items stay in your wardrobe; only the saved combination goes.',
    })
    if (!ok) return
    await api.deleteOutfit(outfit.id)
    toast('Outfit deleted.', 'success')
    reload(true)
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Outfits"
        description="Combinations worth keeping, so you do not rebuild them each time."
        action={
          <button className="btn btn-primary" onClick={() => setBuilding(true)}>
            <Icon name="plus" size={16} /> Build outfit
          </button>
        }
      />
      <Section>
        <ErrorNote error={error} onRetry={reload} />
        {loading && !data && <div className="space-y-3">{[0, 1].map((i) => <div key={i} className="skeleton h-40 rounded-2xl" />)}</div>}

        {!loading && !outfits.length && (
          <EmptyState
            icon="layers" title="No outfits saved yet"
            hint="Save the combinations you keep coming back to, then log them in one tap."
            action={<button className="btn btn-primary" onClick={() => setBuilding(true)}>
              <Icon name="plus" size={16} /> Build your first outfit
            </button>}
          />
        )}

        <div className="grid gap-3 sm:gap-4 md:grid-cols-2 xl:grid-cols-3">
          {outfits.map((o) => (
            <div key={o.id} className="card card-link flex flex-col overflow-hidden">
              <div className="flex items-start justify-between gap-2 px-4 pt-3.5">
                <div className="min-w-0">
                  <p className="truncate font-semibold">
                    {o.name}
                    {o.is_base && (
                      <span className="ml-2 rounded-full px-2 py-0.5 text-2xs font-bold align-middle uppercase tracking-wide"
                            style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
                        Base
                      </span>
                    )}
                  </p>
                  <p className="mt-0.5 text-xs" style={{ color: 'var(--muted)' }}>
                    {titleCase(o.occasion || 'any')} · warmth {o.total_warmth} · worn {o.times_worn}×
                  </p>
                </div>
                <button className="btn btn-ghost btn-icon" title="Favourite"
                        onClick={async () => { await api.favouriteOutfit(o.id); reload(true) }}>
                  <Icon name="star" size={18} style={{ color: o.is_favourite ? 'var(--accent)' : 'var(--muted)',
                                                       fill: o.is_favourite ? 'var(--accent)' : 'none' }} />
                </button>
              </div>

              <div className="scroll-x flex gap-2 px-4 py-3">
                {o.items.map((i) => (
                  <Link key={i.id} to={`/wardrobe/${i.id}`} className="w-[4.5rem] shrink-0" title={i.name}>
                    <div className="aspect-[3/4] overflow-hidden rounded-lg border"
                         style={{ borderColor: 'var(--border)' }}>
                      <ItemPhoto item={i} rounded="rounded-[.45rem]" />
                    </div>
                  </Link>
                ))}
              </div>

              {Object.keys(o.option_layers || {}).length > 0 && (
                <p className="px-4 pb-2 text-xs" style={{ color: 'var(--muted)' }}>
                  Options: {Object.entries(o.option_layers)
                    .map(([l, n]) => `${n} ${titleCase(l)}`).join(' · ')} — wearing picks
                  the best for the day.
                </p>
              )}

              <div className="mt-auto flex gap-2 px-4 pb-3.5 pt-1">
                {o.is_base ? (
                  <Link to={`/?base=${o.id}`} className="btn btn-primary flex-1">
                    <Icon name="sparkle" size={16} /> Suggest around this
                  </Link>
                ) : (
                  <button className="btn btn-primary flex-1" onClick={() => wear(o)} disabled={busy === o.id}>
                    {busy === o.id ? <Spinner size={16} /> : <Icon name="check" size={16} />} Wear today
                  </button>
                )}
                <button className="btn" onClick={() => setEditing(o)}><Icon name="edit" size={16} /></button>
                <button className="btn btn-ghost" onClick={() => remove(o)}><Icon name="trash" size={16} /></button>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {building && <Builder open bases={bases} onClose={() => setBuilding(false)} onSaved={() => reload(true)} />}
      {editing && <Builder open existing={editing} onClose={() => setEditing(null)} onSaved={() => reload(true)} />}
    </div>
  )
}
