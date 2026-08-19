import { Chip, Field, Icon, Palette, titleCase } from './ui.jsx'

/** Initial form state for an item, used by both editing and first-time tagging. */
export function itemFormState(item = {}) {
  return {
    name: item.name || '',
    category: item.category || 'top',
    subcategory: item.subcategory || '',
    brand: item.brand || '',
    material: item.material || '',
    pattern: item.pattern || '',
    colour_primary: item.colour_primary || '',
    colour_secondary: item.colour_secondary || '',
    warmth: item.warmth ?? 5,
    formality: item.formality ?? 3,
    seasons: item.seasons || [],
    wind_proof: !!item.wind_proof,
    water_proof: !!item.water_proof,
    price: item.price ?? '',
    purchase_date: item.purchase_date || '',
    wash_after_wears: item.wash_after_wears ?? '',
    notes: item.notes || '',
    tags: (item.tags || []).join(', '),
  }
}

/** Convert form state into an API payload. */
export function itemFormPayload(form) {
  return {
    ...form,
    price: form.price === '' ? null : Number(form.price),
    warmth: Number(form.warmth),
    formality: Number(form.formality),
    wash_after_wears: form.wash_after_wears === '' ? null : Number(form.wash_after_wears),
    tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
  }
}

const PATTERNS = ['plain', 'stripe', 'check', 'floral', 'print', 'knit', 'herringbone']

export default function ItemForm({ form, setForm, meta, palette, compact = false }) {
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const toggleSeason = (s) =>
    setForm({
      ...form,
      seasons: form.seasons.includes(s)
        ? form.seasons.filter((x) => x !== s)
        : [...form.seasons, s],
    })

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
          <div className="flex flex-wrap gap-2">
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
        <div className="flex flex-wrap gap-2">
          {PATTERNS.map((p) => (
            <Chip key={p} active={form.pattern === p}
                  onClick={() => setForm({ ...form, pattern: form.pattern === p ? '' : p })}>
              {titleCase(p)}
            </Chip>
          ))}
        </div>
      </Field>

      <Field label={`Warmth — ${form.warmth}/10`}
             hint="How much insulation it gives, not how it looks. This is what weather matching uses.">
        <input type="range" min="0" max="10" value={form.warmth} onChange={set('warmth')}
               className="w-full" style={{ accentColor: 'var(--accent)' }} />
      </Field>

      <Field label={`Formality — ${form.formality}/5`} hint="1 loungewear, 3 work, 5 black tie.">
        <input type="range" min="1" max="5" value={form.formality} onChange={set('formality')}
               className="w-full" style={{ accentColor: 'var(--accent)' }} />
      </Field>

      <Field label="Seasons">
        <div className="flex flex-wrap gap-2">
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

      {!compact && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Wash after (wears)"
                 hint={`Default for ${titleCase(form.category)}: ${suggestedWash ?? '—'}`}>
            <input className="input" type="number" min="0" value={form.wash_after_wears}
                   onChange={set('wash_after_wears')} placeholder="use default" />
          </Field>
          <Field label="Price (£)">
            <input className="input" type="number" step="0.01" value={form.price}
                   onChange={set('price')} />
          </Field>
          <Field label="Bought on">
            <input className="input" type="date" value={form.purchase_date}
                   onChange={set('purchase_date')} />
          </Field>
          <Field label="Tags" hint="Comma separated">
            <input className="input" value={form.tags} onChange={set('tags')} />
          </Field>
        </div>
      )}

      {!compact && (
        <Field label="Notes">
          <textarea className="textarea" rows={2} value={form.notes} onChange={set('notes')} />
        </Field>
      )}
    </div>
  )
}
