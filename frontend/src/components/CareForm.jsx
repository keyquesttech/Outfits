import { useRef } from 'react'
import { Chip, Field, Icon, titleCase } from './ui.jsx'

export function careFormState(care = {}) {
  return {
    wash_temp: care?.wash_temp ?? '',
    wash_cycle: care?.wash_cycle ?? '',
    hand_wash_only: care?.hand_wash_only ?? false,
    do_not_wash: care?.do_not_wash ?? false,
    tumble_dry: care?.tumble_dry ?? '',
    iron_temp: care?.iron_temp ?? '',
    bleach: care?.bleach ?? '',
    dry_clean: care?.dry_clean ?? '',
    colour_group: care?.colour_group ?? '',
    notes: care?.notes ?? '',
  }
}

export function careFormPayload(form) {
  return {
    ...form,
    wash_temp: form.wash_temp === '' ? null : Number(form.wash_temp),
    wash_cycle: form.wash_cycle || null,
    tumble_dry: form.tumble_dry || null,
    iron_temp: form.iron_temp || null,
    bleach: form.bleach || null,
    dry_clean: form.dry_clean || null,
    colour_group: form.colour_group || null,
  }
}

/** True once the user has actually said something about how to wash it. */
export function careIsSet(form) {
  const blank = careFormState()
  return Object.keys(blank).some((k) => form[k] !== blank[k])
}

export default function CareForm({ form, setForm, meta, onScan, busy }) {
  const labelRef = useRef(null)
  const set = (k) => (e) =>
    setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const Sel = ({ k, options, label }) => (
    <Field label={label}>
      <select className="select" value={form[k]} onChange={set(k)}>
        <option value="">Not set</option>
        {options.map((o) => <option key={o} value={o}>{titleCase(o)}</option>)}
      </select>
    </Field>
  )

  return (
    <div className="space-y-4">
      {onScan && (
        <>
          <input ref={labelRef} type="file" accept="image/*" capture="environment"
                 className="hidden"
                 onChange={(e) => e.target.files?.[0] && onScan(e.target.files[0])} />
          <button className="card flex w-full items-center gap-3 border-dashed px-4 py-3"
                  onClick={() => labelRef.current?.click()} disabled={busy} type="button">
            <span className="rounded-full p-2"
                  style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
              <Icon name="sparkle" size={18} />
            </span>
            <span className="text-left">
              <span className="block text-sm font-semibold">Photograph the care label</span>
              <span className="block text-xs" style={{ color: 'var(--muted)' }}>
                AI reads the symbols and fills this in. Needs a provider set up.
              </span>
            </span>
          </button>
        </>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Field label="Wash temperature">
          <select className="select" value={form.wash_temp} onChange={set('wash_temp')}>
            <option value="">Not set</option>
            {[30, 40, 60, 95].map((t) => <option key={t} value={t}>{t}°C</option>)}
          </select>
        </Field>
        <Sel k="wash_cycle" label="Cycle" options={meta.wash_cycles || []} />
        <Sel k="tumble_dry" label="Tumble dry" options={meta.tumble_dry || []} />
        <Sel k="iron_temp" label="Iron" options={meta.iron_temp || []} />
        <Sel k="bleach" label="Bleach" options={meta.bleach || []} />
        <Sel k="dry_clean" label="Dry clean" options={meta.dry_clean || []} />
        <Sel k="colour_group" label="Laundry pile" options={meta.colour_groups || []} />
      </div>

      <div className="rail">
        <Chip active={form.hand_wash_only}
              onClick={() => setForm({ ...form, hand_wash_only: !form.hand_wash_only })}>
          Hand wash only
        </Chip>
        <Chip active={form.do_not_wash}
              onClick={() => setForm({ ...form, do_not_wash: !form.do_not_wash })}>
          Do not wash
        </Chip>
      </div>

      <Field label="Notes">
        <textarea className="textarea" rows={2} value={form.notes} onChange={set('notes')} />
      </Field>
    </div>
  )
}
