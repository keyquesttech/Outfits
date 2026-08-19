import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAsync, useDebounced, useLocalState } from '../hooks.js'
import { applyTheme } from '../theme.js'
import {
  Chip, ErrorNote, Field, Icon, Section, Spinner, WeatherIcon, titleCase, useToast,
} from '../components/ui.jsx'

const THEMES = [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]

/* ------------------------------------------------------------- location */

function LocationPicker({ form, setForm, onSave, busy }) {
  const toast = useToast()
  const [query, setQuery] = useState('')
  const debounced = useDebounced(query, 400)
  const [locating, setLocating] = useState(false)
  const [manual, setManual] = useState(false)

  const search = useAsync(
    () => (debounced.length >= 2 ? api.geocode(debounced) : Promise.resolve({ results: [] })),
    [debounced]
  )

  // Browsers only expose geolocation on secure origins. http://outfits.local is
  // not one, so on the Pi this is usually unavailable — say so plainly instead
  // of letting the button fail with a cryptic permission error.
  const secure = typeof window !== 'undefined' && window.isSecureContext
  const hasGeo = typeof navigator !== 'undefined' && 'geolocation' in navigator

  const useDevice = () => {
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      async ({ coords }) => {
        const lat = coords.latitude.toFixed(4)
        const lon = coords.longitude.toFixed(4)
        let label = `${lat}, ${lon}`
        try {
          const near = await api.geocode(`${lat},${lon}`)
          if (near.results?.[0]) label = near.results[0].label
        } catch { /* naming is a nicety, the coordinates are the point */ }
        setForm((f) => ({ ...f, latitude: lat, longitude: lon, location_name: label }))
        setLocating(false)
        toast('Location set from your device.', 'success')
      },
      (err) => {
        setLocating(false)
        toast(
          err.code === 1
            ? 'Location permission was denied. Search for your town instead.'
            : `Could not get device location: ${err.message}`,
          'error'
        )
      },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 300000 }
    )
  }

  const choose = (r) => {
    setForm((f) => ({
      ...f,
      latitude: String(r.latitude),
      longitude: String(r.longitude),
      timezone: r.timezone || f.timezone,
      location_name: r.label,
    }))
    setQuery('')
    toast(`Location set to ${r.label}.`, 'success')
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
        <button className="btn" onClick={useDevice} disabled={!secure || !hasGeo || locating}>
          {locating ? <Spinner size={15} /> : <Icon name="search" size={15} />}
          Use my device location
        </button>
        <button className="btn btn-ghost" onClick={() => setManual((m) => !m)}>
          {manual ? 'Hide' : 'Enter'} coordinates
        </button>
      </div>

      {!secure && (
        <p className="text-xs" style={{ color: 'var(--muted)' }}>
          Device location needs a secure connection, and this app is served over plain HTTP
          on your network, so browsers block it here. Searching for your town below sets the
          same thing.
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
            <button key={i} onClick={() => choose(r)}
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
            <input className="input" value={form.latitude}
                   onChange={(e) => setForm({ ...form, latitude: e.target.value })} />
          </Field>
          <Field label="Longitude">
            <input className="input" value={form.longitude}
                   onChange={(e) => setForm({ ...form, longitude: e.target.value })} />
          </Field>
          <Field label="Place name">
            <input className="input" value={form.location_name}
                   onChange={(e) => setForm({ ...form, location_name: e.target.value })} />
          </Field>
          <Field label="Timezone">
            <input className="input" value={form.timezone}
                   onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          </Field>
        </div>
      )}

      <button className="btn btn-primary" onClick={onSave} disabled={busy}>
        {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save location
      </button>
    </div>
  )
}

/* -------------------------------------------------------------- weather */

function WeatherSettings({ data, form, setForm, save, busy }) {
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState(null)

  const providers = data.weather_providers || []
  const current = form.weather_provider || 'open-meteo'
  const usage = data.weather_usage || {}
  const keySet = data.settings.metoffice_api_key_set
  const region = data.warning_region
  const optimize = form.metoffice_optimize !== '0'
  const warningsOn = form.warnings_enabled !== '0'

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
              onClick={() => setForm({ ...form, weather_provider: p.name })}
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
                   onChange={(e) => setForm({ ...form, metoffice_api_key: e.target.value })} />
          </Field>

          <button
            type="button"
            onClick={() => setForm({ ...form, metoffice_optimize: optimize ? '0' : '1' })}
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

      <div className="flex flex-wrap gap-2">
        <button className="btn" onClick={test} disabled={testing}>
          {testing ? <Spinner size={15} /> : <Icon name="refresh" size={15} />} Test connection
        </button>
        <button className="btn btn-primary" onClick={() => save({
          weather_provider: current,
          metoffice_api_key: form.metoffice_api_key || '',
          metoffice_optimize: optimize ? '1' : '0',
        })} disabled={busy}>
          {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save source
        </button>
      </div>

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
          onClick={() => setForm({ ...form, warnings_enabled: warningsOn ? '0' : '1' })}
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

      <button className="btn btn-primary" onClick={() => save({
        warnings_enabled: warningsOn ? '1' : '0',
      })} disabled={busy}>
        {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save warnings
      </button>
    </div>
  )
}

/* ---------------------------------------------------------------- page */

export default function Settings() {
  const toast = useToast()
  const { data, loading, error, reload } = useAsync(() => api.settings(), [])
  const jobs = useAsync(() => api.jobs(), [])
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [theme, setTheme] = useLocalState('outfits.theme', 'system')

  useEffect(() => { applyTheme(theme) }, [theme])
  useEffect(() => {
    if (data) setForm({ ...data.settings, gemini_api_key: '', metoffice_api_key: '' })
  }, [data])

  if (loading && !data) return <div className="skeleton h-64 rounded-2xl" />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!form) return null

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const save = async (values) => {
    setBusy(true)
    try {
      await api.saveSettings(values)
      toast('Settings saved.', 'success')
      await reload(true)
      setTestResult(null)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
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
      <Section title="Weather">
        <div className="card px-4 py-4">
          <WeatherSettings data={data} form={form} setForm={setForm} save={save} busy={busy} />
        </div>
      </Section>

      <Section title="Location">
        <div className="card px-4 py-4">
          <LocationPicker
            form={form} setForm={setForm} busy={busy}
            onSave={() => save({
              location_name: form.location_name || '',
              latitude: String(form.latitude || ''),
              longitude: String(form.longitude || ''),
              timezone: form.timezone || '',
            })}
          />
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
                <Chip key={p} active={provider === p} onClick={() => save({ ai_provider: p })}>
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
                       value={form.gemini_api_key} onChange={set('gemini_api_key')} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Text/vision model">
                  <input className="input" value={form.gemini_model || ''}
                         onChange={set('gemini_model')} />
                </Field>
                <Field label="Image model" hint="Used only for background removal.">
                  <input className="input" value={form.gemini_image_model || ''}
                         onChange={set('gemini_image_model')}
                         placeholder="gemini-2.5-flash-image" />
                </Field>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn btn-primary" disabled={busy}
                        onClick={() => save({
                          gemini_api_key: form.gemini_api_key,
                          gemini_model: form.gemini_model || '',
                          gemini_image_model: form.gemini_image_model || '',
                        })}>
                  {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save
                </button>
                <button className="btn" onClick={testAI} disabled={testing}>
                  {testing ? <Spinner size={15} /> : <Icon name="sparkle" size={15} />}
                  Test connection
                </button>
              </div>
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
          <Field label="Theme">
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
