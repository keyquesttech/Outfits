import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync, useDebounced, useLocalState } from '../hooks.js'
import { ItemGrid, ItemPhoto } from '../components/ItemCard.jsx'
import ItemForm, { itemFormPayload, itemFormState } from '../components/ItemForm.jsx'
import {
  Chip, EmptyState, ErrorNote, Field, Icon, Modal, Spinner, titleCase, useToast,
} from '../components/ui.jsx'

const SORTS = [
  ['recent', 'Newest'], ['name', 'A–Z'], ['worn', 'Most worn'],
  ['least_worn', 'Least worn'], ['value', 'Priciest'],
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
            {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />}
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
  const inputRef = useRef(null)

  const aiReady = useAsync(() => api.settings(), [])
  const aiAvailable = aiReady.data?.ai?.available

  const pick = (files) => {
    const list = Array.from(files || [])
    if (list.length) {
      setQueue(list.map((f) => ({
        file: f, name: f.name.replace(/\.[^.]+$/, ''), state: 'ready',
      })))
    }
  }

  const reset = () => { setQueue([]); onClose() }

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
            {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />}
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
              <option key={c} value={c}>{titleCase(c)}</option>
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
              <Icon name="edit" size={17} style={{ color: 'var(--accent)', marginTop: 2 }} />
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
              <Icon name="sparkle" size={17} style={{ color: 'var(--accent)', marginTop: 2 }} />
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
              <div key={i} className="flex items-center gap-3 px-3 py-2">
                <img src={URL.createObjectURL(q.file)} alt=""
                     className="h-12 w-12 rounded-lg object-cover" />
                <input
                  className="input flex-1" value={q.name} placeholder="Item name" disabled={busy}
                  onChange={(e) =>
                    setQueue((qq) => qq.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
                />
                <span className="w-5 shrink-0 text-center">
                  {q.state === 'uploading' && <Spinner size={15} />}
                  {q.state === 'done' && <Icon name="check" size={16} style={{ color: 'var(--good)' }} />}
                  {q.state === 'error' && <span title={q.error} style={{ color: 'var(--bad)' }}>!</span>}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
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
  const [status, setStatus] = useState('')
  const [sort, setSort] = useLocalState('outfits.sort', 'recent')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [tagging, setTagging] = useState(null)

  const load = useCallback(
    () => api.items({ q, category, status, sort }),
    [q, category, status, sort]
  )
  const { data, loading, error, reload } = useAsync(load, [q, category, status, sort])
  const items = data?.items || []

  const afterUpload = (created, mode) => {
    reload(true)
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
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2"
                style={{ color: 'var(--muted)' }}>
            <Icon name="search" size={16} />
          </span>
          <input
            className="input pl-9" placeholder="Search name, brand, material…"
            value={search} onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button className="btn btn-primary shrink-0" onClick={() => setUploadOpen(true)}>
          <Icon name="plus" size={16} /> <span className="hidden sm:inline">Add item</span>
        </button>
      </div>

      <div className="space-y-2">
        <div className="scroll-x flex gap-2">
          <Chip active={!category} onClick={() => setCategory('')}>All</Chip>
          {(meta.categories || []).map((c) => (
            <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? '' : c)}>
              {titleCase(c)}
            </Chip>
          ))}
        </div>
        <div className="scroll-x flex gap-2">
          <Chip active={!status} onClick={() => setStatus('')}>Any status</Chip>
          {(meta.statuses || []).map((s) => (
            <Chip key={s} active={status === s} onClick={() => setStatus(status === s ? '' : s)}>
              {titleCase(s)}
            </Chip>
          ))}
          <span className="mx-1 w-px shrink-0" style={{ background: 'var(--border)' }} />
          {SORTS.map(([value, label]) => (
            <Chip key={value} active={sort === value} onClick={() => setSort(value)}>{label}</Chip>
          ))}
        </div>
      </div>

      <ErrorNote error={error} onRetry={reload} />

      {loading && !data ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {Array.from({ length: 8 }).map((_, i) =>
            <div key={i} className="skeleton aspect-[3/4] rounded-2xl" />)}
        </div>
      ) : (
        <>
          {items.length > 0 && (
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              {items.length} item{items.length === 1 ? '' : 's'}
            </p>
          )}
          <ItemGrid
            items={items}
            empty={
              <EmptyState
                icon="hanger"
                title={q || category || status ? 'Nothing matches' : 'Your wardrobe is empty'}
                hint={q || category || status
                  ? 'Try clearing the filters.'
                  : 'Photograph a few things you actually wear. Everything else builds on top of that.'}
                action={
                  <button className="btn btn-primary" onClick={() => setUploadOpen(true)}>
                    <Icon name="camera" size={15} /> Add your first item
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
          onDone={() => reload(true)}
        />
      )}
    </div>
  )
}
