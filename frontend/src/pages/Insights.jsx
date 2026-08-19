import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import { EmptyState, ErrorNote, Icon, Section, Stat, titleCase } from '../components/ui.jsx'

const SWATCH = {
  black: '#1c1c1c', charcoal: '#36363a', grey: '#808080', silver: '#c0c0c0',
  white: '#f4f4f2', cream: '#f5eedc', beige: '#dec8a5', tan: '#c49a6c',
  brown: '#6e4a2e', burgundy: '#6e1e32', red: '#c82828', orange: '#e67e22',
  mustard: '#d6ae2c', yellow: '#f0dc3c', olive: '#6e743c', green: '#3c9650',
  teal: '#288282', navy: '#1a284e', blue: '#3464be', denim: '#5a78a0',
  'light blue': '#96bee1', purple: '#7846a0', pink: '#e696b4', khaki: '#a0966e',
}

function BarList({ rows, valueKey = 'count', labelKey = 'label', colourOf, format }) {
  const max = Math.max(...rows.map((r) => r[valueKey] || 0), 1)
  return (
    <div className="space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="w-24 shrink-0 truncate text-xs font-medium">{titleCase(r[labelKey])}</span>
          <div className="h-5 flex-1 overflow-hidden rounded" style={{ background: 'var(--surface-2)' }}>
            <div
              className="h-full rounded transition-all"
              style={{
                width: `${Math.max(3, (r[valueKey] / max) * 100)}%`,
                background: colourOf ? colourOf(r) : 'var(--accent)',
                // White and cream bars would vanish into the card without an edge.
                boxShadow: colourOf ? 'inset 0 0 0 1px rgb(0 0 0 / 0.18)' : undefined,
              }}
            />
          </div>
          <span className="w-10 shrink-0 text-right text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
            {format ? format(r) : r[valueKey]}
          </span>
        </div>
      ))}
    </div>
  )
}

function Timeline({ points }) {
  if (!points?.length) {
    return <p className="text-sm" style={{ color: 'var(--muted)' }}>No wears logged yet.</p>
  }
  const max = Math.max(...points.map((p) => p.count), 1)
  const w = 100 / points.length
  return (
    <div>
      <svg viewBox="0 0 100 34" preserveAspectRatio="none" className="h-24 w-full" role="img"
           aria-label="Wears logged over time">
        {points.map((p, i) => {
          const h = (p.count / max) * 30
          return (
            <rect
              key={p.worn_on} x={i * w + w * 0.15} y={32 - h} width={w * 0.7} height={Math.max(h, 0.6)}
              rx={w * 0.2} fill="var(--accent)"
            >
              <title>
                {`${p.worn_on}: ${p.count} item${p.count === 1 ? '' : 's'}`}
                {p.outfits ? ` across ${p.outfits} outfit${p.outfits === 1 ? '' : 's'}` : ''}
              </title>
            </rect>
          )
        })}
      </svg>
      <div className="flex justify-between text-[0.7rem]" style={{ color: 'var(--muted)' }}>
        <span>{points[0].worn_on}</span>
        <span>{points[points.length - 1].worn_on}</span>
      </div>
    </div>
  )
}

function ItemStrip({ items, valueOf, emptyNote }) {
  if (!items?.length) {
    return <p className="text-sm" style={{ color: 'var(--muted)' }}>{emptyNote}</p>
  }
  return (
    <div className="scroll-x flex gap-2.5">
      {items.map((i) => (
        <Link key={i.id} to={`/wardrobe/${i.id}`} className="w-20 shrink-0">
          <div className="aspect-[3/4] overflow-hidden rounded-lg">
            <ItemPhoto item={i} rounded="rounded-lg" />
          </div>
          <p className="mt-1 truncate text-[0.7rem] font-medium">{i.name}</p>
          {valueOf && (
            <p className="truncate text-[0.68rem] tabular-nums" style={{ color: 'var(--muted)' }}>
              {valueOf(i)}
            </p>
          )}
        </Link>
      ))}
    </div>
  )
}

