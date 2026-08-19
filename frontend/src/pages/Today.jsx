import { useCallback, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAsync, useLocalState } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import {
  Chip, EmptyState, ErrorNote, Icon, Section, Spinner, WeatherIcon, useToast,
} from '../components/ui.jsx'

const OCCASIONS = ['everyday', 'work', 'smart', 'sport', 'date', 'formal', 'lounge']
const DAYS = ['Today', 'Tomorrow', 'In 2 days', 'In 3 days']

const WARNING_COLOUR = { yellow: '#d9a054', amber: '#e08b2e', red: '#c0392b' }

function Warnings({ warnings }) {
  const [open, setOpen] = useState(false)
  const list = warnings?.warnings || []
  if (!warnings?.available || !list.length) return null

  const worst = WARNING_COLOUR[warnings.highest] || WARNING_COLOUR.yellow
  const shown = open ? list : list.slice(0, 2)

  return (
    <div className="card overflow-hidden" style={{ borderColor: worst }}>
      <div className="flex items-center gap-2 px-4 pt-3">
        <span style={{ color: worst }}><Icon name="storm" size={18} /></span>
        <p className="text-sm font-bold">
          {list.length} Met Office warning{list.length === 1 ? '' : 's'} today
        </p>
        <span className="ml-auto truncate text-xs" style={{ color: 'var(--muted)' }}>
          {warnings.derived_region?.label || warnings.region_label}
        </span>
      </div>
      <div className="space-y-1.5 px-4 py-3">
        {shown.map((w, i) => (
          <a key={i} href={w.link} target="_blank" rel="noreferrer"
             className="flex items-start gap-2 text-sm">
            <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full"
                  style={{ background: WARNING_COLOUR[w.level] || worst }} />
            <span className="min-w-0">
              <span className="block font-medium">
                {w.hazard ? `${w.hazard[0].toUpperCase()}${w.hazard.slice(1)}` : w.title}
                {w.active_now && (
                  <span className="ml-1.5 text-[0.65rem] font-bold uppercase tracking-wide"
                        style={{ color: WARNING_COLOUR[w.level] || worst }}>
                    in force
                  </span>
                )}
              </span>
              {w.when && (
                <span className="block text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
                  {w.when}
                </span>
              )}
              {w.counties && (
                <span className="block text-xs" style={{ color: 'var(--muted)' }}>
                  {w.counties}
                </span>
              )}
            </span>
          </a>
        ))}
        {list.length > 2 && (
          <button className="btn btn-ghost !px-0 text-xs" onClick={() => setOpen(!open)}>
            {open ? 'Show fewer' : `Show ${list.length - 2} more`}
          </button>
        )}
      </div>
    </div>
  )
}

