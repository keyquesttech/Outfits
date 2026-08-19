import { useCallback, useEffect, useRef, useState } from 'react'

/** Run an async loader, exposing data/loading/error plus a manual reload. */
export function useAsync(loader, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })
  const alive = useRef(true)
  const fn = useRef(loader)
  fn.current = loader

  const run = useCallback(async (quiet = false) => {
    if (!quiet) setState((s) => ({ ...s, loading: true, error: null }))
    try {
      const data = await fn.current()
      if (alive.current) setState({ data, loading: false, error: null })
      return data
    } catch (error) {
      if (alive.current) setState((s) => ({ ...s, loading: false, error }))
    }
  }, [])

  useEffect(() => {
    alive.current = true
    run()
    return () => { alive.current = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { ...state, reload: run, setData: (d) => setState((s) => ({ ...s, data: d })) }
}

/** Debounce a fast-changing value, e.g. a search box. */
export function useDebounced(value, delay = 300) {
  const [out, setOut] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setOut(value), delay)
    return () => clearTimeout(t)
  }, [value, delay])
  return out
}

export function useLocalState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw === null ? initial : JSON.parse(raw)
    } catch { return initial }
  })
  useEffect(() => {
    try { localStorage.setItem(key, JSON.stringify(value)) } catch { /* private mode */ }
  }, [key, value])
  return [value, setValue]
}

/**
 * Debounced auto-save.
 *
 * Changes are queued by field and flushed together after a pause, so typing an
 * API key sends one request rather than one per keystroke. Pass delay 0 for
 * things toggled rather than typed — a switch should save the instant it moves.
 */
export function useAutoSave(save, { delay = 700 } = {}) {
  const [status, setStatus] = useState('idle')
  const pending = useRef({})
  const timer = useRef(null)
  const saveRef = useRef(save)
  saveRef.current = save

  const flush = useCallback(async () => {
    const values = pending.current
    pending.current = {}
    if (!Object.keys(values).length) return
    setStatus('saving')
    try {
      await saveRef.current(values)
      setStatus('saved')
      setTimeout(() => setStatus((s) => (s === 'saved' ? 'idle' : s)), 2500)
    } catch (err) {
      setStatus('error')
      throw err
    }
  }, [])

  const queue = useCallback((values, wait = delay) => {
    pending.current = { ...pending.current, ...values }
    clearTimeout(timer.current)
    if (wait <= 0) flush().catch(() => {})
    else timer.current = setTimeout(() => flush().catch(() => {}), wait)
  }, [delay, flush])

  useEffect(() => () => clearTimeout(timer.current), [])
  return { queue, flush, status }
}
