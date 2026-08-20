import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync, useLocalState } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import {
  Chip, PageHeader, EmptyState, ErrorNote, Icon, Section, Spinner, WeatherIcon, useToast,
} from '../components/ui.jsx'

const OCCASIONS = ['everyday', 'work', 'smart', 'sport', 'date', 'formal', 'lounge']
const DAYS = ['Today', 'Tomorrow', 'In 2 days', 'In 3 days']

const WARNING_COLOUR = { yellow: '#d9a054', amber: '#e08b2e', red: '#c0392b' }

/* A wash of colour behind the current conditions, so the card reads as the
   day's mood before any number is read. Kept faint enough for both themes. */
const CONDITION_TINT = {
  clear: '#e0982e', cloud: '#8a94a6', rain: '#54779c',
  snow: '#7fa6c0', storm: '#6f61a8', fog: '#98948a',
}

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
                  <span className="ml-1.5 text-2xs font-bold uppercase tracking-wide"
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
          <button className="btn btn-link" onClick={() => setOpen(!open)}>
            {open ? 'Show fewer' : `Show ${list.length - 2} more`}
          </button>
        )}
      </div>
    </div>
  )
}

function Metric({ label, value, sub }) {
  return (
    <div className="rounded-xl px-3 py-2.5"
         style={{ background: 'color-mix(in srgb, var(--surface-2) 72%, transparent)' }}>
      <p className="text-2xs font-semibold uppercase tracking-wide"
         style={{ color: 'var(--muted)' }}>{label}</p>
      <p className="mt-0.5 text-base font-bold tabular-nums leading-none">{value}</p>
      {sub && <p className="mt-1 text-2xs" style={{ color: 'var(--muted)' }}>{sub}</p>}
    </div>
  )
}

