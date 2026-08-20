import { useCallback, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync, useDebounced, useLocalState } from '../hooks.js'
import { ItemGrid, ItemPhoto } from '../components/ItemCard.jsx'
import ItemForm, { itemFormPayload, itemFormState } from '../components/ItemForm.jsx'
import ImageEditor from '../components/ImageEditor.jsx'
import { Swatch } from '../components/ColourField.jsx'
import {
  Chip, EmptyState, ErrorNote, Field, Icon, Modal, PageHeader, Spinner, titleCase,
  useToast,
} from '../components/ui.jsx'

const SORTS = [
  ['recent', 'Newest'], ['name', 'A–Z'], ['worn', 'Most worn'],
  ['least_worn', 'Least worn'],
]

/* ---------------------------------------------------------------- tagging */

/** Walks through freshly added items one at a time, filling in their details. */
function TagSheet({ open, items, onClose, onDone }) {
  const meta = useMeta()
  const toast = useToast()
  const [index, setIndex] = useState(0)
  const [form, setForm] = useState(() => itemFormState(items[0]))
  const [busy, setBusy] = useState(false)

  const item = items[index]
  const last = index === items.length - 1

  const goTo = (next) => {
    setIndex(next)
    setForm(itemFormState(items[next]))
  }

  const finish = () => {
    onDone()
    onClose()
  }

  const save = async ({ advance = true } = {}) => {
    setBusy(true)
    try {
      await api.updateItem(item.id, itemFormPayload(form))
      if (advance && !last) {
        goTo(index + 1)
      } else {
        toast(`Tagged ${items.length} item${items.length === 1 ? '' : 's'}.`, 'success')
        finish()
      }
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const skip = () => (last ? finish() : goTo(index + 1))

  return (
    <Modal
      open={open}
      onClose={finish}
      wide
      title={items.length > 1 ? `Tag item ${index + 1} of ${items.length}` : 'Tag this item'}
      footer={
        <>
          <button className="btn btn-ghost" onClick={skip} disabled={busy}>
            {last ? 'Finish' : 'Skip'}
          </button>
          {index > 0 && (
            <button className="btn" onClick={() => goTo(index - 1)} disabled={busy}>Back</button>
          )}
          <button className="btn btn-primary" onClick={() => save()} disabled={busy}>
            {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />}
            {last ? 'Save and finish' : 'Save and next'}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        {items.length > 1 && (
          <div className="flex gap-1">
            {items.map((_, i) => (
              <span key={i} className="h-1 flex-1 rounded-full"
                    style={{ background: i <= index ? 'var(--accent)' : 'var(--surface-2)' }} />
            ))}
          </div>
        )}

        <div className="flex gap-4">
          <div className="h-32 w-24 shrink-0 overflow-hidden rounded-xl">
            <ItemPhoto item={item} full />
          </div>
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Warmth and formality are what the weather matching actually uses, so they are
            worth getting roughly right. Everything else can wait — you can edit any item
            later.
          </p>
        </div>

        <ItemForm form={form} setForm={setForm} meta={meta} palette={item.palette} />

      </div>
    </Modal>
  )
}

/* ---------------------------------------------------------------- upload */

function UploadSheet({ open, onClose, onDone }) {
  const meta = useMeta()
  const toast = useToast()
  const [category, setCategory] = useLocalState('outfits.lastCategory', 'top')
  const [mode, setMode] = useLocalState('outfits.tagMode', 'manual')
  const [queue, setQueue] = useState([])
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState(null)
  const inputRef = useRef(null)

  const aiReady = useAsync(() => api.settings(), [])
  const aiAvailable = aiReady.data?.ai?.available

  const pick = (files) => {
    const list = Array.from(files || [])
    if (list.length) {
      setQueue(list.map((f) => ({
        file: f, name: f.name.replace(/\.[^.]+$/, ''), state: 'ready',
        preview: URL.createObjectURL(f), edited: false,
      })))
    }
  }

  const applyEdit = (index) => (edited) => {
    setQueue((qq) => qq.map((x, j) => {
      if (j !== index) return x
      URL.revokeObjectURL(x.preview)
      return { ...x, file: edited, preview: URL.createObjectURL(edited), edited: true }
    }))
    setEditing(null)
  }

  const reset = () => {
    queue.forEach((q) => URL.revokeObjectURL(q.preview))
    setQueue([])
    onClose()
  }

  const upload = async () => {
    setBusy(true)
    const created = []
    for (let i = 0; i < queue.length; i++) {
      setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: 'uploading' } : x)))
      try {
        const item = await api.uploadItem(queue[i].file, {
          name: queue[i].name || 'Untitled item',
          category,
          analyse: mode === 'ai',
        })
        created.push(item)
        setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: 'done' } : x)))
      } catch (e) {
        setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: 'error', error: e.message } : x)))
      }
    }
    setBusy(false)
    if (created.length) {
      setQueue([])
      onDone(created, mode)
    }
  }

  return (
    <Modal
      open={open} onClose={busy ? () => {} : reset} title="Add to wardrobe" wide
      footer={
        <>
          <button className="btn" onClick={reset} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={upload} disabled={busy || !queue.length}>
            {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />}
            Add {queue.length || ''}
          </button>
        </>
      }
    >
      <div className="space-y-4">
        <input
          ref={inputRef} type="file" accept="image/*" multiple capture="environment"
          className="hidden" onChange={(e) => pick(e.target.files)}
        />
        <button
          className="card flex w-full flex-col items-center gap-2 border-dashed px-4 py-8"
          onClick={() => inputRef.current?.click()} disabled={busy}
        >
          <span className="rounded-full p-3"
                style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
            <Icon name="camera" size={24} />
          </span>
          <span className="text-sm font-semibold">Take a photo or choose files</span>
          <span className="text-xs" style={{ color: 'var(--muted)' }}>
            Colours are read from the photo automatically, with or without AI
          </span>
        </button>

        <Field label="Category" hint="You can change this per item while tagging.">
          <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            {(meta.categories || []).map((c) => (
              <option key={c} value={c}>{meta.category_labels?.[c] || titleCase(c)}</option>
            ))}
          </select>
        </Field>

        <Field label="How should these be tagged?">
          <div className="space-y-2">
            <button
              type="button" onClick={() => setMode('manual')}
              className="card flex w-full items-start gap-3 px-3 py-2.5 text-left"
              style={mode === 'manual' ? { borderColor: 'var(--accent)' } : undefined}
            >
              <Icon name="edit" size={18} style={{ color: 'var(--accent)', marginTop: 2 }} />
              <span>
                <span className="block text-sm font-semibold">Tag them myself</span>
                <span className="block text-xs" style={{ color: 'var(--muted)' }}>
                  Opens a form for each item right after uploading. No AI involved.
                </span>
              </span>
            </button>

            <button
              type="button"
              onClick={() => aiAvailable && setMode('ai')}
              disabled={!aiAvailable}
              className="card flex w-full items-start gap-3 px-3 py-2.5 text-left"
              style={{
                borderColor: mode === 'ai' ? 'var(--accent)' : undefined,
                opacity: aiAvailable ? 1 : 0.55,
              }}
            >
              <Icon name="sparkle" size={18} style={{ color: 'var(--accent)', marginTop: 2 }} />
              <span>
                <span className="block text-sm font-semibold">Let AI tag them</span>
                <span className="block text-xs" style={{ color: 'var(--muted)' }}>
                  {aiAvailable
                    ? 'Fills in category, material, warmth and formality for you to check.'
                    : 'Needs an AI provider — set one up in Settings.'}
                </span>
              </span>
            </button>
          </div>
        </Field>

        {queue.length > 0 && (
          <div className="card divide-y" style={{ borderColor: 'var(--border)' }}>
            {queue.map((q, i) => (
              <div key={i} className="flex items-center gap-2 px-3 py-2 sm:gap-3">
                <img src={q.preview} alt=""
                     className="h-12 w-12 shrink-0 rounded-lg object-cover" />
                <input
                  className="input min-w-0 flex-1" value={q.name} placeholder="Item name"
                  disabled={busy}
                  onChange={(e) =>
                    setQueue((qq) => qq.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                />
                <button
                  className="btn btn-ghost btn-icon shrink-0" disabled={busy}
                  title="Rotate or crop this photo"
                  onClick={() => setEditing(i)}
                >
                  <Icon name="crop" size={16} />
                  {q.edited && (
                    <span className="text-2xs font-bold" style={{ color: 'var(--accent)' }}>
                      edited
                    </span>
                  )}
                </button>
                <span className="w-5 shrink-0 text-center">
                  {q.state === 'uploading' && <Spinner size={16} />}
                  {q.state === 'done' && <Icon name="check" size={16} style={{ color: 'var(--good)' }} />}
                  {q.state === 'error' && <span title={q.error} style={{ color: 'var(--bad)' }}>!</span>}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {editing !== null && queue[editing] && (
        <ImageEditor
          open file={queue[editing].file}
          onCancel={() => setEditing(null)}
          onApply={applyEdit(editing)}
        />
      )}
    </Modal>
  )
}

/* ---------------------------------------------------------------- page */

export default function Wardrobe() {
  const meta = useMeta()
  const navigate = useNavigate()
  const toast = useToast()
  const [search, setSearch] = useState('')
  const q = useDebounced(search, 280)
  const [category, setCategory] = useState('')
  const [subcategory, setSubcategory] = useState('')
  const [colour, setColour] = useState('')
  const [sort, setSort] = useLocalState('outfits.sort', 'recent')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [tagging, setTagging] = useState(null)
  // Bumped whenever items change, so the category counts follow them.
  const [version, setVersion] = useState(0)

  const load = useCallback(
    () => api.items({ q, category, subcategory, colour, sort }),
    [q, category, subcategory, colour, sort]
  )
  const { data, loading, error, reload } =
    useAsync(load, [q, category, subcategory, colour, sort])
  const items = data?.items || []
  const filtering = Boolean(q || category || subcategory || colour)

  // Subcategories present in what is on screen, same ref trick as the colour
  // rail: picking one narrows the results to itself, and rebuilding the rail
  // from those would leave a single chip and no way back.
  const subRef = useRef([])
  const subcats = useMemo(() => {
    if (subcategory) return subRef.current
    const counts = new Map()
    for (const item of items) {
      const raw = String(item.subcategory || '').trim()
      if (!raw) continue
      const key = raw.toLowerCase()
      const slot = counts.get(key) || { key, label: raw, count: 0 }
      slot.count += 1
      counts.set(key, slot)
    }
    subRef.current = [...counts.values()]
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
    return subRef.current
  }, [items, subcategory])

  // Only the categories you actually own something in. Nineteen chips, most of
  // them matching nothing, is a worse filter than the five you wear — and the
  // counts have to come from their own call, because `items` is already
  // filtered and would collapse the rail to whatever is selected.
  const catalogue = useAsync(() => api.categories(), [version])
  const inUse = (catalogue.data?.categories || []).filter(
    (c) => c.count > 0 || c.key === category)

  // Only offer the colours actually owned. A rail of thirty-six swatches, most
  // of which match nothing, is a worse filter than a rail of the eight you wear.
  //
  // Held in a ref and refreshed only while no colour is chosen: picking one
  // narrows the results to that colour, and rebuilding the rail from those
  // would leave a single chip and no way back to the others.
  const railRef = useRef([])
  const owned = useMemo(() => {
    if (colour) return railRef.current
    const counts = new Map()
    for (const item of items) {
      const name = String(item.colour_primary || '').toLowerCase()
      if (name) counts.set(name, (counts.get(name) || 0) + 1)
    }
    const swatches = meta.colours || []
    railRef.current = [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
      .map(([name]) => ({ name, hex: swatches.find((c) => c.name === name)?.hex || null }))
    return railRef.current
  }, [items, colour, meta.colours])

  const afterUpload = (created, mode) => {
    reload(true)
    setVersion((v) => v + 1)
    if (mode === 'manual') {
      setUploadOpen(false)
      setTagging(created)
    } else {
      toast(`Added ${created.length}. AI is tagging them now.`, 'success')
      setUploadOpen(false)
      if (created.length === 1) navigate(`/wardrobe/${created[0].id}`)
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Wardrobe"
        description="Everything you own, and what the app knows about it."
        action={
          <button className="btn btn-primary" onClick={() => setUploadOpen(true)}>
            <Icon name="plus" size={16} /> Add item
          </button>
        }
      />

      <div className="relative">
        <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
              style={{ color: 'var(--muted)' }}>
          <Icon name="search" size={16} />
        </span>
        <input
          className="input pl-9 pr-9" type="search" placeholder="Search name, brand, material…"
          value={search} onChange={(e) => setSearch(e.target.value)}
        />
        {search && (
          <button
            type="button" onClick={() => setSearch('')} aria-label="Clear search"
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1"
            style={{ color: 'var(--muted)' }}
          >
            <Icon name="close" size={14} />
          </button>
        )}
      </div>

      <div className="space-y-2">
        <div className="rail">
          <Chip active={!category} onClick={() => { setCategory(''); setSubcategory('') }}>All</Chip>
          {inUse.map((c) => (
            <Chip key={c.key} active={category === c.key}
                  onClick={() => { setCategory(category === c.key ? '' : c.key); setSubcategory('') }}>
              {c.label}
              <span className="tabular-nums" style={{ opacity: 0.6 }}>{c.count}</span>
            </Chip>
          ))}
          {catalogue.data && inUse.length === 0 && (
            <span className="text-xs" style={{ color: 'var(--muted)' }}>
              No categories in use yet.
            </span>
          )}
        </div>
        {subcats.length > 1 && (
          <div className="rail">
            <Chip active={!subcategory} onClick={() => setSubcategory('')}>Any type</Chip>
            {subcats.map((sc) => (
              <Chip key={sc.key} active={subcategory === sc.key}
                    onClick={() => setSubcategory(subcategory === sc.key ? '' : sc.key)}>
                {sc.label}
                <span className="tabular-nums" style={{ opacity: 0.6 }}>{sc.count}</span>
              </Chip>
            ))}
          </div>
        )}
        {owned.length > 1 && (
          <div className="rail">
            <Chip active={!colour} onClick={() => setColour('')}>Any colour</Chip>
            {owned.map((c) => (
              <Chip key={c.name} active={colour === c.name}
                    onClick={() => setColour(colour === c.name ? '' : c.name)}>
                <Swatch hex={c.hex} size={12} /> {titleCase(c.name)}
              </Chip>
            ))}
          </div>
        )}
      </div>

      <ErrorNote error={error} onRetry={reload} />

      {loading && !data ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
          {Array.from({ length: 8 }).map((_, i) =>
            <div key={i} className="skeleton aspect-[3/4] rounded-2xl" />)}
        </div>
      ) : (
        <>
          {items.length > 0 && (
            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                {items.length} item{items.length === 1 ? '' : 's'}
                {filtering && ' matching'}
              </p>
              <div className="flex items-center gap-1.5">
                <span className="text-xs" style={{ color: 'var(--muted)' }}>Sort</span>
                <select className="select !w-auto !py-1 text-xs" value={sort}
                        onChange={(e) => setSort(e.target.value)} aria-label="Sort items">
                  {SORTS.map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </div>
            </div>
          )}
          <ItemGrid
            items={items}
            empty={
              <EmptyState
                icon="hanger"
                title={filtering ? 'Nothing matches' : 'Your wardrobe is empty'}
                hint={filtering
                  ? 'Try clearing the filters.'
                  : 'Photograph a few things you actually wear. Everything else builds on top of that.'}
                action={
                  <button className="btn btn-primary" onClick={() => setUploadOpen(true)}>
                    <Icon name="camera" size={16} /> Add your first item
                  </button>
                }
              />
            }
          />
        </>
      )}

      {uploadOpen && (
        <UploadSheet open onClose={() => setUploadOpen(false)} onDone={afterUpload} />
      )}
      {tagging && (
        <TagSheet
          open items={tagging}
          onClose={() => setTagging(null)}
          onDone={() => { reload(true); setVersion((v) => v + 1) }}
        />
      )}
    </div>
  )
}
