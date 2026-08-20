import { useMemo, useState } from 'react'
import { useMeta } from '../App.jsx'
import { ItemPhoto } from './ItemCard.jsx'
import { Chip, Icon } from './ui.jsx'

/**
 * The item chooser: picked strip, category chips, search, grid.
 *
 * One component, because the outfit builder and the wear editor grew separate
 * pickers that behaved differently — one filtered by layer, the other only by
 * search, and only one showed what was already picked. Categories are the words
 * the wearer actually filed things under, so they are the filter.
 */
export default function ItemPicker({ items = [], picked = [], onToggle, loading = false }) {
  const meta = useMeta()
  const [category, setCategory] = useState('')
  const [query, setQuery] = useState('')

  // Only categories with something in them, with counts — same rule as the
  // wardrobe filter rail.
  const cats = useMemo(() => {
    const counts = new Map()
    for (const item of items) {
      const key = item.category
      if (!key) continue
      counts.set(key, (counts.get(key) || 0) + 1)
    }
    return [...counts.entries()]
      .map(([key, count]) => ({
        key, count, label: meta.category_labels?.[key] || key,
      }))
      .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label))
  }, [items, meta.category_labels])

  const needle = query.trim().toLowerCase()
  const shown = items.filter((i) => {
    if (category && i.category !== category) return false
    if (!needle) return true
    return `${i.name} ${i.brand || ''} ${i.subcategory || ''}`
      .toLowerCase().includes(needle)
  })
  const chosen = items.filter((i) => picked.includes(i.id))

  return (
    <div className="space-y-3">
      {chosen.length > 0 && (
        <div className="card px-3 py-3">
          <p className="label">Picked · {chosen.length}</p>
          <div className="scroll-x mt-2 flex gap-2">
            {chosen.map((i) => (
              <button key={i.id} type="button" onClick={() => onToggle(i.id)}
                      className="relative w-16 shrink-0" title={`Remove ${i.name}`}>
                <div className="aspect-[3/4] overflow-hidden rounded-lg">
                  <ItemPhoto item={i} rounded="rounded-lg" />
                </div>
                <span className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-white ring-2"
                      style={{ background: 'var(--bad)', '--tw-ring-color': 'var(--surface)' }}>
                  <Icon name="close" size={12} />
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      <input className="input" placeholder="Search name, brand or type…"
             value={query} onChange={(e) => setQuery(e.target.value)} />

      <div className="rail">
        <Chip active={!category} onClick={() => setCategory('')}>All</Chip>
        {cats.map((c) => (
          <Chip key={c.key} active={category === c.key}
                onClick={() => setCategory(category === c.key ? '' : c.key)}>
            {c.label}
            <span className="tabular-nums" style={{ opacity: 0.6 }}>{c.count}</span>
          </Chip>
        ))}
      </div>

      {loading ? (
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) =>
            <div key={i} className="skeleton aspect-[3/4] rounded-lg" />)}
        </div>
      ) : (
        <div className="grid max-h-80 grid-cols-3 gap-2 overflow-y-auto sm:grid-cols-5">
          {shown.map((i) => {
            const on = picked.includes(i.id)
            return (
              <button key={i.id} type="button" onClick={() => onToggle(i.id)}
                      className="card overflow-hidden text-left"
                      style={on ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 2px var(--accent)' } : undefined}>
                <div className="relative aspect-[3/4] overflow-hidden">
                  <ItemPhoto item={i} rounded="" />
                  {on && (
                    <span className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-white ring-2"
                          style={{ background: 'var(--accent)', '--tw-ring-color': 'var(--surface)' }}>
                      <Icon name="check" size={12} />
                    </span>
                  )}
                </div>
                <p className="truncate px-1.5 py-1 text-2xs font-medium">{i.name}</p>
              </button>
            )
          })}
          {!shown.length && (
            <p className="col-span-full py-6 text-center text-sm"
               style={{ color: 'var(--muted)' }}>
              Nothing matches.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