function WeatherCard({ weather, onRefresh, refreshing }) {
  if (!weather) return <div className="skeleton h-48 rounded-2xl" />
  if (!weather.available) {
    return (
      <div className="card px-4 py-4 sm:px-5">
        <p className="text-sm font-semibold">Weather unavailable</p>
        <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
          {weather.error || 'Could not reach the forecast service.'} Suggestions still work,
          they just will not be scored on temperature.
        </p>
        <button className="btn mt-3" onClick={onRefresh}>
          <Icon name="refresh" size={16} /> Retry
        </button>
      </div>
    )
  }

  const c = weather.current || {}
  const t = weather.today || {}
  const days = (weather.daily || []).slice(1)
  const tint = CONDITION_TINT[c.condition?.group] || CONDITION_TINT.cloud

  return (
    <div className="card overflow-hidden">
      {/* Conditions on the left, the rest of the week filling the width on the
          right. On a phone the two stack instead. */}
      <div className="grid gap-px lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]"
           style={{ background: 'var(--border)' }}>
        <div className="relative px-4 py-4 sm:px-5 sm:py-5" style={{ background: 'var(--surface)' }}>
          <div className="pointer-events-none absolute inset-0" aria-hidden="true"
               style={{ background:
                 `radial-gradient(36rem 16rem at -4rem -6rem, color-mix(in srgb, ${tint} 14%, transparent), transparent 72%)` }} />
          <div className="relative flex items-start gap-4">
            <span className="mt-1 shrink-0" style={{ color: tint }}>
              <WeatherIcon group={c.condition?.group} size={52} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className="font-display text-6xl font-medium leading-none tabular-nums tracking-tight">
                  {Math.round(c.temp_c)}°
                </span>
                <span className="text-sm font-medium" style={{ color: 'var(--muted)' }}>
                  feels like {Math.round(c.apparent_c)}°
                </span>
              </div>
              <p className="mt-1.5 truncate text-base font-semibold">{c.condition?.label}</p>
              <p className="truncate text-xs" style={{ color: 'var(--muted)' }}>
                {weather.location} · {weather.provider_label}
                {weather.blend?.member_count > 1 && (
                  <> · {weather.blend.member_count} models
                    {weather.blend.spread_c > 0 && ` within ±${(weather.blend.spread_c / 2).toFixed(1)}°`}
                  </>
                )}
                {weather.stale && ' · last known forecast'}
              </p>
            </div>
            <button className="btn btn-ghost btn-icon shrink-0" onClick={onRefresh}
                    disabled={refreshing} aria-label="Refresh weather">
              {refreshing ? <Spinner size={16} /> : <Icon name="refresh" size={16} />}
            </button>
          </div>

          <div className="relative mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label="High / low"
                    value={`${Math.round(t.max_c)}° / ${Math.round(t.min_c)}°`} sub="today" />
            <Metric label="Rain"
                    value={t.rain_chance != null ? `${Math.round(t.rain_chance)}%` : '—'}
                    sub={t.hours_remaining ? `next ${t.hours_remaining} h` : 'chance'} />
            <Metric label="Wind"
                    value={c.wind_kph != null ? `${Math.round(c.wind_kph)}` : '—'} sub="km/h" />
            <Metric label="Humidity"
                    value={c.humidity != null ? `${Math.round(c.humidity)}%` : '—'} sub="now" />
          </div>
        </div>

        {days.length > 0 && (
          <div className="px-4 py-4 sm:px-5 sm:py-5" style={{ background: 'var(--surface)' }}>
            <p className="label mb-2.5">Next {days.length} days</p>
            {/* Scrolls on a phone rather than crushing six days into the width. */}
            <div className="scroll-x -mx-4 flex gap-2 px-4 sm:-mx-5 sm:px-5 lg:mx-0 lg:px-0">
              {days.map((d) => (
                <div key={d.date}
                     className="flex min-w-[3.9rem] flex-1 flex-col items-center gap-1.5 rounded-xl px-1 py-3"
                     style={{ background: 'var(--surface-2)' }}>
                  <span className="text-2xs font-semibold uppercase tracking-wide"
                        style={{ color: 'var(--muted)' }}>
                    {new Date(d.date).toLocaleDateString(undefined, { weekday: 'short' })}
                  </span>
                  <span style={{ color: CONDITION_TINT[d.condition?.group] || 'var(--accent)' }}>
                    <WeatherIcon group={d.condition?.group} size={20} />
                  </span>
                  <span className="text-sm font-bold tabular-nums">{Math.round(d.max_c)}°</span>
                  <span className="text-2xs tabular-nums" style={{ color: 'var(--muted)' }}>
                    {Math.round(d.min_c)}°
                  </span>
                  {d.rain_chance > 20 && (
                    <span className="flex items-center gap-0.5 text-2xs tabular-nums"
                          style={{ color: CONDITION_TINT.rain }}>
                      <Icon name="drop" size={9} /> {Math.round(d.rain_chance)}%
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

/** The match score as a small ring — read at a glance, precise on inspection. */
function ScoreRing({ pct }) {
  const r = 10.5
  const c = 2 * Math.PI * r
  return (
    <span className="relative inline-flex h-7 w-7 items-center justify-center" title={`${pct}% match`}>
      <svg viewBox="0 0 28 28" className="absolute inset-0 -rotate-90">
        <circle cx="14" cy="14" r={r} fill="none" stroke="var(--surface-2)" strokeWidth="3" />
        <circle cx="14" cy="14" r={r} fill="none" stroke="var(--accent)" strokeWidth="3"
                strokeLinecap="round" strokeDasharray={c}
                strokeDashoffset={c * (1 - Math.min(pct, 100) / 100)} />
      </svg>
      <span className="text-[.55rem] font-bold tabular-nums">{pct}</span>
    </span>
  )
}

function SuggestionCard({ suggestion, index, onWear, onRate, verdict, busy }) {
  const pct = Math.round(suggestion.score * 100)
  return (
    <div className="card card-link fade-up overflow-hidden"
         style={{ animationDelay: `${index * 70}ms` }}>
      <div className="flex items-center justify-between gap-2 px-4 pt-3.5">
        <div className="flex items-center gap-2">
          <ScoreRing pct={pct} />
          <span className="text-sm font-semibold">
            {index === 0 ? 'Best match' : `Option ${index + 1}`}
          </span>
          {index === 0 && (
            <span className="rounded-full px-2 py-0.5 text-2xs font-bold uppercase tracking-wide"
                  style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
              Top pick
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Every thumb is a training example — this is how the suggestions
              learn your taste rather than an average person's. */}
          <button className="btn btn-ghost btn-icon" title="More like this"
                  aria-pressed={verdict === 1} onClick={() => onRate(suggestion, 1)}>
            <Icon name="thumbUp" size={16}
                  style={verdict === 1 ? { color: 'var(--good)' } : undefined} />
          </button>
          <button className="btn btn-ghost btn-icon" title="Less like this"
                  aria-pressed={verdict === -1} onClick={() => onRate(suggestion, -1)}>
            <Icon name="thumbDown" size={16}
                  style={verdict === -1 ? { color: 'var(--bad)' } : undefined} />
          </button>
        </div>
      </div>

      {/* Photos and the decision sit side by side once there is room. Stacked,
          the garments took a fifth of a wide card and left the rest empty. */}
      <div className="gap-5 px-4 py-3.5 md:flex md:items-start">
        <div className="scroll-x -mx-4 flex gap-2.5 px-4 md:mx-0 md:flex-1 md:flex-wrap md:px-0">
          {suggestion.items.map((item) => (
            <Link key={item.id} to={`/wardrobe/${item.id}`}
                  className="w-24 shrink-0" title={item.name}>
              <div className="aspect-[3/4] overflow-hidden rounded-xl border"
                   style={{ borderColor: 'var(--border)' }}>
                <ItemPhoto item={item} rounded="rounded-[.7rem]" />
              </div>
              <p className="mt-1 truncate text-2xs font-medium">{item.name}</p>
            </Link>
          ))}
        </div>

        <div className="mt-3 space-y-3 md:mt-0 md:w-64 md:shrink-0">
          <div className="flex flex-wrap gap-1.5">
            {suggestion.reasons.map((r, i) => (
              <span key={i} className="rounded-full px-2 py-0.5 text-2xs font-medium"
                    style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>
                {r}
              </span>
            ))}
          </div>
          <button className="btn btn-primary w-full" onClick={() => onWear(suggestion)}
                  disabled={busy}>
            {busy ? <Spinner size={16} /> : <Icon name="check" size={16} />} Wear this
          </button>
          <p className="text-2xs tabular-nums" style={{ color: 'var(--muted)' }}>
            Total warmth {suggestion.warmth}
            {suggestion.target_warmth != null && ` of ${suggestion.target_warmth} wanted`}
          </p>
        </div>
      </div>
    </div>
  )
}

/** First run: say what the app does in three steps, then point at the camera. */
function GettingStarted({ message }) {
  const steps = [
    { icon: 'camera', title: 'Photograph your wardrobe',
      text: 'Snap what you own. Colours are read straight off the photo — no AI needed.' },
    { icon: 'sun', title: 'Get dressed by the weather',
      text: 'Outfits are scored against the forecast, the occasion and colour harmony.' },
    { icon: 'sparkle', title: 'It learns you',
      text: 'Thumb suggestions, rate wears, and it calibrates to your taste and how you feel the cold.' },
  ]
  return (
    <div className="card relative overflow-hidden px-5 py-8 sm:px-8">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40" aria-hidden="true"
           style={{ background: 'radial-gradient(30rem 12rem at 30% -5rem, var(--glow), transparent 70%)' }} />
      <p className="font-display relative text-2xl font-semibold">Start with a few photos</p>
      <p className="relative mt-1 max-w-lg text-sm" style={{ color: 'var(--muted)' }}>
        {message || 'Add a handful of things you actually wear and the suggestions begin.'}
      </p>
      <div className="relative mt-6 grid gap-4 sm:grid-cols-3">
        {steps.map((s, i) => (
          <div key={s.title} className="flex gap-3 sm:block">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl sm:mb-3"
                  style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
              <Icon name={s.icon} size={18} />
            </span>
            <div>
              <p className="text-sm font-semibold">{i + 1}. {s.title}</p>
              <p className="mt-0.5 text-xs leading-relaxed" style={{ color: 'var(--muted)' }}>
                {s.text}
              </p>
            </div>
          </div>
        ))}
      </div>
      <Link to="/wardrobe" className="btn btn-primary relative mt-6">
        <Icon name="camera" size={16} /> Add your first items
      </Link>
    </div>
  )
}

export default function Today() {
  const toast = useToast()
  const meta = useMeta()
  const [occasion, setOccasion] = useLocalState('outfits.occasion', 'everyday')
  const [dayOffset, setDayOffset] = useState(0)
  const [useAI, setUseAI] = useLocalState('outfits.useAI', false)
  // The stylist is a Gemini feature. With no provider there is nothing behind
  // the switch, so it is not offered — and a preference left on from when there
  // was one does not keep asking for a suggestion that cannot be made.
  const aiAvailable = Boolean(meta.ai?.available)
  const wantsAI = useAI && aiAvailable
  const [wearing, setWearing] = useState(null)
  const [refreshing, setRefreshing] = useState(false)

  // A base is a saved partial outfit — trainers and joggers filed as "Gym".
  // Selecting one pins its pieces, and every suggestion is built around them.
  const [params, setParams] = useSearchParams()
  const baseId = Number(params.get('base')) || null
  const saved = useAsync(() => api.outfits(), [])
  const bases = (saved.data?.outfits || []).filter((o) => o.is_base)
  const base = bases.find((b) => b.id === baseId) || null
  const setBase = (id) => setParams(id ? { base: String(id) } : {}, { replace: true })

  const weather = useAsync(() => api.weather(), [])
  const load = useCallback(
    () => api.suggest({ occasion, count: 3,
                        day_offset: dayOffset, use_ai: wantsAI,
                        pinned: base ? base.items.map((i) => i.id) : undefined }),
    [occasion, dayOffset, wantsAI, base?.id]
  )
  const suggestions = useAsync(load, [occasion, dayOffset, wantsAI, base?.id])

  const refreshWeather = async () => {
    setRefreshing(true)
    await api.weather(true).catch(() => {})
    await weather.reload(true)
    await suggestions.reload(true)
    setRefreshing(false)
  }

  // Verdicts already given this session, keyed by the outfit's items, so the
  // thumb stays lit across reshuffles that surface the same combination.
  const [verdicts, setVerdicts] = useState({})
  const rate = async (suggestion, verdict) => {
    const key = suggestion.item_ids.join(',')
    const existing = verdicts[key]
    try {
      if (existing) {
        await api.withdrawSuggestFeedback(existing.id)
        setVerdicts((v) => { const next = { ...v }; delete next[key]; return next })
        if (existing.verdict === verdict) return          // same thumb again: undone
      }
      const res = await api.suggestFeedback({
        verdict, item_ids: suggestion.item_ids, occasion, day_offset: dayOffset,
      })
      setVerdicts((v) => ({ ...v, [key]: { id: res.id, verdict } }))
      const t = res.taste
      toast(t.learning
        ? `Noted — ${t.likes} liked, ${t.dislikes} disliked. Suggestions are learning.`
        : `Noted. ${t.needed} more verdict${t.needed === 1 ? '' : 's'} and the scoring starts adapting.`,
        'success')
    } catch (e) { toast(e.message, 'error') }
  }

  const wear = async (suggestion) => {
    setWearing(suggestion.item_ids.join(','))
    try {
      const res = await api.logWear({ item_ids: suggestion.item_ids, occasion })
      // Point at where the feedback lives, since that is the whole loop: the
      // warmth calibration only learns from comfort ratings given after a wear.
      toast('Logged. Say how it felt in History and the suggestions calibrate to you.', 'success')
      suggestions.reload(true)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setWearing(null)
    }
  }

  const data = suggestions.data
  const todayLine = new Date().toLocaleDateString(undefined,
    { weekday: 'long', day: 'numeric', month: 'long' })

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <PageHeader
        kicker={todayLine}
        title="Today"
        description="What the weather is doing, and what to wear in it."
      />
      <WeatherCard weather={weather.data} onRefresh={refreshWeather} refreshing={refreshing} />
      <Warnings warnings={weather.data?.warnings} />

      <div className="space-y-3">
        <div className="rail">
          {DAYS.map((label, i) => (
            <Chip key={label} active={dayOffset === i} onClick={() => setDayOffset(i)}>{label}</Chip>
          ))}
        </div>
        <div className="rail">
          {OCCASIONS.map((o) => (
            <Chip key={o} active={occasion === o} onClick={() => setOccasion(o)}>
              {o[0].toUpperCase() + o.slice(1)}
            </Chip>
          ))}
        </div>
        {bases.length > 0 && (
          <div className="rail items-center">
            <span className="shrink-0 text-xs" style={{ color: 'var(--muted)' }}>
              Build around
            </span>
            {bases.map((b) => (
              <Chip key={b.id} active={base?.id === b.id}
                    onClick={() => setBase(base?.id === b.id ? null : b.id)}>
                <Icon name="layers" size={14} /> {b.name}
              </Chip>
            ))}
            {base && (
              <span className="shrink-0 text-xs" style={{ color: 'var(--muted)' }}>
                — suggestions are built around it, one piece per layer where it holds options
              </span>
            )}
          </div>
        )}
      </div>

      <Section
        title="Suggestions"
        action={
          <>
            {aiAvailable && (
              <Chip active={useAI} onClick={() => setUseAI(!useAI)}>
                <Icon name="sparkle" size={14} /> AI stylist
              </Chip>
            )}
            <button className="btn btn-ghost" onClick={() => suggestions.reload()}
                    disabled={suggestions.loading}>
              {suggestions.loading ? <Spinner size={16} /> : <Icon name="refresh" size={16} />}
              Reshuffle
            </button>
          </>
        }
      >
        <ErrorNote error={suggestions.error} onRetry={suggestions.reload} />

        {suggestions.loading && !data && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => <div key={i} className="skeleton h-56 rounded-2xl" />)}
          </div>
        )}

        {data?.missing_categories?.length > 0 && (
          <GettingStarted message={data.message} />
        )}

        {data?.suggestions?.map((s, i) => (
          <SuggestionCard
            key={s.item_ids.join('-')} suggestion={s} index={i}
            onWear={wear} onRate={rate}
            verdict={verdicts[s.item_ids.join(',')]?.verdict}
            busy={wearing === s.item_ids.join(',')}
          />
        ))}

        {data && !data.suggestions?.length && !data.missing_categories?.length && (
          <EmptyState
            icon="drop"
            title="Nothing to suggest"
            hint="No combination matches right now. Try another occasion, or add a few more pieces."
          />
        )}
      </Section>

      {aiAvailable && data?.ai && (
        <Section title="AI stylist">
          {data.ai.available ? (
            <div className="card px-4 py-4">
              <p className="flex items-center gap-1.5 text-sm font-semibold">
                <span style={{ color: 'var(--accent)' }}><Icon name="sparkle" size={15} /></span>
                {data.ai.name || 'Stylist pick'}
              </p>
              <div className="scroll-x mt-3 flex gap-2">
                {data.ai.items.map((item) => (
                  <Link key={item.id} to={`/wardrobe/${item.id}`} className="w-24 shrink-0">
                    <div className="aspect-[3/4] overflow-hidden rounded-lg"><ItemPhoto item={item} rounded="rounded-lg" /></div>
                    <p className="mt-1 truncate text-2xs">{item.name}</p>
                  </Link>
                ))}
              </div>
              <p className="mt-3 text-sm" style={{ color: 'var(--muted)' }}>{data.ai.reasoning}</p>
              <button className="btn btn-primary mt-3"
                      onClick={() => wear({ item_ids: data.ai.items.map((i) => i.id) })}>
                <Icon name="check" size={16} /> Wear this
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
