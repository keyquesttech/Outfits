import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync, useAutoSave, useDebounced, useLocalState } from '../hooks.js'
import { applyTheme } from '../theme.js'
import CategoryManager from '../components/CategoryManager.jsx'
import {
  Chip, ErrorNote, Field, Icon, Section, Spinner, WeatherIcon, titleCase, useToast,
} from '../components/ui.jsx'

const THEMES = [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]

/* Typing needs a pause before saving; flipping a switch does not. */
const TYPING = 800
const SECRET = 1400
const INSTANT = 0

function SaveStatus({ status }) {
  const map = {
    idle: null,
    saving: { text: 'Saving…', tone: 'muted' },
    saved: { text: 'Saved', tone: 'good' },
    error: { text: 'Could not save', tone: 'bad' },
  }
  const s = map[status]
  if (!s) return null
  return (
    <span className="flex items-center gap-1.5 text-xs font-semibold"
          style={{ color: `var(--${s.tone})` }}>
      {status === 'saving' ? <Spinner size={13} /> : <Icon name="check" size={13} />}
      {s.text}
    </span>
  )
}

/* ------------------------------------------------------------- location */

function LocationPicker({ form, setForm, queue }) {
  const toast = useToast()
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query, 400)
  const [locating, setLocating] = useState(false)
  const [manual, setManual] = useState(false)
  const [found, setFound] = useState(null)

  const search = useAsync(
    () => (debounced.length >= 2 ? api.geocode(debounced) : Promise.resolve({ results: [] })),
    [debounced]
  )

  // Browsers only expose GPS on secure origins, and this app is served over
  // plain HTTP on the LAN, so navigator.geolocation refuses with "Only secure
  // origins are allowed". Fall back to an IP lookup, which needs no permission
  // and no HTTPS — approximate, but a forecast only needs the right town.
  const secure = typeof window !== 'undefined' && window.isSecureContext
  const hasGeo = typeof navigator !== 'undefined' && 'geolocation' in navigator

  const nameFor = async (lat, lon, fallback) => {
    try {
      const near = await api.geocode(`${lat},${lon}`)
      if (near.results?.[0]) return near.results[0].label
    } catch { /* naming is a nicety; the coordinates are the point */ }
    return fallback
  }

  const byGps = () => new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const lat = Number(coords.latitude.toFixed(4))
        const lon = Number(coords.longitude.toFixed(4))
        resolve({
          latitude: lat, longitude: lon, accuracy: 'gps',
          label: await nameFor(lat, lon, `${lat}, ${lon}`),
        })
      },
      reject,
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 300000 }
    )
  })

  const detect = async () => {
    setLocating(true)
    setFound(null)
    try {
      if (secure && hasGeo) {
        try {
          setFound(await byGps())
          return
        } catch { /* denied or unavailable — fall through to the network lookup */ }
      }
      const ip = await api.geoip()
      setFound({
        latitude: ip.latitude, longitude: ip.longitude, timezone: ip.timezone,
        label: ip.label, accuracy: 'network', source: ip.source,
      })
    } catch (e) {
      toast(`Could not detect a location: ${e.message}`, 'error')
    } finally {
      setLocating(false)
    }
  }

  const apply = (place) => {
    setForm((f) => ({
      ...f,
      latitude: String(place.latitude),
      longitude: String(place.longitude),
      timezone: place.timezone || f.timezone,
      location_name: place.label,
    }))
    queue({
      latitude: String(place.latitude),
      longitude: String(place.longitude),
      timezone: place.timezone || form.timezone || '',
      location_name: place.label,
    }, INSTANT)
  }

  // Coordinates typed by hand are only worth saving once they parse.
  const setCoord = (key) => (e) => {
    const value = e.target.value
    setForm((f) => ({ ...f, [key]: value }))
    if (value !== '' && Number.isFinite(Number(value))) queue({ [key]: value })
  }

  return (
    <div className="space-y-4">
      <div className="card px-3.5 py-3">
        <p className="label">Current location</p>
        <p className="mt-1 text-sm font-semibold">{form.location_name || 'Not set'}</p>
        <p className="text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
          {form.latitude}, {form.longitude} · {form.timezone}
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <button className="btn" onClick={detect} disabled={locating}>
          {locating ? <Spinner size={15} /> : <Icon name="search" size={15} />}
          Detect my location
        </button>
        <button className="btn btn-ghost" onClick={() => setManual((m) => !m)}>
          {manual ? 'Hide' : 'Enter'} coordinates
        </button>
      </div>

      {found && (
        <div className="card px-3.5 py-3" style={{ borderColor: 'var(--accent)' }}>
          <p className="label">
            {found.accuracy === 'gps' ? 'From your device' : 'From your network'}
          </p>
          <p className="mt-1 text-sm font-semibold">{found.label}</p>
          <p className="text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
            {found.latitude}, {found.longitude}
          </p>
          {found.accuracy === 'network' && (
            <p className="mt-1 text-xs" style={{ color: 'var(--warn)' }}>
              Worked out from your broadband address, so it can be a town or two out —
              check it before using it.
            </p>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            <button className="btn btn-primary" onClick={() => {
              apply(found)
              setFound(null)
              toast('Location updated.', 'success')
            }}>
              <Icon name="check" size={15} /> Use this
            </button>
            <button className="btn btn-ghost" onClick={() => setFound(null)}>Not right</button>
          </div>
        </div>
      )}

      {!secure && !found && (
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Your browser only shares GPS over a secure connection, and this app is served over
          plain HTTP on your network — so this works out roughly where you are from your
          broadband connection instead. Searching for your town is the precise way.
        </p>
      )}

      <Field label="Search for a place">
        <input className="input" value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder="Shoreditch, Bristol, Edinburgh…" />
      </Field>

      {search.loading && debounced.length >= 2 && (
        <p className="text-xs" style={{ color: 'var(--muted)' }}>Searching…</p>
      )}
      {search.data?.results?.length > 0 && (
        <div className="card divide-y" style={{ borderColor: 'var(--border)' }}>
          {search.data.results.map((r, i) => (
            <button key={i}
                    onClick={() => { apply(r); setQuery(''); toast(`Location set to ${r.label}.`, 'success') }}
                    className="flex w-full items-center justify-between gap-3 px-3.5 py-2.5 text-left">
              <span className="min-w-0">
                <span className="block truncate text-sm font-medium">{r.label}</span>
                <span className="block text-xs tabular-nums" style={{ color: 'var(--muted)' }}>
                  {r.latitude?.toFixed(3)}, {r.longitude?.toFixed(3)}
                </span>
              </span>
              <Icon name="plus" size={15} style={{ color: 'var(--accent)' }} />
            </button>
          ))}
        </div>
      )}

      {manual && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Latitude">
            <input className="input" value={form.latitude} onChange={setCoord('latitude')} />
          </Field>
          <Field label="Longitude">
            <input className="input" value={form.longitude} onChange={setCoord('longitude')} />
          </Field>
          <Field label="Place name">
            <input className="input" value={form.location_name}
                   onChange={(e) => {
                     setForm({ ...form, location_name: e.target.value })
                     queue({ location_name: e.target.value })
                   }} />
          </Field>
          <Field label="Timezone">
            <input className="input" value={form.timezone}
                   onChange={(e) => {
                     setForm({ ...form, timezone: e.target.value })
                     queue({ timezone: e.target.value })
                   }} />
          </Field>
        </div>
      )}
    </div>
  )
}

