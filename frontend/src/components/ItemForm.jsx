import { useId } from 'react'
import { api } from '../api.js'
import { useAsync } from '../hooks.js'
import { Chip, Field, Icon, titleCase } from './ui.jsx'

/**
 * Capitalise the first letter of every word as it is typed.
 *
 * Only the character after a space is touched, so anything already typed in the
 * middle of a word survives — "McQueen" and "adidas Originals" are not mangled.
 */
export const autoCapitalise = (value) =>
  String(value ?? '').replace(/(^|\s)(\S)/g, (_, gap, ch) => gap + ch.toUpperCase())

/**
 * Swatches read from the photo, offered as a shortcut for one colour field.
 *
 * They are only ever a suggestion — the primary and secondary colour fields are
 * what the app matches on, so the swatches fill those rather than standing on
 * their own.
 */
function PaletteRow({ palette, value, onPick }) {
  if (!palette?.length) return null
  return (
    <div className="rail mt-1.5">
      {palette.map((c, i) => {
        const on = (value || '').toLowerCase() === c.name.toLowerCase()
        return (
          <button
            key={i} type="button" onClick={() => onPick(autoCapitalise(c.name))}
            className="chip"
            style={on ? { borderColor: 'var(--accent)', color: 'var(--accent)' } : undefined}
            title={`${c.name} — ${Math.round(c.share * 100)}% of the photo`}
          >
            <span className="h-3 w-3 rounded-full ring-1"
                  style={{ background: c.hex, '--tw-ring-color': 'var(--border)' }} />
            {c.name}
          </button>
        )
      })}
    </div>
  )
}

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
  const beltRelevant = (meta.belt_categories || []).includes(form.category)
  // What has been typed into these fields before, offered as you type.
  // useAsync starts at null, and a destructuring default only covers undefined,
  // so the fallback has to be an explicit `|| {}`.
  const fieldValues = useAsync(() => api.fieldValues(), [])
  const known = fieldValues.data || {}
  const formalities = (meta.formality_levels || [])
  const suggestedWash = meta.default_wash_after_wears?.[form.category]

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
              <option key={c} value={c}>{titleCase(c)}</option>
            ))}
          </select>
        </Field>
        <Field
          label="Also counts as"
          hint="Optional. The main category above still decides the layer and how outfits are built — this just files it in more than one place."
        >
          <div className="rail">
            {(meta.categories || []).filter((c) => c !== form.category).map((c) => {
              const on = (form.categories || []).includes(c)
              return (
                <Chip key={c} active={on} onClick={() => setForm({
                  ...form,
                  categories: on
                    ? form.categories.filter((x) => x !== c)
                    : [...(form.categories || []), c],
                })}>
                  {titleCase(c)}
                </Chip>
              )
            })}
          </div>
        </Field>

        <TextField
          label="Subcategory" value={form.subcategory} options={known.subcategory}
          onChange={(v) => setForm({ ...form, subcategory: v })} placeholder="Crew Neck"
        />
        <TextField
          label="Brand" value={form.brand} options={known.brand}
          onChange={(v) => setForm({ ...form, brand: v })}
        />
        <TextField
          label="Material" value={form.material} options={known.material}
          onChange={(v) => setForm({ ...form, material: v })} placeholder="Merino Wool"
        />
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <TextField
            label="Primary colour" value={form.colour_primary} options={known.colour_primary}
            onChange={(v) => setForm({ ...form, colour_primary: v })}
          />
          <PaletteRow palette={palette} value={form.colour_primary}
                      onPick={(v) => setForm({ ...form, colour_primary: v })} />
        </div>
        <div>
          <TextField
            label="Secondary colour" value={form.colour_secondary}
            options={known.colour_secondary}
            onChange={(v) => setForm({ ...form, colour_secondary: v })}
          />
          <PaletteRow palette={palette} value={form.colour_secondary}
                      onPick={(v) => setForm({ ...form, colour_secondary: v })} />
        </div>
      </div>

      {palette?.length > 0 && (
        <p className="-mt-2 text-xs" style={{ color: 'var(--muted)' }}>
          The swatches are read from the photo as a starting point. What you leave in the two
          fields above is what outfit matching actually uses.
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
        hint="Condition of the garment itself, separate from whether it needs washing."
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
