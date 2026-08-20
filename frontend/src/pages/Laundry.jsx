import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import {
  EmptyNote, EmptyState, ErrorNote, Icon, PageHeader, Section, Spinner, titleCase,
  useToast,
} from '../components/ui.jsx'

function Load({ load, onWash, busy }) {
  const [selected, setSelected] = useState(() => load.items.map((i) => i.id))
  useEffect(() => { setSelected(load.items.map((i) => i.id)) }, [load.key, load.items.length])

  const toggle = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-4 pt-3.5">
        <div>
          <p className="font-semibold">{load.label}</p>
          <p className="text-xs" style={{ color: 'var(--muted)' }}>
            {load.count} item{load.count === 1 ? '' : 's'}
            {load.temp_c ? ` · ${load.temp_c}°C` : ''}
            {!load.machine_wash ? ' · not for the machine' : ''}
          </p>
        </div>
        <button
          className="btn btn-ghost text-xs"
          onClick={() => setSelected(selected.length === load.items.length ? [] : load.items.map((i) => i.id))}
        >
          {selected.length === load.items.length ? 'Clear' : 'All'}
        </button>
      </div>

      {/* Tight columns so a one-item load does not render a giant photo. */}
      <div className="grid grid-cols-3 gap-2 px-4 py-3 sm:grid-cols-6 lg:grid-cols-9">
        {load.items.map((i) => {
          const on = selected.includes(i.id)
          return (
            <button key={i.id} onClick={() => toggle(i.id)} className="text-left"
                    title={i.name}>
              <div className="relative aspect-[3/4] overflow-hidden rounded-lg"
                   style={{ opacity: on ? 1 : 0.35 }}>
                <ItemPhoto item={i} rounded="rounded-lg" />
                {on && (
                  <span className="absolute right-1 top-1 flex h-5 w-5 items-center justify-center rounded-full text-white"
                        style={{ background: 'var(--accent)' }}><Icon name="check" size={12} /></span>
                )}
              </div>
              <p className="mt-1 truncate text-2xs font-medium">{i.name}</p>
            </button>
          )
        })}
      </div>

      <div className="px-4 pb-3">
        <button
          className="btn btn-primary w-full"
          disabled={busy || !selected.length}
          onClick={() => onWash(load, selected)}
        >
          {busy ? <Spinner size={16} /> : <Icon name="drop" size={16} />}
          {load.machine_wash ? `Washed ${selected.length}` : `Cleaned ${selected.length}`}
        </button>
      </div>
    </div>
  )
}

export default function Laundry() {
  const toast = useToast()
  const plan = useAsync(() => api.laundry(), [])
  const history = useAsync(() => api.washHistory(), [])
  const [busy, setBusy] = useState(null)

  const runWash = async (load, itemIds) => {
    setBusy(load.key)
    try {
      await api.wash({
        item_ids: itemIds,
        program: load.group,
        temp_c: load.temp_c,
        notes: load.label,
      })
      toast(`${itemIds.length} item${itemIds.length === 1 ? '' : 's'} back in the wardrobe, clean.`, 'success')
      plan.reload(true)
      history.reload(true)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setBusy(null)
    }
  }

  const data = plan.data
  const loads = data?.loads || []
  const dueSoon = data?.due_soon || []

  return (
    <div className="space-y-6">
      <PageHeader
        title="Laundry"
        description="What is dirty, grouped into loads that can go in together."
      />
      <Section
        title="Ready to wash"
        action={
          <button className="btn btn-ghost" onClick={() => plan.reload()} disabled={plan.loading}>
            {plan.loading ? <Spinner size={16} /> : <Icon name="refresh" size={16} />} Refresh
          </button>
        }
      >
        <ErrorNote error={plan.error} onRetry={plan.reload} />

        {plan.loading && !data && <div className="skeleton h-48 rounded-2xl" />}

        {data && !loads.length && (
          <EmptyState
            icon="check"
            title="Nothing needs washing"
            hint="Items land here once they pass their own wear threshold — socks after one wear, a coat after twenty-five."
          />
        )}

        {loads.length > 0 && (
          <p className="text-xs" style={{ color: 'var(--muted)' }}>
            {data.dirty_count} item{data.dirty_count === 1 ? '' : 's'} across {loads.length} load
            {loads.length === 1 ? '' : 's'}, grouped so nothing gets ruined by sharing a drum.
          </p>
        )}

        <div className="space-y-3">
          {loads.map((load) => (
            <Load key={load.key} load={load} onWash={runWash} busy={busy === load.key} />
          ))}
        </div>
      </Section>

      {dueSoon.length > 0 && (
        <Section title="One more wear left">
          <div className="card divide-y" style={{ borderColor: 'var(--border)' }}>
            {dueSoon.map((i) => (
              <div key={i.id} className="flex items-center gap-3 px-3.5 py-2.5">
                <div className="h-10 w-10 shrink-0 overflow-hidden rounded-lg">
                  <ItemPhoto item={i} rounded="rounded-lg" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{i.name}</p>
                  <p className="text-xs" style={{ color: 'var(--muted)' }}>
                    {i.wears_since_wash}/{i.wash_threshold} wears
                  </p>
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Wash history">
        {history.data?.batches?.length ? (
          <div className="space-y-2">
            {history.data.batches.slice(0, 12).map((b) => (
              <div key={b.id} className="card flex items-center gap-3 px-3.5 py-2.5">
                <span className="rounded-full p-2" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
                  <Icon name="drop" size={16} />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {b.count} item{b.count === 1 ? '' : 's'}
                    {b.temp_c ? ` at ${b.temp_c}°C` : ''}
                  </p>
                  <p className="truncate text-xs" style={{ color: 'var(--muted)' }}>
                    {b.washed_on}{b.notes ? ` · ${b.notes}` : ''}
                  </p>
                </div>
                <div className="scroll-x flex gap-1">
                  {b.items.slice(0, 4).map((i) => (
                    <div key={i.id} className="h-8 w-8 shrink-0 overflow-hidden rounded">
                      <ItemPhoto item={i} rounded="rounded" />
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyNote boxed>Nothing washed yet. Loads you run show up here.</EmptyNote>
        )}
      </Section>
    </div>
  )
}
