import { useCallback, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync, useDebounced, useLocalState } from '../hooks.js'
import { ItemGrid } from '../components/ItemCard.jsx'
import {
  Chip, EmptyState, ErrorNote, Field, Icon, Modal, Spinner, titleCase, useToast,
} from '../components/ui.jsx'

const SORTS = [
  ['recent', 'Newest'], ['name', 'A–Z'], ['worn', 'Most worn'],
  ['least_worn', 'Least worn'], ['value', 'Priciest'],
]

function UploadSheet({ open, onClose, onDone }) {
  const meta = useMeta()
  const toast = useToast()
  const [category, setCategory] = useLocalState('outfits.lastCategory', 'top')
  const [analyse, setAnalyse] = useState(true)
  const [queue, setQueue] = useState([])
  const [busy, setBusy] = useState(false)
  const inputRef = useRef(null)

  const pick = (files) => {
    const list = Array.from(files || [])
    if (list.length) setQueue(list.map((f) => ({ file: f, name: f.name.replace(/\.[^.]+$/, ''), state: 'ready' })))
  }

  const upload = async () => {
    setBusy(true)
    const done = []
    for (let i = 0; i < queue.length; i++) {
      setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: 'uploading' } : x)))
      try {
        const item = await api.uploadItem(queue[i].file, {
          name: queue[i].name || 'Untitled item', category, analyse,
        })
        done.push(item)
        setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: 'done' } : x)))
      } catch (e) {
        setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: 'error', error: e.message } : x)))
      }
    }
    setBusy(false)
    const ok = done.length
    if (ok) {
      const queued = done.some((d) => d.queued_jobs?.length)
      toast(queued ? `Added ${ok} item${ok === 1 ? '' : 's'}. AI is tagging them now.`
                   : `Added ${ok} item${ok === 1 ? '' : 's'}.`, 'success')
      onDone(done)
      if (done.length === queue.length) { setQueue([]); onClose() }
    }
  }

  return (
    <Modal
      open={open} onClose={busy ? () => {} : onClose} title="Add to wardrobe" wide
      footer={
        <>
          <button className="btn" onClick={onClose} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={upload} disabled={busy || !queue.length}>
            {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />}
            Add {queue.length ? queue.length : ''}
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
          <span className="rounded-full p-3" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
            <Icon name="camera" size={24} />
          </span>
          <span className="text-sm font-semibold">Take a photo or choose files</span>
          <span className="text-xs" style={{ color: 'var(--muted)' }}>
            Colours are read from the photo automatically, with or without AI
          </span>
        </button>

        <Field label="Category">
          <select className="select" value={category} onChange={(e) => setCategory(e.target.value)}>
            {(meta.categories || []).map((c) => (
              <option key={c} value={c}>{titleCase(c)}</option>
            ))}
          </select>
        </Field>

        <label className="flex items-center gap-2.5">
          <input type="checkbox" checked={analyse} onChange={(e) => setAnalyse(e.target.checked)}
                 className="h-4 w-4 accent-current" style={{ accentColor: 'var(--accent)' }} />
          <span className="text-sm">
            Auto-tag with AI
            <span className="block text-xs" style={{ color: 'var(--muted)' }}>
              Skipped automatically when no AI provider is set up
            </span>
          </span>
        </label>

        {queue.length > 0 && (
          <div className="card divide-y" style={{ borderColor: 'var(--border)' }}>
            {queue.map((q, i) => (
              <div key={i} className="flex items-center gap-3 px-3 py-2">
                <img src={URL.createObjectURL(q.file)} alt="" className="h-12 w-12 rounded-lg object-cover" />
                <input
                  className="input flex-1" value={q.name} placeholder="Item name" disabled={busy}
                  onChange={(e) => setQueue((qq) => qq.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))}
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

export default function Wardrobe() {
  const meta = useMeta()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const q = useDebounced(search, 280)
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState('')
  const [sort, setSort] = useLocalState('outfits.sort', 'recent')
  const [uploadOpen, setUploadOpen] = useState(false)

  const load = useCallback(
    () => api.items({ q, category, status, sort }),
    [q, category, status, sort]
  )
  const { data, loading, error, reload } = useAsync(load, [q, category, status, sort])
  const items = data?.items || []

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--muted)' }}>
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
          {Array.from({ length: 8 }).map((_, i) => <div key={i} className="skeleton aspect-[3/4] rounded-2xl" />)}
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

      <UploadSheet
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        onDone={(created) => {
          reload(true)
          if (created.length === 1) navigate(`/wardrobe/${created[0].id}`)
        }}
      />
    </div>
  )
}
