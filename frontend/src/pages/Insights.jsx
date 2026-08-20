import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import {
  EmptyNote, EmptyState, ErrorNote, Icon, PageHeader, Section, Stat, titleCase,
} from '../components/ui.jsx'

function BarList({ rows, valueKey = 'count', labelKey = 'label', colourOf, format }) {
  const max = Math.max(...rows.map((r) => r[valueKey] || 0), 1)
  return (
    <div className="space-y-2">
      {rows.map((r, i) => (
        <div key={i} className="flex items-center gap-3">
          <span className="w-20 shrink-0 truncate text-xs font-medium sm:w-24">{titleCase(r[labelKey])}</span>
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
          <span className="w-9 shrink-0 text-right text-xs tabular-nums sm:w-10" style={{ color: 'var(--muted)' }}>
            {format ? format(r) : r[valueKey]}
          </span>
        </div>
      ))}
    </div>
  )
}

function Timeline({ points }) {
  if (!points?.length) {
    return <EmptyNote>No wears logged yet.</EmptyNote>
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
      <div className="flex justify-between text-2xs" style={{ color: 'var(--muted)' }}>
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
          <p className="mt-1 truncate text-2xs font-medium">{i.name}</p>
          {valueOf && (
            <p className="truncate text-2xs tabular-nums" style={{ color: 'var(--muted)' }}>
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
        action={<Link to="/wardrobe" className="btn btn-primary"><Icon name="plus" size={16} /> Add items</Link>}
      />
    )
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Insights"
        description="What you actually wear, against what you actually own."
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Stat label="Items" value={s.active_items}
              sub={s.total_items > s.active_items
                ? `${s.total_items - s.active_items} archived`
                : 'all in use'} />
        <Stat label="Total wears" value={s.total_wears} sub={`${s.wear_logs} days logged`} />
        <Stat label="Outfits saved" value={s.outfits}
              sub={s.outfits ? 'ready to wear' : 'none built yet'} />
        <Stat label="Categories" value={s.by_category.length}
              sub="in use" />
      </div>

      <Section title="Items worn per day, last 12 weeks">
        <div className="card px-4 py-4"><Timeline points={data.timeline} /></div>
      </Section>

      <div className="grid gap-5 md:grid-cols-2">
        <Section title="Colours you own">
          <div className="card px-4 py-4">
            {data.colours.length ? (
              <BarList
                // The swatch comes with the row now. Insights used to keep its
                // own copy of the colour table, which quietly fell behind the
                // one the rest of the app names colours with.
                rows={data.colours.map((c) => ({ ...c, label: c.colour }))}
                colourOf={(r) => r.hex || 'var(--surface-2)'}
                format={(r) => `${r.count}`}
              />
            ) : (
              <EmptyNote>No colours recorded yet.</EmptyNote>
            )}
            {data.colours.some((c) => !c.known) && (
              <p className="mt-3 text-xs" style={{ color: 'var(--warn)' }}>
                Some colours are written in words the app does not recognise, so they are
                not matched in an outfit. Open the item and
                pick a colour from the list to fix it.
              </p>
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

      {data.taste && (
        <Section title="Taste">
          <div className="card px-4 py-4">
            {data.taste.total ? (
              <>
                <p className="text-sm">
                  <span className="font-bold tabular-nums">{data.taste.likes}</span> liked ·{' '}
                  <span className="font-bold tabular-nums">{data.taste.dislikes}</span> disliked
                  {' — '}
                  {data.taste.learning
                    ? 'the scoring is adapting to you.'
                    : `${data.taste.needed} more and the scoring starts adapting.`}
                </p>
                {(data.taste.favourites.length > 0 || data.taste.avoided.length > 0) && (
                  <div className="mt-3 grid gap-4 sm:grid-cols-2">
                    {data.taste.favourites.length > 0 && (
                      <div>
                        <p className="label mb-1.5">Pulled towards</p>
                        {data.taste.favourites.map((f) => (
                          <p key={f.id} className="truncate text-xs">
                            <Link to={`/wardrobe/${f.id}`} style={{ color: 'var(--good)' }}>
                              {f.name}
                            </Link>
                          </p>
                        ))}
                      </div>
                    )}
                    {data.taste.avoided.length > 0 && (
                      <div>
                        <p className="label mb-1.5">Steered away from</p>
                        {data.taste.avoided.map((f) => (
                          <p key={f.id} className="truncate text-xs">
                            <Link to={`/wardrobe/${f.id}`} style={{ color: 'var(--bad)' }}>
                              {f.name}
                            </Link>
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                Thumb suggestions up or down on the Today page and the scoring learns what
                you actually like, not what an average person would.
              </p>
            )}
          </div>
        </Section>
      )}

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
