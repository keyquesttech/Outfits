import { useState } from 'react'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync } from '../hooks.js'
import { Chip, Field, Icon, Modal, Spinner, titleCase, useToast } from './ui.jsx'

/** Add a category, or edit one. Two questions; everything else has a default. */
function CategorySheet({ open, category, layers, onClose, onSaved }) {
  const toast = useToast()
  const editing = Boolean(category)
  const [label, setLabel] = useState(category?.label || '')
  const [layer, setLayer] = useState(category?.layer || 'top')
  const [advanced, setAdvanced] = useState(false)
  const [busy, setBusy] = useState(false)
  const [extra, setExtra] = useState({
    warmth: category?.warmth ?? '',
    formality: category?.formality ?? '',
    wash_after_wears: category?.wash_after_wears ?? '',
    one_piece: category?.one_piece ?? false,
    takes_belt: category?.takes_belt ?? false,
  })

  const number = (value) => (value === '' ? null : Number(value))

  const save = async () => {
    if (!label.trim()) return toast('Give the category a name.', 'error')
    setBusy(true)
    try {
      const body = {
        label: label.trim(),
        layer,
        one_piece: extra.one_piece,
        takes_belt: extra.takes_belt,
        ...(advanced || editing ? {
          warmth: number(extra.warmth),
          formality: number(extra.formality),
          wash_after_wears: number(extra.wash_after_wears),
        } : {}),
      }
      if (editing) await api.updateCategory(category.key, body)
      else await api.createCategory(body)
      toast(editing ? `${label} updated.` : `${label} added.`, 'success')
      onSaved()
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <Modal
      open={open} onClose={onClose}
      title={editing ? `Edit ${category.label}` : 'Add a category'}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>
            {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />}
            {editing ? 'Save' : 'Add'}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <Field label="Name">
          <input className="input" value={label} autoFocus autoCapitalize="words"
                 placeholder="Gym kit" onChange={(e) => setLabel(e.target.value)} />
        </Field>

        <Field
          label="Which layer is it?"
          hint="This is the one that matters: it decides which slot the garment fills in an outfit, and the builder only puts one thing in each."
        >
          <div className="space-y-1.5">
            {layers.map((l) => (
              <button
                key={l.key} type="button" onClick={() => setLayer(l.key)}
                className="card flex w-full items-baseline gap-2 px-3 py-2 text-left"
                style={layer === l.key
                  ? { borderColor: 'var(--accent)', background: 'var(--accent-soft)' }
                  : undefined}
              >
                <span className="text-sm font-semibold"
                      style={layer === l.key ? { color: 'var(--accent)' } : undefined}>
                  {l.label}
                </span>
                <span className="text-xs" style={{ color: 'var(--muted)' }}>{l.hint}</span>
              </button>
            ))}
          </div>
        </Field>

        <div className="rail">
          <Chip active={extra.one_piece}
                onClick={() => setExtra({ ...extra, one_piece: !extra.one_piece })}>
            Covers top and bottom
          </Chip>
          <Chip active={extra.takes_belt}
                onClick={() => setExtra({ ...extra, takes_belt: !extra.takes_belt })}>
            Can take a belt
          </Chip>
        </div>

        {!editing && (
          <button type="button" className="btn btn-link"
                  onClick={() => setAdvanced((v) => !v)}>
            <Icon name="chevron" size={14}
                  style={{ transform: advanced ? 'rotate(180deg)' : 'none' }} />
            {advanced ? 'Hide defaults' : 'Set the defaults myself'}
          </button>
        )}

        {(advanced || editing) && (
          <div className="grid grid-cols-3 gap-3">
            <Field label="Warmth" hint="0-10">
              <input className="input" type="number" min="0" max="10" value={extra.warmth}
                     placeholder="auto"
                     onChange={(e) => setExtra({ ...extra, warmth: e.target.value })} />
            </Field>
            <Field label="Formality" hint="1-5">
              <input className="input" type="number" min="1" max="5" value={extra.formality}
                     placeholder="auto"
                     onChange={(e) => setExtra({ ...extra, formality: e.target.value })} />
            </Field>
            <Field label="Wash after" hint="0 = never">
              <input className="input" type="number" min="0" value={extra.wash_after_wears}
                     placeholder="auto"
                     onChange={(e) => setExtra({ ...extra, wash_after_wears: e.target.value })} />
            </Field>
          </div>
        )}

        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          {advanced || editing
            ? 'These seed a new item; every one stays editable per garment.'
            : 'Warmth, formality and how many wears before washing are taken from the layer. Each is editable per garment anyway.'}
        </p>
      </div>
    </Modal>
  )
}

/**
 * Deleting a category that still holds garments would orphan them: they would
 * keep a name nothing recognises, so they would lose their layer and drop out
 * of outfits. So the delete asks where they should go instead.
 */
function DeleteSheet({ open, category, options, onClose, onDone }) {
  const toast = useToast()
  const [moveTo, setMoveTo] = useState('')
  const [busy, setBusy] = useState(false)
  const occupied = category.count > 0

  const remove = async () => {
    if (occupied && !moveTo) return toast('Choose where these items should go.', 'error')
    setBusy(true)
    try {
      await api.deleteCategory(category.key, occupied ? moveTo : undefined)
      toast(`${category.label} removed.`, 'success')
      onDone()
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <Modal
      open={open} onClose={onClose} title={`Remove ${category.label}`}
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={remove} disabled={busy}
                  style={{ background: 'var(--bad)', borderColor: 'var(--bad)' }}>
            {busy ? <Spinner size={16} /> : <Icon name="trash" size={16} />} Remove
          </button>
        </>
      }
    >
      {occupied ? (
        <div className="space-y-3">
          <p className="text-sm">
            {category.count} item{category.count === 1 ? '' : 's'} {category.count === 1 ? 'is' : 'are'} filed
            under {category.label}. They need a category to keep their layer, so pick one to move
            them to.
          </p>
          <Field label="Move them to">
            <select className="select" value={moveTo} onChange={(e) => setMoveTo(e.target.value)}>
              <option value="">Choose a category…</option>
              {options.filter((c) => c.key !== category.key).map((c) => (
                <option key={c.key} value={c.key}>{c.label}</option>
              ))}
            </select>
          </Field>
        </div>
      ) : (
        <p className="text-sm">
          Nothing is filed under {category.label}, so removing it only takes it off the list.
          You can add it back later.
        </p>
      )}
    </Modal>
  )
}

export default function CategoryManager() {
  const meta = useMeta()
  const [version, setVersion] = useState(0)
  const { data, loading } = useAsync(() => api.categories(), [version])
  const [editing, setEditing] = useState(null)
  const [adding, setAdding] = useState(false)
  const [removing, setRemoving] = useState(null)

  const categories = data?.categories || []
  const layers = data?.layers || []

  const refresh = () => {
    setVersion((v) => v + 1)
    meta.reloadMeta?.()      // the item form reads its dropdown from meta
  }

  return (
    <div className="card px-4 py-4">
      <p className="text-sm" style={{ color: 'var(--muted)' }}>
        The wardrobe filter only shows categories with something in them, so an unused one
        is out of your way already — remove it here when you want it off the list for good.
      </p>

      {loading && !data ? (
        <div className="py-6 text-center"><Spinner /></div>
      ) : (
        <div className="mt-3 divide-y" style={{ borderColor: 'var(--border)' }}>
          {categories.map((c) => (
            <div key={c.key} className="flex items-center gap-2 py-2">
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold">{c.label}</p>
                <p className="truncate text-xs" style={{ color: 'var(--muted)' }}>
                  {titleCase(c.layer)} layer · {c.count} item{c.count === 1 ? '' : 's'}
                  {c.launderable ? ` · washes after ${c.wash_after_wears}` : ' · never washed'}
                  {c.one_piece ? ' · one piece' : ''}
                </p>
              </div>
              <button className="btn btn-ghost btn-icon" onClick={() => setEditing(c)}
                      aria-label={`Edit ${c.label}`}>
                <Icon name="edit" size={16} />
              </button>
              <button className="btn btn-ghost btn-icon" onClick={() => setRemoving(c)}
                      aria-label={`Remove ${c.label}`} style={{ color: 'var(--bad)' }}>
                <Icon name="trash" size={16} />
              </button>
            </div>
          ))}
        </div>
      )}

      <button className="btn btn-primary mt-3" onClick={() => setAdding(true)}>
        <Icon name="plus" size={16} /> Add a category
      </button>

      {adding && (
        <CategorySheet open layers={layers} onClose={() => setAdding(false)} onSaved={refresh} />
      )}
      {editing && (
        <CategorySheet open category={editing} layers={layers}
                       onClose={() => setEditing(null)} onSaved={refresh} />
      )}
      {removing && (
        <DeleteSheet open category={removing} options={categories}
                     onClose={() => setRemoving(null)} onDone={refresh} />
      )}
    </div>
  )
}
