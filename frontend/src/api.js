const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = `Request failed (${res.status})`
    try {
      const body = await res.json()
      detail = body.detail || detail
    } catch { /* response was not JSON */ }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

const get = (p) => request(p)
const post = (p, body) => request(p, { method: 'POST', body: JSON.stringify(body ?? {}) })
const put = (p, body) => request(p, { method: 'PUT', body: JSON.stringify(body ?? {}) })
const patch = (p, body) => request(p, { method: 'PATCH', body: JSON.stringify(body ?? {}) })
const del = (p) => request(p, { method: 'DELETE' })

const qs = (params) => {
  const clean = Object.entries(params || {}).filter(
    ([, v]) => v !== undefined && v !== null && v !== ''
  )
  return clean.length ? '?' + new URLSearchParams(clean).toString() : ''
}

export const api = {
  meta: () => get('/api/meta'),
  fieldValues: () => get('/api/field-values'),

  categories: () => get('/api/categories'),
  createCategory: (body) => post('/api/categories', body),
  updateCategory: (key, body) => patch(`/api/categories/${key}`, body),
  deleteCategory: (key, moveTo) =>
    del(`/api/categories/${key}` + (moveTo ? `?move_to=${encodeURIComponent(moveTo)}` : '')),
  health: () => get('/api/health'),

  items: (params) => get('/api/items' + qs(params)),
  item: (id) => get(`/api/items/${id}`),
  createItem: (body) => post('/api/items', body),
  updateItem: (id, body) => patch(`/api/items/${id}`, body),
  deleteItem: (id, hard = false) => del(`/api/items/${id}${hard ? '?hard=true' : ''}`),
  setStatus: (id, status) => post(`/api/items/${id}/status`, { status }),
  analyse: (id, kind = 'analyse_item') => post(`/api/items/${id}/analyse?kind=${kind}`),
  putCare: (id, body) => put(`/api/items/${id}/care`, body),
  rescanItemColours: (id) => post(`/api/items/${id}/rescan-colours`),
  rescanColours: (overwrite = false) =>
    post(`/api/colours/rescan?overwrite=${overwrite}`),

  uploadItem: (file, fields = {}) => {
    const form = new FormData()
    form.append('file', file)
    Object.entries(fields).forEach(([k, v]) => form.append(k, String(v)))
    return request('/api/items/upload', { method: 'POST', body: form })
  },
  replacePhoto: (id, file, analyse = false) => {
    const form = new FormData()
    form.append('file', file)
    form.append('analyse', String(analyse))
    return request(`/api/items/${id}/photo`, { method: 'POST', body: form })
  },
  careLabel: (id, file) => {
    const form = new FormData()
    form.append('file', file)
    return request(`/api/items/${id}/care-label`, { method: 'POST', body: form })
  },

  outfits: (params) => get('/api/outfits' + qs(params)),
  outfit: (id) => get(`/api/outfits/${id}`),
  createOutfit: (body) => post('/api/outfits', body),
  updateOutfit: (id, body) => put(`/api/outfits/${id}`, body),
  favouriteOutfit: (id) => post(`/api/outfits/${id}/favourite`),
  deleteOutfit: (id) => del(`/api/outfits/${id}`),

  wears: (params) => get('/api/wear' + qs(params)),
  logWear: (body) => post('/api/wear', body),
  rateComfort: (id, verdict) => post(`/api/wear/${id}/comfort?verdict=${verdict}`),
  deleteWear: (id) => del(`/api/wear/${id}`),

  laundry: () => get('/api/laundry/plan'),
  wash: (body) => post('/api/laundry/wash', body),
  washHistory: () => get('/api/laundry/history'),

  weather: (refresh = false) => get('/api/weather' + (refresh ? '?refresh=true' : '')),
  weatherProviders: () => get('/api/weather/providers'),
  weatherUsage: () => get('/api/weather/usage'),
  weatherWarnings: (region) => get('/api/weather/warnings' + qs({ region })),
  testWeather: (provider, api_key) => post('/api/weather/test', { provider, api_key }),
  geocode: (q) => get('/api/geocode' + qs({ q })),
  geoip: (refresh = false) => get('/api/geoip' + (refresh ? '?refresh=true' : '')),
  suggest: (body) => post('/api/suggest', body),
  calibration: () => get('/api/suggest/calibration'),

  analytics: () => get('/api/analytics'),

  settings: () => get('/api/settings'),
  saveSettings: (values) => put('/api/settings', { values }),
  testAI: () => post('/api/settings/ai/test'),
  jobs: () => get('/api/jobs'),
  retryJob: (id) => post(`/api/jobs/${id}/retry`),
}