/* -------------------------------------------------------------- weather */

function WeatherSettings({ data, form, setForm, queue }) {
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState(null)

  const providers = data.weather_providers || []
  const current = form.weather_provider || 'open-meteo'
  const usage = data.weather_usage || {}
  const keySet = data.settings.metoffice_api_key_set
  const region = data.warning_region
  const optimize = form.metoffice_optimize !== '0'
  const warningsOn = form.warnings_enabled !== '0'

  const set = (values, wait) => {
    setForm((f) => ({ ...f, ...values }))
    queue(values, wait)
  }

  const test = async () => {
    setTesting(true)
    try {
      setResult(await api.testWeather(current, form.metoffice_api_key || null))
    } catch (e) {
      setResult({ ok: false, error: e.message })
    } finally {
      setTesting(false)
    }
  }

  return (
    <div className="space-y-4">
      <Field label="Forecast source">
        <div className="space-y-2">
          {providers.map((p) => (
            <button
              key={p.name} type="button"
              onClick={() => set({ weather_provider: p.name }, INSTANT)}
              className="card flex w-full items-start gap-3 px-3 py-2.5 text-left"
              style={current === p.name ? { borderColor: 'var(--accent)' } : undefined}
            >
              <span style={{ color: 'var(--accent)', marginTop: 2 }}>
                <WeatherIcon group={p.name === 'metoffice' ? 'rain' : 'clear'} size={17} />
              </span>
              <span className="min-w-0">
                <span className="block text-sm font-semibold">
                  {p.label}
                  {p.needs_key && (
                    <span className="ml-2 text-[0.68rem] font-normal"
                          style={{ color: keySet ? 'var(--good)' : 'var(--warn)' }}>
                      {keySet ? 'key saved' : 'needs a key'}
                    </span>
                  )}
                </span>
                <span className="block text-xs" style={{ color: 'var(--muted)' }}>
                  {p.description}
                </span>
              </span>
            </button>
          ))}
        </div>
      </Field>

      {current === 'metoffice' && (
        <>
          <Field
            label="Met Office DataHub API key"
            hint={keySet
              ? 'A key is stored. Leave blank to keep it, or paste a new one to replace it.'
              : 'Create a free account at datahub.metoffice.gov.uk and subscribe to Site Specific.'}
          >
            <input className="input" type="password" autoComplete="off"
                   placeholder={keySet ? '••••••••••••  (stored)' : 'paste your key'}
                   value={form.metoffice_api_key || ''}
                   onChange={(e) => set({ metoffice_api_key: e.target.value }, SECRET)} />
          </Field>

          <button
            type="button"
            onClick={() => set({ metoffice_optimize: optimize ? '0' : '1' }, INSTANT)}
            className="card flex w-full items-start gap-3 px-3 py-2.5 text-left"
            style={optimize ? { borderColor: 'var(--accent)' } : undefined}
          >
            <span className="mt-0.5 flex h-5 w-5 items-center justify-center rounded"
                  style={{
                    background: optimize ? 'var(--accent)' : 'var(--surface-2)',
                    border: '1px solid var(--border)', color: '#fff',
                  }}>
              {optimize && <Icon name="check" size={13} />}
            </span>
            <span>
              <span className="block text-sm font-semibold">Optimise for the free plan</span>
              <span className="block text-xs" style={{ color: 'var(--muted)' }}>
                Uses one three-hourly request instead of two, and caches for three hours.
                Roughly {usage.projected_monthly_calls ?? 240} calls a month rather than
                thousands. Turn off for hourly detail if you have the allowance.
              </span>
            </span>
          </button>

          <div className="card px-3.5 py-3">
            <p className="label">Usage this month</p>
            <p className="mt-1 text-2xl font-bold tabular-nums">{usage.calls ?? 0}</p>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              requests since {usage.month} · {usage.note}
            </p>
          </div>
        </>
      )}

      <button className="btn" onClick={test} disabled={testing}>
        {testing ? <Spinner size={15} /> : <Icon name="refresh" size={15} />} Test connection
      </button>

      {result && (
        <div className="rounded-xl px-3 py-2.5 text-sm"
             style={{ background: 'var(--surface-2)',
                      color: result.ok ? 'var(--good)' : 'var(--bad)' }}>
          {result.ok
            ? `${result.provider} responded: ${result.detail}${result.site ? ` (${result.site})` : ''}`
            : (result.error || 'Connection failed')}
          {result.ok && result.missing_fields?.length > 0 && (
            <p className="mt-1" style={{ color: 'var(--warn)' }}>
              Fields not found in the response: {result.missing_fields.join(', ')}.
              The forecast will still work but may be missing some detail.
            </p>
          )}
        </div>
      )}

      <hr style={{ borderColor: 'var(--border)' }} />

      <Field
        label="Severe weather warnings"
        hint="Met Office warnings in force today, for the region covering your location."
      >
        <button
          type="button"
          onClick={() => set({ warnings_enabled: warningsOn ? '0' : '1' }, INSTANT)}
          className="chip" style={warningsOn
            ? { background: 'var(--accent)', borderColor: 'var(--accent)', color: '#fff' }
            : undefined}
        >
          <Icon name="storm" size={13} /> Warnings {warningsOn ? 'on' : 'off'}
        </button>
      </Field>

      {warningsOn && (
        <div className="card px-3.5 py-3">
          <p className="label">Region</p>
          <p className="mt-1 text-sm font-semibold">
            {region?.in_uk ? region.label : 'Outside the UK'}
          </p>
          <p className="text-xs" style={{ color: 'var(--muted)' }}>
            {region?.in_uk
              ? 'Follows your location — set it below to change region.'
              : 'Met Office warnings only cover the UK, so none will be shown.'}
          </p>
          {current !== 'metoffice' && (
            <p className="mt-2 text-xs" style={{ color: 'var(--warn)' }}>
              Warnings appear on the Today page only while the Met Office is the
              forecast source.
            </p>
          )}
        </div>
      )}
    </div>
  )
}

