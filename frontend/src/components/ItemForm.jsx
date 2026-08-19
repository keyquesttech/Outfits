import { Chip, Field, Icon, titleCase } from './ui.jsx'

/** Initial form state for an item, used by both editing and first-time tagging. */
export function itemFormState(item = {}) {
  return {
    name: item.name || '',
    category: item.category || 'top',
    subcategory: item.subcategory || '',
    brand: item.brand || '',
    material: item.material || '',
    pattern: item.pattern || '',
    fit: item.fit || '',
    colour_primary: item.colour_primary || '',
    colour_secondary: item.colour_secondary || '',
    warmth: item.warmth ?? 5,
    formality: item.formality ?? 3,
    seasons: item.seasons || [],
    wind_proof: !!item.wind_proof,
    water_proof: !!item.water_proof,
    wash_after_wears: item.wash_after_wears ?? '',
    notes: item.notes || '',
    tags: (item.tags || []).join(', '),
  }
}

/** Convert form state into an API payload. */
export function itemFormPayload(form) {
  return {
    ...form,
    warmth: Number(form.warmth),
    formality: Number(form.formality),
    wash_after_wears: form.wash_after_wears === '' ? null : Number(form.wash_after_wears),
    tags: parseTags(form.tags),
  }
}

const parseTags = (raw) =>
  String(raw || '').split(',').map((t) => t.trim()).filter(Boolean)

/**
 * The three warmth choices, as numbers on the stored 0-10 scale.
 *
 * They are relative to what is normal for the category, because "hot" means
 * something completely different for a t-shirt than for an overcoat. Values are
 * forced apart so the three buttons can never map to the same number.
 */
export function warmthOptions(meta, category) {
  const base = meta.default_warmth?.[category] ?? 5
  const levels = meta.warmth_levels || []
  const raw = levels.map((l, i) =>
    base > 1 ? Math.round(base * l.factor) : [0, 1, 2][i] ?? i)

  const spread = []
  raw.forEach((v, i) => {
    let value = Math.max(0, Math.min(10, v))
    if (i > 0 && value <= spread[i - 1]) value = Math.min(10, spread[i - 1] + 1)
    spread.push(value)
  })
  // Clamping at 10 can re-collide from the top; push the lower ones down instead.
  for (let i = spread.length - 1; i > 0; i--) {
    if (spread[i] <= spread[i - 1]) spread[i - 1] = Math.max(0, spread[i] - 1)
  }
  return levels.map((l, i) => ({ ...l, value: spread[i] }))
}

/** Which of the three buttons a stored number corresponds to. */
export function nearestOption(options, value) {
  if (!options.length) return null
  return options.reduce((best, o) =>
    Math.abs(o.value - value) < Math.abs(best.value - value) ? o : best)
}

function LevelPicker({ label, hint, options, value, onChange }) {
  const active = nearestOption(options, Number(value))
  return (
    <Field label={label} hint={hint}>
      <div className="grid grid-cols-3 gap-2">
        {options.map((o) => {
          const on = active && active.key === o.key
          return (
            <button
              key={o.key} type="button" onClick={() => onChange(o.value)}
              className="card px-2 py-2 text-center"
              style={on
                ? { borderColor: 'var(--accent)', background: 'var(--accent-soft)' }
                : undefined}
            >
              <span className="block text-sm font-semibold"
                    style={on ? { color: 'var(--accent)' } : undefined}>
                {o.label}
              </span>
              <span className="block text-[0.68rem] leading-tight"
                    style={{ color: 'var(--muted)' }}>
                {o.hint}
              </span>
            </button>
          )
        })}
      </div>
    </Field>
  )
}