function WeatherCard({ weather, onRefresh, refreshing }) {
  if (!weather) return <div className="skeleton h-32 rounded-2xl" />
  if (!weather.available) {
    return (
      <div className="card px-4 py-4">
        <p className="text-sm font-semibold">Weather unavailable</p>
        <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
          {weather.error || 'Could not reach Open-Meteo.'} Suggestions still work, they just will not
          be scored on temperature.
        </p>
        <button className="btn mt-3" onClick={onRefresh}><Icon name="refresh" size={15} /> Retry</button>
      </div>
    )
  }
  const c = weather.current || {}
  const t = weather.today || {}
  return (
    <div className="card overflow-hidden">
      <div className="flex items-start gap-4 px-4 py-4">
        <div style={{ color: 'var(--accent)' }}>
          <WeatherIcon group={c.condition?.group} size={44} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-2">
            <span className="text-3xl font-bold tabular-nums">{Math.round(c.temp_c)}°</span>
            <span className="text-sm" style={{ color: 'var(--muted)' }}>
              feels like {Math.round(c.apparent_c)}°
            </span>
          </div>
          <p className="mt-0.5 truncate text-sm font-medium">{c.condition?.label}</p>
          <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
            {weather.location} · {Math.round(t.min_c)}° to {Math.round(t.max_c)}°
            {t.rain_chance != null && ` · ${t.rain_chance}% rain`}
            {c.wind_kph != null && ` · ${Math.round(c.wind_kph)} km/h wind`}
          </p>
          <p className="text-[0.68rem]" style={{ color: 'var(--muted)' }}>
            {weather.provider_label}
            {weather.stale && ' · showing last known forecast'}
          </p>
        </div>
        <button className="btn btn-ghost !p-1.5" onClick={onRefresh} disabled={refreshing} aria-label="Refresh weather">
          {refreshing ? <Spinner size={16} /> : <Icon name="refresh" size={16} />}
        </button>
      </div>
      {weather.daily?.length > 1 && (
        <div className="scroll-x flex gap-2 border-t px-4 py-3" style={{ borderColor: 'var(--border)' }}>
          {weather.daily.slice(1).map((d) => (
            <div key={d.date} className="flex min-w-[4.5rem] flex-col items-center gap-1 rounded-xl px-2 py-2"
                 style={{ background: 'var(--surface-2)' }}>
              <span className="text-[0.68rem] font-semibold" style={{ color: 'var(--muted)' }}>
                {new Date(d.date).toLocaleDateString(undefined, { weekday: 'short' })}
              </span>
              <span style={{ color: 'var(--accent)' }}><WeatherIcon group={d.condition?.group} size={18} /></span>
              <span className="text-xs font-semibold tabular-nums">
                {Math.round(d.max_c)}°/{Math.round(d.min_c)}°
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function SuggestionCard({ suggestion, index, onWear, busy }) {
  const pct = Math.round(suggestion.score * 100)
  return (
    <div className="card fade-up overflow-hidden" style={{ animationDelay: `${index * 60}ms` }}>
      <div className="flex items-center justify-between gap-2 px-4 pt-3.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold"
                style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
            {index + 1}
          </span>
          <span className="text-sm font-semibold">
            {index === 0 ? 'Best match' : `Option ${index + 1}`}
          </span>
        </div>
        <span className="text-xs font-bold tabular-nums" style={{ color: 'var(--muted)' }}>{pct}%</span>
      </div>

      <div className="scroll-x flex gap-2 px-4 py-3">
        {suggestion.items.map((item) => (
          <Link key={item.id} to={`/wardrobe/${item.id}`}
                className="w-24 shrink-0" title={item.name}>
            <div className="aspect-[3/4] overflow-hidden rounded-lg">
              <ItemPhoto item={item} rounded="rounded-lg" />
            </div>
            <p className="mt-1 truncate text-[0.7rem] font-medium">{item.name}</p>
          </Link>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5 px-4">
        {suggestion.reasons.map((r, i) => (
          <span key={i} className="rounded-full px-2 py-0.5 text-[0.68rem] font-medium"
                style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
            {r}
          </span>
        ))}
      </div>

      <div className="flex items-center gap-2 px-4 py-3">
        <button className="btn btn-primary flex-1" onClick={() => onWear(suggestion)} disabled={busy}>
          {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Wear this
        </button>
        <span className="text-[0.7rem] tabular-nums" style={{ color: 'var(--muted)' }}>
          warmth {suggestion.warmth}
          {suggestion.target_warmth != null && ` / ${suggestion.target_warmth}`}
        </span>
      </div>
    </div>
  )
}

export default function Today() {
  const toast = useToast()
  const [occasion, setOccasion] = useLocalState('outfits.occasion', 'everyday')
  const [dayOffset, setDayOffset] = useState(0)
  const [excludeDirty, setExcludeDirty] = useLocalState('outfits.excludeDirty', true)
  const [useAI, setUseAI] = useLocalState('outfits.useAI', false)
  const [wearing, setWearing] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  const weather = useAsync(() => api.weather(), [])
  const load = useCallback(
    () => api.suggest({ occasion, count: 3, exclude_dirty: excludeDirty, day_offset: dayOffset, use_ai: useAI }),
    [occasion, excludeDirty, dayOffset, useAI]
  )
  const suggestions = useAsync(load, [occasion, excludeDirty, dayOffset, useAI])

  const refreshWeather = async () => {
    setRefreshing(true)
    await api.weather(true).catch(() => {})
    await weather.reload(true)
    await suggestions.reload(true)
    setRefreshing(false)
  }

  const wear = async (suggestion) => {
    setWearing(suggestion.item_ids.join(','))
    try {
      const res = await api.logWear({ item_ids: suggestion.item_ids, occasion })
      const dirty = res.now_needing_wash?.length
      toast(dirty ? `Logged. ${dirty} item${dirty === 1 ? '' : 's'} now need washing.` : 'Logged today’s outfit.', 'success')
      suggestions.reload(true)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setWearing(null)
    }
  }

  const data = suggestions.data

  return (
    <div className="space-y-6">
      <WeatherCard weather={weather.data} onRefresh={refreshWeather} refreshing={refreshing} />
      <Warnings warnings={weather.data?.warnings} />

      <div className="space-y-3">
        <div className="scroll-x flex gap-2">
          {DAYS.map((label, i) => (
            <Chip key={label} active={dayOffset === i} onClick={() => setDayOffset(i)}>{label}</Chip>
          ))}
        </div>
        <div className="scroll-x flex gap-2">
          {OCCASIONS.map((o) => (
            <Chip key={o} active={occasion === o} onClick={() => setOccasion(o)}>
              {o[0].toUpperCase() + o.slice(1)}
            </Chip>
          ))}
        </div>
        <div className="flex flex-wrap gap-2">
          <Chip active={excludeDirty} onClick={() => setExcludeDirty(!excludeDirty)}>
            <Icon name="drop" size={13} /> {excludeDirty ? 'Hiding dirty items' : 'Including dirty items'}
          </Chip>
          <Chip active={useAI} onClick={() => setUseAI(!useAI)}>
            <Icon name="sparkle" size={13} /> AI stylist {useAI ? 'on' : 'off'}
          </Chip>
        </div>
      </div>

      <Section
        title="Suggestions"
        action={
          <button className="btn btn-ghost" onClick={() => suggestions.reload()} disabled={suggestions.loading}>
            {suggestions.loading ? <Spinner size={15} /> : <Icon name="refresh" size={15} />} Reshuffle
          </button>
        }
      >
        <ErrorNote error={suggestions.error} onRetry={suggestions.reload} />

        {suggestions.loading && !data && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => <div key={i} className="skeleton h-56 rounded-2xl" />)}
          </div>
        )}

        {data?.missing_categories?.length > 0 && (
          <EmptyState
            icon="hanger"
            title="Not enough in the wardrobe yet"
            hint={data.message}
            action={<Link to="/wardrobe" className="btn btn-primary"><Icon name="plus" size={15} /> Add items</Link>}
          />
        )}

        {data?.suggestions?.map((s, i) => (
          <SuggestionCard
            key={s.item_ids.join('-')} suggestion={s} index={i}
            onWear={wear} busy={wearing === s.item_ids.join(',')}
          />
        ))}

        {data && !data.suggestions?.length && !data.missing_categories?.length && (
          <EmptyState
            icon="drop"
            title="Everything is in the wash"
            hint="Nothing clean matches right now. Turn off “Hiding dirty items” to see options anyway."
          />
        )}
      </Section>

      {data?.ai && (
        <Section title="AI stylist">
          {data.ai.available ? (
            <div className="card px-4 py-4">
              <p className="text-sm font-semibold">{data.ai.name || 'Stylist pick'}</p>
              <div className="scroll-x mt-3 flex gap-2">
                {data.ai.items.map((item) => (
                  <Link key={item.id} to={`/wardrobe/${item.id}`} className="w-24 shrink-0">
                    <div className="aspect-[3/4] overflow-hidden rounded-lg"><ItemPhoto item={item} rounded="rounded-lg" /></div>
                    <p className="mt-1 truncate text-[0.7rem]">{item.name}</p>
                  </Link>
                ))}
              </div>
              <p className="mt-3 text-sm" style={{ color: 'var(--muted)' }}>{data.ai.reasoning}</p>
              <button className="btn btn-primary mt-3"
                      onClick={() => wear({ item_ids: data.ai.items.map((i) => i.id) })}>
                <Icon name="check" size={15} /> Wear this
              </button>
            </div>
          ) : (
            <div className="card px-4 py-3 text-sm" style={{ color: 'var(--muted)' }}>
              {data.ai.reason}. <Link to="/settings" className="font-semibold underline">Set up AI</Link>
            </div>
          )}
        </Section>
      )}

      {data?.personal_offset != null && Math.abs(data.personal_offset) > 0.2 && (
        <p className="px-1 text-xs" style={{ color: 'var(--muted)' }}>
          Calibrated to you: {data.personal_offset < 0 ? 'you run warm' : 'you feel the cold'}, so
          suggestions are {data.personal_offset < 0 ? 'lighter' : 'warmer'} than the default by{' '}
          {Math.abs(data.personal_offset).toFixed(1)} warmth points.
        </p>
      )}
    </div>
  )
}