/* ---------------------------------------------------------------- page */

function ColourMaintenance() {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)

  const run = async (overwrite) => {
    setBusy(true)
    try {
      const data = await api.rescanColours(overwrite)
      setResult(data)
      toast(data.changed.length
        ? `Re-read ${data.scanned} photos, ${data.changed.length} colour${data.changed.length === 1 ? '' : 's'} changed.`
        : `Re-read ${data.scanned} photos. Nothing changed.`, 'success')
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <div className="card px-4 py-4">
      <p className="text-sm" style={{ color: 'var(--muted)' }}>
        Every photo carries the colours read from it the day it was added. Reading them
        again applies the current colour engine to the whole wardrobe — useful after an
        upgrade, and harmless to run twice.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn" onClick={() => run(false)} disabled={busy}>
          {busy ? <Spinner size={15} /> : <Icon name="refresh" size={15} />}
          Fill in what is missing
        </button>
        <button className="btn" onClick={() => run(true)} disabled={busy}>
          <Icon name="refresh" size={15} /> Overwrite every colour
        </button>
      </div>
      <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
        The first only touches items whose colour is blank or unrecognised, so anything you
        chose by hand is left alone. The second replaces all of them with what the photo says.
      </p>
      {result && (
        <div className="mt-3 text-xs" style={{ color: 'var(--muted)' }}>
          <p>{result.scanned} photos read{result.unreadable ? `, ${result.unreadable} could not be opened` : ''}.</p>
          {result.changed.length > 0 && (
            <ul className="mt-1.5 space-y-0.5">
              {result.changed.slice(0, 12).map((c) => (
                <li key={c.id}>
                  <Link to={`/wardrobe/${c.id}`} style={{ color: 'var(--accent)' }}>{c.name}</Link>
                  {' '}— {c.was || 'nothing'} → <strong>{c.now || 'nothing'}</strong>
                </li>
              ))}
              {result.changed.length > 12 && <li>and {result.changed.length - 12} more.</li>}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export default function Settings() {
  const toast = useToast()
  const meta = useMeta()
  const { data, loading, error, reload } = useAsync(() => api.settings(), [])
  const jobs = useAsync(() => api.jobs(), [])
  const [form, setForm] = useState(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [theme, setTheme] = useLocalState('outfits.theme', 'system')
  const initialised = useRef(false)

  useEffect(() => { applyTheme(theme) }, [theme])

  // Seed the form once. Later refreshes must not clobber what is being typed.
  useEffect(() => {
    if (data && !initialised.current) {
      setForm({ ...data.settings, gemini_api_key: '', metoffice_api_key: '' })
      initialised.current = true
    }
  }, [data])

  const { queue, status } = useAutoSave(async (values) => {
    await api.saveSettings(values)
    // Secrets are write-only; clear the field so the UI shows "key saved".
    const secrets = Object.keys(values).filter((k) => k.endsWith('_api_key') && values[k])
    if (secrets.length) {
      setForm((f) => ({ ...f, ...Object.fromEntries(secrets.map((k) => [k, ''])) }))
    }
    await reload(true)
    // Turning a provider on or off changes what other pages should offer — the
    // AI stylist on Today is only worth a control when there is a key behind it.
    if (Object.keys(values).some((k) => k.startsWith("ai_") || k.endsWith("_api_key"))) {
      meta.reloadMeta?.()
    }
    setTestResult(null)
  })

  if (loading && !data) return <div className="skeleton h-64 rounded-2xl" />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!form) return null

  const set = (values, wait) => {
    setForm((f) => ({ ...f, ...values }))
    queue(values, wait)
  }

  const testAI = async () => {
    setTesting(true)
    try { setTestResult(await api.testAI()) }
    catch (e) { setTestResult({ ok: false, error: e.message }) }
    finally { setTesting(false) }
  }

  const provider = form.ai_provider || 'none'
  const keySet = data.settings.gemini_api_key_set

  return (
    <div className="space-y-6">
      <div className="sticky top-[3.6rem] z-20 -mx-4 flex items-center justify-between gap-3 px-4 py-2"
           style={{ background: 'color-mix(in srgb, var(--bg) 92%, transparent)' }}>
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Changes save automatically.
        </p>
        <SaveStatus status={status} />
      </div>

      <Section title="Weather">
        <div className="card px-4 py-4">
          <WeatherSettings data={data} form={form} setForm={setForm} queue={queue} />
        </div>
      </Section>

      <Section title="Location">
        <div className="card px-4 py-4">
          <LocationPicker form={form} setForm={setForm} queue={queue} />
        </div>
      </Section>

      <Section title="AI">
        <div className="card space-y-4 px-4 py-4">
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Everything works without AI — colours are read from photos regardless, and you can
            tag by hand. AI adds automatic tagging, care-label reading, and a stylist suggestion.
          </p>

          <Field label="Provider">
            <div className="flex gap-2">
              {(data.providers || []).map((p) => (
                <Chip key={p} active={provider === p}
                      onClick={() => set({ ai_provider: p }, INSTANT)}>
                  {p === 'none' ? 'No AI' : titleCase(p)}
                </Chip>
              ))}
            </div>
          </Field>

          {provider === 'gemini' && (
            <>
              <Field
                label="Gemini API key"
                hint={keySet ? 'A key is stored. Leave blank to keep it, or paste a new one.'
                             : 'Get one free at aistudio.google.com/apikey'}
              >
                <input className="input" type="password" autoComplete="off"
                       placeholder={keySet ? '••••••••••••  (stored)' : 'paste your key'}
                       value={form.gemini_api_key}
                       onChange={(e) => set({ gemini_api_key: e.target.value }, SECRET)} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Text/vision model">
                  <input className="input" value={form.gemini_model || ''}
                         onChange={(e) => set({ gemini_model: e.target.value }, TYPING)} />
                </Field>
                <Field label="Image model" hint="Used only for background removal.">
                  <input className="input" value={form.gemini_image_model || ''}
                         onChange={(e) => set({ gemini_image_model: e.target.value }, TYPING)}
                         placeholder="gemini-2.5-flash-image" />
                </Field>
              </div>
              <button className="btn" onClick={testAI} disabled={testing}>
                {testing ? <Spinner size={15} /> : <Icon name="sparkle" size={15} />}
                Test connection
              </button>
            </>
          )}

          {testResult && (
            <div className="rounded-xl px-3 py-2.5 text-sm"
                 style={{ background: 'var(--surface-2)',
                          color: testResult.ok ? 'var(--good)' : 'var(--bad)' }}>
              {testResult.ok
                ? `Connected. ${testResult.model || ''} replied “${testResult.reply || 'OK'}”.`
                : (testResult.error || 'Connection failed')}
              {!testResult.ok && testResult.hint && (
                <p className="mt-1" style={{ color: 'var(--muted)' }}>{testResult.hint}</p>
              )}
            </div>
          )}
        </div>
      </Section>

      <Section title="Appearance">
        <div className="card px-4 py-4">
          <Field label="Theme" hint="Stored in this browser only.">
            <div className="flex gap-2">
              {THEMES.map(([value, label]) => (
                <Chip key={value} active={theme === value} onClick={() => setTheme(value)}>
                  {label}
                </Chip>
              ))}
            </div>
          </Field>
        </div>
      </Section>

      <Section
        title="Background jobs"
        action={
          <button className="btn btn-ghost" onClick={() => jobs.reload()}>
            <Icon name="refresh" size={15} /> Refresh
          </button>
        }
      >
        <div className="card px-4 py-4">
          {jobs.data ? (
            <>
              <div className="flex flex-wrap gap-2">
                <span className="chip">Worker {jobs.data.worker_alive ? 'running' : 'stopped'}</span>
                {Object.entries(jobs.data.counts || {}).map(([k, v]) => (
                  <span key={k} className="chip">{titleCase(k)} {v}</span>
                ))}
                {!Object.keys(jobs.data.counts || {}).length && (
                  <span className="text-sm" style={{ color: 'var(--muted)' }}>No jobs yet.</span>
                )}
              </div>
              {jobs.data.recent?.length > 0 && (
                <div className="mt-3 space-y-1.5">
                  {jobs.data.recent.slice(0, 8).map((j) => (
                    <div key={j.id} className="flex items-center gap-2 text-xs">
                      <span className="font-medium">{titleCase(j.kind)}</span>
                      <span style={{ color: j.status === 'done' ? 'var(--good)'
                                          : j.status === 'failed' ? 'var(--bad)' : 'var(--muted)' }}>
                        {j.status}
                      </span>
                      {j.error && <span className="truncate"
                                        style={{ color: 'var(--muted)' }}>{j.error}</span>}
                      {j.status === 'failed' && (
                        <button className="btn btn-ghost !px-1.5 !py-0.5 ml-auto text-[0.7rem]"
                                onClick={async () => { await api.retryJob(j.id); jobs.reload(true) }}>
                          Retry
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : <Spinner />}
        </div>
      </Section>

      <Section title="Categories">
        <CategoryManager />
      </Section>

      <Section title="Colours">
        <ColourMaintenance />
      </Section>

      <Section title="About">
        <div className="card px-4 py-4 text-sm" style={{ color: 'var(--muted)' }}>
          <p>Outfits runs entirely on your Raspberry Pi. Photos live on its disk, the database
             is a single SQLite file, and nothing leaves the network unless you turn on an AI
             provider or the Met Office forecast.</p>
          <p className="mt-2">Back up by copying <code>data/outfits.db</code> and
             <code> data/photos/</code>.</p>
        </div>
      </Section>
    </div>
  )
}
