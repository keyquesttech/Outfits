import { useId, useState } from 'react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import ColourField from './ColourField.jsx'
import { Chip, Field, Icon, MultiSelect, titleCase } from './ui.jsx'

/**
 * Capitalise the first letter of every word as it is typed.
 *
 * Only the character after a space is touched, so anything already typed in the
 * middle of a word survives — "McQueen" and "adidas Originals" are not mangled.
 */
export const autoCapitalise = (value) =>
  String(value ?? '').replace(/(^|\s)(\S)/g, (_, gap, ch) => gap + ch.toUpperCase())

/** Text input that capitalises words and offers what has been typed before. */
function TextField({ label, hint, value, onChange, options = [], capitalise = true, ...rest }) {
  const listId = useId()
  const hasOptions = options.length > 0
  return (
    <Field label={label} hint={hint}>
      <input
        className="input"
        value={value}
        list={hasOptions ? listId : undefined}
        autoCapitalize={capitalise ? 'words' : 'off'}
        autoComplete="off"
        onChange={(e) => onChange(capitalise ? autoCapitalise(e.target.value) : e.target.value)}
        {...rest}
      />
      {hasOptions && (
        <datalist id={listId}>
          {options.map((o) => <option key={o} value={o} />)}
        </datalist>
      )}
    </Field>
  )
}

/**
 * Free-text input with the app's own dropdown of known values.
 *
 * Brand, material and subcategory used the browser's datalist, which renders
 * differently in every browser and nothing like the Category select beside
 * them. This is the same affordance as the rest of the form: a styled panel of
 * everything typed before, filtered as you type, that still accepts a value it
 * has never seen.
 */
function ComboField({ label, hint, value, onChange, options = [], placeholder }) {
  const [open, setOpen] = useState(false)
  const query = String(value || '').trim().toLowerCase()
  // Filter while typing, but a field already holding a complete known value is
  // being browsed, not typed — show everything, with the current one marked.
  const settled = !query || options.some((o) => o.toLowerCase() === query)
  const shown = settled
    ? options
    : options.filter((o) => o.toLowerCase().includes(query))
  const pick = (v) => { onChange(v); setOpen(false) }

  return (
    <Field label={label} hint={hint}>
      <div className="relative">
        <input
          className="input pr-9" value={value} placeholder={placeholder}
          autoCapitalize="words" autoComplete="off"
          onChange={(e) => { onChange(autoCapitalise(e.target.value)); setOpen(true) }}
        />
        {options.length > 0 && (
          <button
            type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open}
            className="absolute right-1 top-1/2 -translate-y-1/2 rounded-lg p-1.5"
            style={{ color: 'var(--muted)' }}
            aria-label={`Show known values for ${label}`}
          >
            <Icon name="chevron" size={16}
                  style={{ transform: open ? 'rotate(180deg)' : 'none' }} />
          </button>
        )}
      </div>
      {open && shown.length > 0 && (
        <div className="card mt-1.5 max-h-48 overflow-y-auto p-1">
          {shown.map((o) => {
            const on = o.toLowerCase() === query
            return (
              <button
                key={o} type="button" onClick={() => pick(o)}
                className="flex w-full items-center rounded-lg px-2.5 py-1.5 text-left text-sm"
                style={on
                  ? { background: 'var(--accent-soft)', color: 'var(--accent)', fontWeight: 600 }
                  : undefined}
              >
                {o}
              </button>
            )
          })}
        </div>
      )}
    </Field>
  )
}

