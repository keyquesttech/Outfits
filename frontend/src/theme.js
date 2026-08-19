const KEY = 'outfits.theme'

export function applyTheme(theme) {
  const root = document.documentElement
  if (!theme || theme === 'system') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', theme)
}

export function readTheme() {
  try {
    const raw = localStorage.getItem(KEY)
    return raw === null ? 'system' : JSON.parse(raw)
  } catch {
    return 'system'
  }
}

/** Run before React mounts, so the first paint is already the right theme. */
export function initTheme() {
  applyTheme(readTheme())
}
