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