export default function ItemForm({ form, setForm, meta, palette, compact = false }) {
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const toggleSeason = (s) =>
    setForm({
      ...form,
      seasons: form.seasons.includes(s)
        ? form.seasons.filter((x) => x !== s)
        : [...form.seasons, s],
    })

  const tags = parseTags(form.tags)
  const toggleTag = (t) => {
    const next = tags.includes(t) ? tags.filter((x) => x !== t) : [...tags, t]
    setForm({ ...form, tags: next.join(', ') })
  }

  const warmths = warmthOptions(meta, form.category)
  const fits = meta.fit_options?.[form.category] || []
  const formalities = (meta.formality_levels || [])
  const suggestedWash = meta.default_wash_after_wears?.[form.category]

  return (
    <div className="space-y-4">
      <Field label="Name">
        <input className="input" value={form.name} onChange={set('name')}
               placeholder="Navy merino crew jumper" autoFocus />
      </Field>

      <div className="grid grid-cols-2 gap-3">
        <Field label="Category">
          <select className="select" value={form.category} onChange={set('category')}>
            {(meta.categories || []).map((c) => (
              <option key={c} value={c}>{titleCase(c)}</option>
            ))}
          </select>
        </Field>
        <Field label="Subcategory">
          <input className="input" value={form.subcategory} onChange={set('subcategory')}
                 placeholder="crew neck" />
        </Field>
        <Field label="Brand">
          <input className="input" value={form.brand} onChange={set('brand')} />
        </Field>
        <Field label="Material">
          <input className="input" value={form.material} onChange={set('material')}
                 placeholder="merino wool" />
        </Field>
      </div>

      {palette?.length > 0 && (
        <Field label="Colours found in the photo" hint="Tap one to set it as the main colour.">
          <div className="rail">
            {palette.map((c, i) => (
              <button
                key={i} type="button"
                onClick={() => setForm({ ...form, colour_primary: c.name })}
                className="chip"
                style={form.colour_primary === c.name
                  ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : undefined}
              >
                <span className="h-3 w-3 rounded-full ring-1"
                      style={{ background: c.hex, '--tw-ring-color': 'var(--border)' }} />
                {c.name}
              </button>
            ))}
          </div>
        </Field>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Primary colour">
          <input className="input" value={form.colour_primary} onChange={set('colour_primary')} />
        </Field>
        <Field label="Secondary colour">
          <input className="input" value={form.colour_secondary}
                 onChange={set('colour_secondary')} />
        </Field>
      </div>

      <Field label="Pattern">
        <div className="rail">
          {(meta.patterns || []).map((p) => (
            <Chip key={p} active={form.pattern === p}
                  onClick={() => setForm({ ...form, pattern: form.pattern === p ? '' : p })}>
              {titleCase(p)}
            </Chip>
          ))}
        </div>
      </Field>

      {fits.length > 0 && (
        <Field label="Fit">
          <div className="rail">
            {fits.map((f) => (
              <Chip key={f} active={form.fit === f}
                    onClick={() => setForm({ ...form, fit: form.fit === f ? '' : f })}>
                {titleCase(f)}
              </Chip>
            ))}
          </div>
        </Field>
      )}

      <LevelPicker
        label="Warmth"
        hint="How it feels to wear. This is what the weather matching uses."
        options={warmths}
        value={form.warmth}
        onChange={(v) => setForm({ ...form, warmth: v })}
      />

      <LevelPicker
        label="Formality"
        options={formalities}
        value={form.formality}
        onChange={(v) => setForm({ ...form, formality: v })}
      />

      <Field label="Seasons">
        <div className="rail">
          {(meta.seasons || []).map((s) => (
            <Chip key={s} active={form.seasons.includes(s)} onClick={() => toggleSeason(s)}>
              {titleCase(s)}
            </Chip>
          ))}
        </div>
      </Field>

      <div className="flex flex-wrap gap-2">
        <Chip active={form.water_proof}
              onClick={() => setForm({ ...form, water_proof: !form.water_proof })}>
          <Icon name="drop" size={13} /> Waterproof
        </Chip>
        <Chip active={form.wind_proof}
              onClick={() => setForm({ ...form, wind_proof: !form.wind_proof })}>
          <Icon name="wind" size={13} /> Windproof
        </Chip>
      </div>

      <Field label="Tags" hint="Tap the common ones, or type your own separated by commas.">
        <div className="rail mb-2">
          {(meta.suggested_tags || []).map((t) => (
            <Chip key={t} active={tags.includes(t)} onClick={() => toggleTag(t)}>
              {titleCase(t)}
            </Chip>
          ))}
        </div>
        <input className="input" value={form.tags} onChange={set('tags')}
               placeholder="favourite, logo, work" />
      </Field>

      {!compact && (
        <Field label="Wash after (wears)"
               hint={`Default for ${titleCase(form.category)}: ${suggestedWash ?? '—'}`}>
          <input className="input" type="number" min="0" value={form.wash_after_wears}
                 onChange={set('wash_after_wears')} placeholder="use default" />
        </Field>
      )}

      {!compact && (
        <Field label="Notes">
          <textarea className="textarea" rows={2} value={form.notes} onChange={set('notes')} />
        </Field>
      )}
    </div>
  )
}
