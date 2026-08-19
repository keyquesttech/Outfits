import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, Link } from 'react-router-dom'
import { api } from '../api.js'
import { useMeta } from '../App.jsx'
import { useAsync } from '../hooks.js'
import { ItemPhoto } from '../components/ItemCard.jsx'
import ItemForm, {
  itemFormPayload, itemFormState, nearestOption, warmthOptions,
} from '../components/ItemForm.jsx'
import ImageEditor from '../components/ImageEditor.jsx'
import {
  Chip, ErrorNote, Field, Icon, Modal, Section, Spinner, StatusPill,
  titleCase, useConfirm, useToast,
} from '../components/ui.jsx'

function CareSheet({ open, onClose, item, onSaved }) {
  const meta = useMeta()
  const toast = useToast()
  const [form, setForm] = useState(() => ({
    wash_temp: item.care?.wash_temp ?? '',
    wash_cycle: item.care?.wash_cycle ?? '',
    hand_wash_only: item.care?.hand_wash_only ?? false,
    do_not_wash: item.care?.do_not_wash ?? false,
    tumble_dry: item.care?.tumble_dry ?? '',
    iron_temp: item.care?.iron_temp ?? '',
    bleach: item.care?.bleach ?? '',
    dry_clean: item.care?.dry_clean ?? '',
    colour_group: item.care?.colour_group ?? '',
    notes: item.care?.notes ?? '',
  }))
  const [busy, setBusy] = useState(false)
  const labelRef = useRef(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })

  const save = async () => {
    setBusy(true)
    try {
      await api.putCare(item.id, {
        ...form,
        wash_temp: form.wash_temp === '' ? null : Number(form.wash_temp),
        wash_cycle: form.wash_cycle || null,
        tumble_dry: form.tumble_dry || null,
        iron_temp: form.iron_temp || null,
        bleach: form.bleach || null,
        dry_clean: form.dry_clean || null,
        colour_group: form.colour_group || null,
      })
      toast('Care instructions saved.', 'success')
      onSaved()
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  const scanLabel = async (file) => {
    setBusy(true)
    try {
      await api.careLabel(item.id, file)
      toast('Reading the care label. This takes a few seconds.', 'success')
      setTimeout(onSaved, 6000)
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  const Sel = ({ k, options, label }) => (
    <Field label={label}>
      <select className="select" value={form[k]} onChange={set(k)}>
        <option value="">Not set</option>
        {options.map((o) => <option key={o} value={o}>{titleCase(o)}</option>)}
      </select>
    </Field>
  )

  return (
    <Modal open={open} onClose={onClose} title="Care instructions" wide
      footer={<>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save
        </button>
      </>}>
      <div className="space-y-4">
        <input ref={labelRef} type="file" accept="image/*" capture="environment" className="hidden"
               onChange={(e) => e.target.files?.[0] && scanLabel(e.target.files[0])} />
        <button className="card flex w-full items-center gap-3 border-dashed px-4 py-3"
                onClick={() => labelRef.current?.click()} disabled={busy}>
          <span className="rounded-full p-2" style={{ background: 'var(--accent-soft)', color: 'var(--accent)' }}>
            <Icon name="sparkle" size={18} />
          </span>
          <span className="text-left">
            <span className="block text-sm font-semibold">Photograph the care label</span>
            <span className="block text-xs" style={{ color: 'var(--muted)' }}>
              AI reads the symbols and fills this in. Needs a provider set up.
            </span>
          </span>
        </button>

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

        <div className="flex flex-wrap gap-2">
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
    </Modal>
  )
}

function EditSheet({ open, onClose, item, onSaved }) {
  const meta = useMeta()
  const toast = useToast()
  const [form, setForm] = useState(() => itemFormState(item))
  const [busy, setBusy] = useState(false)

  const save = async () => {
    setBusy(true)
    try {
      await api.updateItem(item.id, itemFormPayload(form))
      toast('Saved.', 'success')
      onSaved()
      onClose()
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  return (
    <Modal open={open} onClose={onClose} title="Edit item" wide
      footer={<>
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={busy}>
          {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />} Save
        </button>
      </>}>
      <ItemForm form={form} setForm={setForm} meta={meta} palette={item.palette} />
    </Modal>
  )
}

const COMFORT_LABEL = { '-1': 'too cold', 0: 'just right', 1: 'too hot' }

export default function ItemDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const meta = useMeta()
  const { data: item, loading, error, reload } = useAsync(() => api.item(id), [id])
  const [editing, setEditing] = useState(false)
  const [caring, setCaring] = useState(false)
  const [busy, setBusy] = useState(false)
  const [allWorn, setAllWorn] = useState(false)
  const [pendingPhoto, setPendingPhoto] = useState(null)
  const photoRef = useRef(null)

  useEffect(() => { window.scrollTo(0, 0) }, [id])

  if (loading) return <div className="skeleton h-96 rounded-2xl" />
  if (error) return <ErrorNote error={error} onRetry={reload} />
  if (!item) return null

  const act = async (fn, message) => {
    setBusy(true)
    try { await fn(); if (message) toast(message, 'success'); await reload(true) }
    catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  const removeWear = async (w) => {
    const ok = await confirm({
      title: 'Delete this wear?',
      body: `The wear logged on ${w.worn_on} will be removed.`,
      detail: 'Wear counts go back down, including progress towards the next wash.',
    })
    if (!ok) return
    setBusy(true)
    try {
      await api.deleteWear(w.id)
      toast('Wear deleted and counters reverted.', 'success')
      await reload(true)
    } catch (e) { toast(e.message, 'error') } finally { setBusy(false) }
  }

  const remove = async () => {
    const ok = await confirm({
      title: 'Remove from wardrobe?',
      body: `“${item.name}” will no longer appear in your wardrobe.`,
      detail: 'It stays in your history, so past wears and analytics are unaffected.',
      confirmLabel: 'Remove',
    })
    if (!ok) return
    await api.deleteItem(item.id)
    toast('Removed from the wardrobe.', 'success')
    navigate('/wardrobe')
  }

  // A belt or a ring contributes no insulation at all, so calling it "Cold" is
  // nonsense — those categories say so plainly instead of picking a band.
  const addsWarmth = (meta.default_warmth?.[item.category] ?? 5) > 0
  const warmthLabel = addsWarmth
    ? (nearestOption(warmthOptions(meta, item.category), item.warmth)?.label ?? '—')
    : 'None'
  const formalityLabel =
    nearestOption(meta.formality_levels || [], item.formality)?.label ?? '—'

  const care = item.care
  const careBits = care ? [
    care.do_not_wash ? 'do not wash' : null,
    care.hand_wash_only ? 'hand wash only' : null,
    care.wash_temp ? `${care.wash_temp}°C` : null,
    care.wash_cycle ? `${care.wash_cycle} cycle` : null,
    care.tumble_dry ? `tumble ${care.tumble_dry}` : null,
    care.iron_temp ? `iron ${care.iron_temp}` : null,
    care.dry_clean && care.dry_clean !== 'no' ? 'dry clean' : null,
  ].filter(Boolean) : []

  return (
    <div className="space-y-5">
      <button className="btn btn-ghost -ml-2" onClick={() => navigate(-1)}>
        <Icon name="back" size={16} /> Back
      </button>

      <div className="grid gap-5 md:grid-cols-[minmax(0,22rem)_1fr]">
        <div className="space-y-3">
          <div className="card aspect-[3/4] overflow-hidden">
            <ItemPhoto item={item} rounded="" full />
          </div>
          {/* Straight into the editor, so a sideways photo can be fixed before it lands. */}
          <input ref={photoRef} type="file" accept="image/*" capture="environment" className="hidden"
                 onChange={(e) => {
                   const picked = e.target.files?.[0]
                   if (picked) setPendingPhoto(picked)
                   e.target.value = ''
                 }} />
          <div className="flex gap-2">
            <button className="btn flex-1" onClick={() => photoRef.current?.click()} disabled={busy}>
              <Icon name="camera" size={15} /> Replace photo
            </button>
            <button className="btn" onClick={() => act(() => api.analyse(item.id), 'AI is re-tagging this item.')}
                    disabled={busy} title="Re-run AI tagging">
              <Icon name="sparkle" size={15} />
            </button>
          </div>
          {item.palette?.length > 0 && (
            <div className="card px-3.5 py-3">
              <p className="label">Colours read from the photo</p>
              <div className="mt-2 space-y-1.5">
                {item.palette.map((c, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="h-4 w-4 rounded-full ring-1" style={{ background: c.hex, '--tw-ring-color': 'var(--border)' }} />
                    <span className="font-medium">{c.name}</span>
                    <span className="tabular-nums" style={{ color: 'var(--muted)' }}>{c.hex}</span>
                    <span className="ml-auto tabular-nums" style={{ color: 'var(--muted)' }}>
                      {Math.round(c.share * 100)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">{item.name}</h1>
              <StatusPill status={item.status} size="md" />
            </div>
            <p className="mt-1 text-sm" style={{ color: 'var(--muted)' }}>
              {titleCase(item.category)}
              {item.fit ? ` · ${titleCase(item.fit)} fit` : ''}
              {item.subcategory ? ` · ${item.subcategory}` : ''}
              {item.brand ? ` · ${item.brand}` : ''}
              {item.material ? ` · ${item.material}` : ''}
            </p>
            {item.ai_provider && (
              <p className="mt-1 text-xs" style={{ color: 'var(--muted)' }}>
                Tagged by {item.ai_provider}
                {item.ai_confidence != null && ` · ${Math.round(item.ai_confidence * 100)}% confident`}
              </p>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" onClick={() => setEditing(true)}>
              <Icon name="edit" size={15} /> Edit
            </button>
            <button className="btn" disabled={busy}
                    onClick={() => act(() => api.logWear({ item_ids: [item.id] }), 'Wear logged.')}>
              <Icon name="check" size={15} /> Log a wear
            </button>
            {item.launderable && (
              <button className="btn" disabled={busy}
                      onClick={() => act(() => api.wash({ item_ids: [item.id] }), 'Marked as washed.')}>
                <Icon name="drop" size={15} /> Mark washed
              </button>
            )}
            <button className="btn btn-ghost" onClick={remove}><Icon name="trash" size={15} /> Remove</button>
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <div className="card px-3 py-2.5">
              <p className="label">Worn</p>
              <p className="mt-0.5 text-xl font-bold tabular-nums">{item.total_wears}</p>
              {item.last_worn && <p className="text-[0.7rem]" style={{ color: 'var(--muted)' }}>last {item.last_worn}</p>}
            </div>
            <div className="card px-3 py-2.5">
              <p className="label">Since wash</p>
              <p className="mt-0.5 text-xl font-bold tabular-nums">
                {item.launderable ? `${item.wears_since_wash}/${item.wash_threshold}` : '—'}
              </p>
              {item.launderable && (
                <p className="text-[0.7rem]" style={{ color: item.needs_wash ? 'var(--bad)' : 'var(--muted)' }}>
                  {item.needs_wash ? 'wash it' : `${item.wears_left} left`}
                </p>
              )}
            </div>
            <div className="card px-3 py-2.5">
              <p className="label">Warmth</p>
              <p className="mt-0.5 text-xl font-bold">{warmthLabel}</p>
              <p className="text-[0.7rem]" style={{ color: 'var(--muted)' }}>
                {addsWarmth ? `formality · ${formalityLabel}` : `adds no warmth · ${formalityLabel}`}
              </p>
            </div>
          </div>

          <Section title="Status">
            <div className="rail">
              {(meta.statuses || []).map((s) => (
                <Chip key={s} active={item.status === s} disabled={busy}
                      onClick={() => act(() => api.setStatus(item.id, s))}>
                  {titleCase(s)}
                </Chip>
              ))}
            </div>
            <p className="text-xs" style={{ color: 'var(--muted)' }}>
              Marking it clean resets the wear counter. “Airing” keeps it out of the wash pile without resetting.
            </p>
          </Section>

          <Section
            title="Care"
            action={<button className="btn btn-ghost" onClick={() => setCaring(true)}><Icon name="edit" size={14} /> Edit</button>}
          >
            <div className="card px-4 py-3">
              {careBits.length ? (
                <div className="flex flex-wrap gap-1.5">
                  {careBits.map((b, i) => (
                    <span key={i} className="rounded-full px-2 py-0.5 text-xs font-medium"
                          style={{ background: 'var(--surface-2)', color: 'var(--muted)' }}>{b}</span>
                  ))}
                </div>
              ) : (
                <p className="text-sm" style={{ color: 'var(--muted)' }}>
                  No care instructions yet. Add them so laundry loads get grouped correctly.
                </p>
              )}
              {care?.raw_symbols?.length > 0 && (
                <p className="mt-2 text-xs" style={{ color: 'var(--muted)' }}>
                  Symbols read: {care.raw_symbols.join(', ')}
                </p>
              )}
            </div>
          </Section>

          {(item.seasons?.length > 0 || item.tags?.length > 0 || item.water_proof || item.wind_proof) && (
            <div className="flex flex-wrap gap-1.5">
              {item.water_proof && <span className="chip">Waterproof</span>}
              {item.wind_proof && <span className="chip">Windproof</span>}
              {item.seasons?.map((s) => <span key={s} className="chip">{titleCase(s)}</span>)}
              {item.tags?.map((t) => <span key={t} className="chip">#{t}</span>)}
            </div>
          )}

          {item.notes && (
            <div className="card px-4 py-3 text-sm" style={{ color: 'var(--muted)' }}>{item.notes}</div>
          )}

          <Section
            title="Recently worn"
            action={item.worn_history?.length > 6 && (
              <button className="btn btn-ghost" onClick={() => setAllWorn((v) => !v)}>
                {allWorn ? 'Show fewer' : `Show all ${item.worn_history.length}`}
              </button>
            )}
          >
            {item.worn_history?.length ? (
              <div className="card divide-y" style={{ borderColor: 'var(--border)' }}>
                {(allWorn ? item.worn_history : item.worn_history.slice(0, 6)).map((w) => (
                  <div key={w.id} className="flex items-center gap-3 px-3.5 py-2 text-sm">
                    <span className="tabular-nums">{w.worn_on}</span>
                    {w.occasion && (
                      <span className="truncate" style={{ color: 'var(--muted)' }}>{w.occasion}</span>
                    )}
                    <span className="ml-auto flex shrink-0 items-center gap-3">
                      {w.comfort_rating != null && (
                        <span className="text-xs" style={{ color: 'var(--muted)' }}>
                          {COMFORT_LABEL[w.comfort_rating]}
                        </span>
                      )}
                      {w.apparent_c != null && (
                        <span className="tabular-nums text-xs" style={{ color: 'var(--muted)' }}>
                          felt {Math.round(w.apparent_c)}°
                        </span>
                      )}
                      <button
                        className="btn btn-ghost !p-1" title="Delete this wear"
                        disabled={busy} onClick={() => removeWear(w)}
                      >
                        <Icon name="trash" size={14} />
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm" style={{ color: 'var(--muted)' }}>
                Not worn yet. Log a wear and it will appear here.
              </p>
            )}
            {item.worn_history?.length > 0 && (
              <p className="text-xs" style={{ color: 'var(--muted)' }}>
                Deleting a wear puts the counters back where they were, so it also
                undoes progress towards the next wash.
              </p>
            )}
          </Section>

          {item.wash_history?.length > 0 && (
            <Section title="Wash history">
              <div className="card divide-y" style={{ borderColor: 'var(--border)' }}>
                {item.wash_history.slice(0, 6).map((w) => (
                  <div key={w.id} className="flex items-center gap-3 px-3.5 py-2 text-sm">
                    <span className="tabular-nums">{w.washed_on}</span>
                    <span style={{ color: 'var(--muted)' }}>
                      {[w.program, w.temp_c ? `${w.temp_c}°C` : null].filter(Boolean).join(' · ')}
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}
        </div>
      </div>

      {pendingPhoto && (
        <ImageEditor
          open file={pendingPhoto}
          onCancel={() => setPendingPhoto(null)}
          onApply={(edited) => {
            setPendingPhoto(null)
            act(() => api.replacePhoto(item.id, edited), 'Photo replaced.')
          }}
        />
      )}
      {editing && <EditSheet open onClose={() => setEditing(false)} item={item} onSaved={() => reload(true)} />}
      {caring && <CareSheet open onClose={() => setCaring(false)} item={item} onSaved={() => reload(true)} />}
    </div>
  )
}