/** Initial form state for an item, used by both editing and first-time tagging. */
export function itemFormState(item = {}) {
  return {
    name: item.name || '',
    category: item.category || 'top',
    categories: item.extra_categories || [],
    subcategory: item.subcategory || '',
    brand: item.brand || '',
    material: item.material || '',
    pattern: item.pattern || '',
    fit: item.fit || '',
    takes_belt: item.takes_belt ?? true,
    damage: item.damage || 'none',
    colour_primary: item.colour_primary || '',
    colour_secondary: item.colour_secondary || '',
    warmth: item.warmth ?? 5,
    formality: item.formality ?? 3,
    seasons: item.seasons || [],
    wind_proof: !!item.wind_proof,
    water_proof: !!item.water_proof,
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
    tags: parseTags(form.tags),
    categories: (form.categories || []).filter((c) => c !== form.category),
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

/** Three-across chooser. `active` decides which option is highlighted. */
function OptionRow({ label, hint, options, isActive, onChange }) {
  return (
    <Field label={label} hint={hint}>
      <div className="grid grid-cols-3 gap-2">
        {options.map((o) => {
          const on = isActive(o)
          return (
            <button
              key={o.key} type="button" onClick={() => onChange(o)}
              className="card px-2 py-2 text-center"
              style={on
                ? { borderColor: 'var(--accent)', background: 'var(--accent-soft)' }
                : undefined}
            >
              <span className="block text-sm font-semibold"
                    style={on ? { color: 'var(--accent)' } : undefined}>
                {o.label}
              </span>
              <span className="block text-2xs leading-tight"
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
              <span className="block text-2xs leading-tight"
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
  const beltRelevant = (meta.belt_categories || []).includes(form.category)
  // What has been typed into these fields before, offered as you type.
  // useAsync starts at null, and a destructuring default only covers undefined,
  // so the fallback has to be an explicit `|| {}`.
  const fieldValues = useAsync(() => api.fieldValues(), [])
  const known = fieldValues.data || {}
  const formalities = (meta.formality_levels || [])

  return (
    <div className="space-y-4">
      <TextField
        label="Name" value={form.name} options={known.name}
        onChange={(v) => setForm({ ...form, name: v })}
        placeholder="Navy Merino Crew Jumper" autoFocus
      />

      <div className="grid grid-cols-2 gap-3">
        <Field label="Category">
          <select className="select" value={form.category} onChange={set('category')}>
            {(meta.categories || []).map((c) => (
              <option key={c} value={c}>{meta.category_labels?.[c] || titleCase(c)}</option>
            ))}
            {/* An item can outlive the category it was filed under. Keep it
                selectable rather than silently snapping it to the first entry. */}
            {form.category && !(meta.categories || []).includes(form.category) && (
              <option value={form.category}>{titleCase(form.category)} (removed)</option>
            )}
          </select>
        </Field>
        <MultiSelect
          label="Also counts as"
          hint="Optional. The main category above still decides the layer and how outfits are built — this just files it in more than one place."
          options={(meta.categories || [])
            .filter((c) => c !== form.category)
            .map((c) => ({ value: c, label: meta.category_labels?.[c] || titleCase(c) }))}
          selected={form.categories || []}
          onChange={(categories) => setForm({ ...form, categories })}
          empty="Nothing else"
        />

        <ComboField
          label="Subcategory" value={form.subcategory} options={known.subcategory || []}
          onChange={(v) => setForm({ ...form, subcategory: v })} placeholder="Crew Neck"
        />
        <ComboField
          label="Brand" value={form.brand} options={known.brand || []}
          onChange={(v) => setForm({ ...form, brand: v })}
        />
        <ComboField
          label="Material" value={form.material} options={known.material || []}
          onChange={(v) => setForm({ ...form, material: v })} placeholder="Merino Wool"
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <ColourField
          label="Primary colour" meta={meta} palette={palette}
          value={form.colour_primary} options={known.colour_primary}
          onChange={(v) => setForm({ ...form, colour_primary: v })}
        />
        <ColourField
          label="Secondary colour"
          hint="Only if a second colour is really part of the garment — a contrast panel, not a small print."
          meta={meta} palette={palette} allowNone noneLabel="No second colour"
          value={form.colour_secondary} options={known.colour_secondary}
          onChange={(v) => setForm({ ...form, colour_secondary: v })}
        />
      </div>

      {palette?.length > 0 && (
        <p className="-mt-2 text-xs" style={{ color: 'var(--muted)' }}>
          The swatches are read from the photo as a starting point, with the next-closest
          reading offered after "or". What you leave in the two fields above is what outfit
          matching actually uses.
        </p>
      )}

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

      <OptionRow
        label="Damage"
        hint="The garment's condition — a mark, a loose thread, a hole."
        options={meta.damage_levels || []}
        isActive={(o) => (form.damage || 'none') === o.key}
        onChange={(o) => setForm({ ...form, damage: o.key })}
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

      {beltRelevant && (
        <Field
          label="Belt"
          hint="Turn this off for elasticated or drawstring bottoms — the outfit builder will not put a belt with them."
        >
          <Chip active={form.takes_belt}
                onClick={() => setForm({ ...form, takes_belt: !form.takes_belt })}>
            {form.takes_belt ? 'Takes a belt' : 'No belt'}
          </Chip>
        </Field>
      )}

      <div className="rail">
        <Chip active={form.water_proof}
              onClick={() => setForm({ ...form, water_proof: !form.water_proof })}>
          <Icon name="drop" size={14} /> Waterproof
        </Chip>
        <Chip active={form.wind_proof}
              onClick={() => setForm({ ...form, wind_proof: !form.wind_proof })}>
          <Icon name="wind" size={14} /> Windproof
        </Chip>
      </div>

      <Field
        label="Tags"
        hint="Occasion tags do real work: tag trousers gym, date and the builder uses them for those occasions and leaves them out of the rest. Untagged items stay available everywhere."
      >
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
        <Field label="Notes">
          <textarea className="textarea" rows={2} value={form.notes} onChange={set('notes')} />
        </Field>
      )}
    </div>
  )
}