export default function Insights() {
  const { data, loading, error, reload } = useAsync(() => api.analytics(), [])

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} className="skeleton h-20 rounded-2xl" />)}
        </div>
        <div className="skeleton h-56 rounded-2xl" />
      </div>
    )
  }
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!data) return null

  const s = data.summary
  if (!s.total_items) {
    return (
      <EmptyState
        icon="chart" title="Nothing to analyse yet"
        hint="Add a few items and log what you wear. The interesting numbers need a couple of weeks of history."
        action={<Link to="/wardrobe" className="btn btn-primary"><Icon name="plus" size={15} /> Add items</Link>}
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Items" value={s.active_items} sub={`${s.total_items} including archived`} />
        <Stat label="Total wears" value={s.total_wears} sub={`${s.wear_logs} days logged`} />
        <Stat label="Needs washing" value={s.dirty_items} tone={s.dirty_items ? 'bad' : undefined}
              sub={`${s.wash_loads} loads run`} />
        <Stat label="Outfits saved" value={s.outfits}
              sub={`${s.wash_loads} wash loads run`} />
      </div>

      <Section title="Items worn per day, last 12 weeks">
        <div className="card px-4 py-4"><Timeline points={data.timeline} /></div>
      </Section>

      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Colours you own">
          <div className="card px-4 py-4">
            {data.colours.length ? (
              <BarList
                rows={data.colours.map((c) => ({ ...c, label: c.colour }))}
                colourOf={(r) => SWATCH[String(r.colour).toLowerCase()] || 'var(--accent)'}
                format={(r) => `${r.count}`}
              />
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>No colours recorded yet.</p>
            )}
          </div>
        </Section>

        <Section title="What the wardrobe is made of">
          <div className="card px-4 py-4">
            <BarList rows={s.by_category.map((c) => ({ ...c, label: c.category }))} />
          </div>
        </Section>
      </div>

      <Section title="Worn most">
        <div className="card px-4 py-4">
          <ItemStrip
            items={data.most_worn}
            valueOf={(i) => `${i.total_wears} wear${i.total_wears === 1 ? '' : 's'}`}
            emptyNote="Log a few outfits to see this."
          />
        </div>
      </Section>

      <Section title="Owned but ignored">
        <div className="card px-4 py-4">
          <p className="mb-3 text-xs" style={{ color: 'var(--muted)' }}>
            Not worn in the last 90 days. The honest part of the wardrobe.
          </p>
          <ItemStrip
            items={data.neglected}
            valueOf={(i) => (i.last_worn ? `last ${i.last_worn}` : 'never worn')}
            emptyNote="Everything has had an outing recently."
          />
        </div>
      </Section>

      <Section title="Pairs you keep repeating">
        <div className="card px-4 py-4">
          {data.combinations.length ? (
            <div className="space-y-3">
              {data.combinations.map((c, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="flex gap-1.5">
                    {c.items.map((it) => (
                      <Link key={it.id} to={`/wardrobe/${it.id}`} className="h-14 w-11 overflow-hidden rounded-lg">
                        <ItemPhoto item={it} rounded="rounded-lg" />
                      </Link>
                    ))}
                  </div>
                  <p className="min-w-0 flex-1 truncate text-sm">
                    {c.items.map((it) => it.name).join('  +  ')}
                  </p>
                  <span className="shrink-0 text-xs font-semibold tabular-nums" style={{ color: 'var(--muted)' }}>
                    {c.count}×
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm" style={{ color: 'var(--muted)' }}>
              Wear the same two things together twice and they will show up here.
            </p>
          )}
        </div>
      </Section>

      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Laundry">
          <div className="card px-4 py-4">
            {data.wash.by_temp.length ? (
              <BarList rows={data.wash.by_temp.map((t) => ({ label: `${t.temp_c}°C`, count: t.loads }))}
                       format={(r) => `${r.count} load${r.count === 1 ? '' : 's'}`} />
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>No washes recorded yet.</p>
            )}
            {data.wash.most_washed.length > 0 && (
              <>
                <p className="mb-2 mt-4 label">Washed most often</p>
                <ItemStrip items={data.wash.most_washed} valueOf={(i) => `${i.wash_count}×`} emptyNote="" />
              </>
            )}
          </div>
        </Section>

        <Section title="How you feel the cold">
          <div className="card px-4 py-4">
            {data.comfort.total ? (
              <>
                <p className="text-3xl font-bold tabular-nums"
                   style={{ color: data.comfort.offset < 0 ? 'var(--warn)' : data.comfort.offset > 0 ? 'var(--accent)' : 'var(--good)' }}>
                  {data.comfort.offset > 0 ? '+' : ''}{data.comfort.offset}
                </p>
                <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>
                  {data.comfort.offset < -0.2
                    ? 'You run warm, so suggestions come out lighter than the default.'
                    : data.comfort.offset > 0.2
                      ? 'You feel the cold, so suggestions add a layer.'
                      : 'You are close to the default. Keep rating wears to sharpen it.'}
                </p>
                <div className="mt-3 space-y-1.5">
                  {data.comfort.counts.map((c) => (
                    <div key={c.verdict} className="flex justify-between text-xs">
                      <span style={{ color: 'var(--muted)' }}>{titleCase(c.verdict)}</span>
                      <span className="font-semibold tabular-nums">{c.count}</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                Rate a few outfits “too hot” or “too cold” after wearing them and the recommender
                starts calibrating to you rather than an average body.
              </p>
            )}
          </div>
        </Section>
      </div>

      {data.gaps.length > 0 && (
        <Section title="Gaps limiting suggestions">
          <div className="card px-4 py-4">
            <div className="space-y-2">
              {data.gaps.map((g) => (
                <div key={g.category} className="flex items-center justify-between text-sm">
                  <span className="font-medium">{titleCase(g.category)}</span>
                  <span style={{ color: 'var(--muted)' }}>
                    {g.have} of {g.suggested} suggested
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Section>
      )}
    </div>
  )
}
