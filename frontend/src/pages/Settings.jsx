import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAsync, useLocalState } from '../hooks.js'
import { applyTheme } from '../theme.js'
import {
  Chip, ErrorNote, Field, Icon, Section, Spinner, titleCase, useToast,
} from '../components/ui.jsx'

const THEMES = [['system', 'System'], ['light', 'Light'], ['dark', 'Dark']]

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
  useEffect(() => { if (data) setForm({ ...data.settings, gemini_api_key: '' }) }, [data])

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

  const test = async () => {
    setTesting(true)
    try { setTestResult(await api.testAI()) }
    catch (e) { setTestResult({ ok: false, error: e.message }) }
    finally { setTesting(false) }
  }

  const provider = form.ai_provider || 'none'
  const keySet = data.settings.gemini_api_key_set

  return (
    <div className="space-y-6">
      <Section title="Appearance">
        <div className="card px-4 py-4">
          <Field label="Theme">
            <div className="flex gap-2">
              {THEMES.map(([value, label]) => (
                <Chip key={value} active={theme === value} onClick={() => setTheme(value)}>{label}</Chip>
              ))}
            </div>
          </Field>
        </div>
      </Section>

      <Section title="AI">
        <div className="card space-y-4 px-4 py-4">
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Everything works without AI — colours are read from photos regardless, and you can tag
            by hand. AI adds automatic tagging, care-label reading, and a stylist suggestion.
          </p>

          <Field label="Provider">
            <div className="flex gap-2">
              {(data.providers || []).map((p) => (
                <Chip key={p} active={provider === p}
                      onClick={() => save({ ai_provider: p })}>
                  {p === 'none' ? 'No AI' : titleCase(p)}
                </Chip>
              ))}
            </div>
          </Field>

          {provider === 'gemini' && (
            <>
              <Field
                label="Gemini API key"
                hint={keySet ? 'A key is stored. Leave blank to keep it, or paste a new one to replace it.'
                             : 'Get one free at aistudio.google.com/apikey'}
              >
                <input className="input" type="password" autoComplete="off"
                       placeholder={keySet ? '••••••••••••  (stored)' : 'paste your key'}
                       value={form.gemini_api_key} onChange={set('gemini_api_key')} />
              </Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Text/vision model">
                  <input className="input" value={form.gemini_model || ''} onChange={set('gemini_model')} />
                </Field>
                <Field label="Image model" hint="Used only for background removal.">
                  <input className="input" value={form.gemini_image_model || ''}
                         onChange={set('gemini_image_model')} placeholder="gemini-2.5-flash-image" />
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
                <button className="btn" onClick={test} disabled={testing}>
                  {testing ? <Spinner size={15} /> : <Icon name="sparkle" size={15} />} Test connection
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

      <Section title="Location">
        <div className="card space-y-3 px-4 py-4">
          <p className="text-sm" style={{ color: 'var(--muted)' }}>
            Weather comes from Open-Meteo — free, no key, no account.
          </p>
          <Field label="Place name">
            <input className="input" value={form.location_name || ''} onChange={set('location_name')} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Latitude">
              <input className="input" value={form.latitude || ''} onChange={set('latitude')} />
            </Field>
            <Field label="Longitude">
              <input className="input" value={form.longitude || ''} onChange={set('longitude')} />
            </Field>
          </div>
          <Field label="Timezone">
            <input className="input" value={form.timezone || ''} onChange={set('timezone')} />
          </Field>
          <button className="btn btn-primary" disabled={busy}
                  onClick={() => save({
                    location_name: form.location_name || '',
                    latitude: String(form.latitude || ''),
                    longitude: String(form.longitude || ''),
                    timezone: form.timezone || '',
                  })}>
            {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save location
          </button>
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
                      {j.error && <span className="truncate" style={{ color: 'var(--muted)' }}>{j.error}</span>}
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
          <p>Outfits runs entirely on your Raspberry Pi. Photos live on its disk, the database is a
             single SQLite file, and nothing leaves the network unless you turn on an AI provider.</p>
          <p className="mt-2">Back up by copying <code>data/outfits.db</code> and <code>data/photos/</code>.</p>
        </div>
      </Section>
    </div>
  )
}
