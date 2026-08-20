import { Link } from 'react-router-dom'
import { Icon, Palette, titleCase } from './ui.jsx'

export function ItemPhoto({ item, className = '', rounded = 'rounded-xl', full = false }) {
  // Grids and strips get the ~400px thumbnail; only the detail view needs the
  // full image. A phone loading twenty full-size photos for a grid is wasteful.
  const url = full
    ? (item.display_url || item.thumb_url)
    : (item.thumb_url || item.display_url)
  if (!url) {
    return (
      <div className={`flex items-center justify-center ${rounded} ${className}`}
           style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
        <Icon name="hanger" size={28} />
      </div>
    )
  }
  // The placeholder sits behind the photo rather than instead of it. Forty-seven
  // lazy thumbnails do not arrive at once, and an empty card for a second reads
  // as a broken one; a hanger reads as a photo on its way.
  return (
    <span className={`relative block h-full w-full ${rounded} overflow-hidden`}
          style={{ background: 'var(--surface-2)' }}>
      <span className="absolute inset-0 flex items-center justify-center"
            style={{ color: 'var(--border)' }} aria-hidden="true">
        <Icon name="hanger" size={28} />
      </span>
      <img
        src={url} alt={item.name} loading="lazy" decoding="async"
        className={`relative h-full w-full object-cover ${rounded} ${className}`}
      />
    </span>
  )
}

export default function ItemCard({ item, selected, onSelect, compact = false }) {
  const selectable = typeof onSelect === 'function'
  const Wrapper = selectable ? 'button' : Link
  const props = selectable
    ? { onClick: () => onSelect(item), type: 'button' }
    : { to: `/wardrobe/${item.id}` }

  return (
    <Wrapper
      {...props}
      className="card card-link group relative block overflow-hidden text-left"
      style={selected ? { borderColor: 'var(--accent)', boxShadow: '0 0 0 2px var(--accent)' } : undefined}
    >
      <div className="relative aspect-[3/4] w-full overflow-hidden" style={{ background: 'var(--surface-2)' }}>
        <ItemPhoto item={item} rounded="" className="transition duration-300 group-hover:scale-[1.03]" />
        {selected && (
          <span className="absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full text-white"
                style={{ background: 'var(--accent)' }}>
            <Icon name="check" size={14} />
          </span>
        )}
      </div>
      <div className={compact ? 'px-2 py-2' : 'px-3 py-2.5'}>
        <p className="truncate text-sm font-semibold">{item.name}</p>
        <div className="mt-1 flex items-center justify-between gap-2">
          <span className="truncate text-xs" style={{ color: 'var(--muted)' }}>
            {item.category_label || titleCase(item.category)}
            {item.brand ? ` · ${item.brand}` : ''}
          </span>
          <Palette palette={item.palette} size={12} max={3} />
        </div>
        {!compact && item.total_wears > 0 && (
          <p className="mt-2 text-2xs tabular-nums" style={{ color: 'var(--muted)' }}>
            worn {item.total_wears}×{item.last_worn ? ` · last ${item.last_worn}` : ''}
          </p>
        )}
      </div>
    </Wrapper>
  )
}

export function ItemGrid({ items, selectedIds, onSelect, compact, empty }) {
  if (!items?.length) return empty || null
  const selected = new Set(selectedIds || [])
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
      {items.map((item) => (
        <ItemCard
          key={item.id}
          item={item}
          compact={compact}
          selected={selected.has(item.id)}
          onSelect={onSelect}
        />
      ))}
    </div>
  )
}

export function ItemRow({ item, right, onClick }) {
  const Wrapper = onClick ? 'button' : Link
  const props = onClick ? { onClick, type: 'button' } : { to: `/wardrobe/${item.id}` }
  return (
    <Wrapper {...props} className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
      <div className="h-12 w-12 shrink-0 overflow-hidden rounded-lg">
        <ItemPhoto item={item} rounded="rounded-lg" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">{item.name}</p>
        <p className="truncate text-xs" style={{ color: 'var(--muted)' }}>
          {item.category_label || titleCase(item.category)}{item.colour_primary ? ` · ${item.colour_primary}` : ''}
        </p>
      </div>
      {right}
    </Wrapper>
  )
}
