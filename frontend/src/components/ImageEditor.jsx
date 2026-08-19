import { useCallback, useEffect, useRef, useState } from 'react'
import { Icon, Modal, Spinner } from './ui.jsx'

const ASPECTS = [
  { key: 'free', label: 'Free', value: null },
  { key: 'portrait', label: '3:4', value: 3 / 4 },
  { key: 'square', label: '1:1', value: 1 },
  { key: 'landscape', label: '4:3', value: 4 / 3 },
]

// Cap the exported image. A modern phone photo is far larger than anything the
// app displays, and a huge canvas is what makes editing feel sluggish on a Pi.
const MAX_OUTPUT = 2000
const FULL_CROP = { x: 0, y: 0, w: 1, h: 1 }

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v))

/**
 * Render the chosen rotation and crop to a JPEG.
 *
 * The browser already applied any EXIF orientation when it decoded the image,
 * and a canvas export carries no EXIF, so the server's own orientation pass
 * sees an upright photo and leaves it alone — no double rotation.
 */
export async function renderEdited(image, rotation, crop, name) {
  const iw = image.naturalWidth
  const ih = image.naturalHeight
  const swapped = rotation % 180 !== 0
  const rw = swapped ? ih : iw
  const rh = swapped ? iw : ih

  let cw = Math.max(1, Math.round(crop.w * rw))
  let ch = Math.max(1, Math.round(crop.h * rh))
  const cx = Math.round(crop.x * rw)
  const cy = Math.round(crop.y * rh)

  const scale = Math.min(1, MAX_OUTPUT / Math.max(cw, ch))
  const canvas = document.createElement('canvas')
  canvas.width = Math.round(cw * scale)
  canvas.height = Math.round(ch * scale)

  const ctx = canvas.getContext('2d')
  ctx.imageSmoothingQuality = 'high'
  ctx.scale(scale, scale)
  ctx.translate(-cx, -cy)
  ctx.translate(rw / 2, rh / 2)
  ctx.rotate((rotation * Math.PI) / 180)
  ctx.drawImage(image, -iw / 2, -ih / 2)

  const blob = await new Promise((r) => canvas.toBlob(r, 'image/jpeg', 0.92))
  return new File([blob], name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
}

export default function ImageEditor({ open, file, onCancel, onApply }) {
  const [url, setUrl] = useState(null)
  const [image, setImage] = useState(null)
  const [rotation, setRotation] = useState(0)
  const [crop, setCrop] = useState(FULL_CROP)
  const [aspect, setAspect] = useState(null)
  const [busy, setBusy] = useState(false)
  const frameRef = useRef(null)
  const dragRef = useRef(null)

  useEffect(() => {
    if (!file) return undefined
    const objectUrl = URL.createObjectURL(file)
    setUrl(objectUrl)
    setRotation(0)
    setCrop(FULL_CROP)
    setAspect(null)
    const img = new Image()
    img.onload = () => setImage(img)
    img.src = objectUrl
    return () => URL.revokeObjectURL(objectUrl)
  }, [file])

  // Rotating changes what "the image" even looks like, so the crop starts over.
  const rotate = (delta) => {
    setRotation((r) => (r + delta + 360) % 360)
    setCrop(FULL_CROP)
  }

  const applyAspect = useCallback((ratio) => {
    setAspect(ratio)
    if (!ratio || !image) { setCrop(FULL_CROP); return }
    const swapped = rotation % 180 !== 0
    const rw = swapped ? image.naturalHeight : image.naturalWidth
    const rh = swapped ? image.naturalWidth : image.naturalHeight
    // Largest centred box of this ratio that fits the image.
    let w = 1
    let h = (rw * w) / (ratio * rh)
    if (h > 1) { h = 1; w = (ratio * rh * h) / rw }
    setCrop({ x: (1 - w) / 2, y: (1 - h) / 2, w, h })
  }, [image, rotation])

  const pointerPos = (e) => {
    const rect = frameRef.current.getBoundingClientRect()
    return {
      x: clamp((e.clientX - rect.left) / rect.width, 0, 1),
      y: clamp((e.clientY - rect.top) / rect.height, 0, 1),
    }
  }

  const startDrag = (mode, corner) => (e) => {
    e.preventDefault()
    e.stopPropagation()
    e.currentTarget.setPointerCapture?.(e.pointerId)
    dragRef.current = { mode, corner, start: pointerPos(e), crop }
  }

  const onPointerMove = (e) => {
    const drag = dragRef.current
    if (!drag) return
    const now = pointerPos(e)
    const dx = now.x - drag.start.x
    const dy = now.y - drag.start.y
    const base = drag.crop

    if (drag.mode === 'move') {
      setCrop({
        ...base,
        x: clamp(base.x + dx, 0, 1 - base.w),
        y: clamp(base.y + dy, 0, 1 - base.h),
      })
      return
    }

    let { x, y, w, h } = base
    const right = base.x + base.w
    const bottom = base.y + base.h
    if (drag.corner.includes('w')) { x = clamp(base.x + dx, 0, right - 0.05); w = right - x }
    if (drag.corner.includes('e')) { w = clamp(base.w + dx, 0.05, 1 - base.x) }
    if (drag.corner.includes('n')) { y = clamp(base.y + dy, 0, bottom - 0.05); h = bottom - y }
    if (drag.corner.includes('s')) { h = clamp(base.h + dy, 0.05, 1 - base.y) }

    if (aspect && image) {
      // Keep the locked ratio in the image's real pixels, not the box on screen.
      const swapped = rotation % 180 !== 0
      const rw = swapped ? image.naturalHeight : image.naturalWidth
      const rh = swapped ? image.naturalWidth : image.naturalHeight
      h = (rw * w) / (aspect * rh)
      if (y + h > 1) { h = 1 - y; w = (aspect * rh * h) / rw }
      if (drag.corner.includes('n')) y = bottom - h
    }
    setCrop({ x, y, w, h })
  }

  const endDrag = () => { dragRef.current = null }

  const apply = async () => {
    if (!image) return
    setBusy(true)
    try {
      onApply(await renderEdited(image, rotation, crop, file.name))
    } finally {
      setBusy(false)
    }
  }

  const swapped = rotation % 180 !== 0
  const frameRatio = image
    ? (swapped ? image.naturalHeight / image.naturalWidth : image.naturalWidth / image.naturalHeight)
    : 1
  const untouched = rotation === 0 && crop.w === 1 && crop.h === 1

  const handles = ['nw', 'ne', 'sw', 'se']

  return (
    <Modal
      open={open} onClose={onCancel} wide title="Rotate and crop"
      footer={
        <>
          <button className="btn" onClick={onCancel} disabled={busy}>Cancel</button>
          <button className="btn btn-primary" onClick={apply} disabled={busy || !image}>
            {busy ? <Spinner size={15} /> : <Icon name="check" size={15} />}
            {untouched ? 'Use as is' : 'Apply'}
          </button>
        </>
      }
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn" onClick={() => rotate(-90)} disabled={!image}>
            <Icon name="rotateLeft" size={16} /> Left
          </button>
          <button className="btn" onClick={() => rotate(90)} disabled={!image}>
            <Icon name="rotateRight" size={16} /> Right
          </button>
          <span className="mx-1 hidden h-5 w-px sm:block" style={{ background: 'var(--border)' }} />
          {ASPECTS.map((a) => (
            <button
              key={a.key}
              className={`chip ${aspect === a.value ? 'chip-on' : ''}`}
              onClick={() => applyAspect(a.value)}
              disabled={!image}
            >
              {a.label}
            </button>
          ))}
          <button className="btn btn-ghost ml-auto"
                  onClick={() => { setRotation(0); setCrop(FULL_CROP); setAspect(null) }}
                  disabled={!image || untouched}>
            Reset
          </button>
        </div>

        <div className="flex justify-center">
          <div
            ref={frameRef}
            className="relative w-full touch-none select-none overflow-hidden rounded-xl"
            style={{
              maxWidth: 'min(100%, 34rem)',
              aspectRatio: String(frameRatio),
              background: 'var(--surface-2)',
            }}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
          >
            {url && (
              <img
                src={url} alt="" draggable={false}
                className="pointer-events-none absolute inset-0 h-full w-full object-contain"
                style={{ transform: `rotate(${rotation}deg)`, transformOrigin: 'center',
                         scale: swapped ? `${1 / frameRatio}` : '1' }}
              />
            )}

            {/* Everything outside the crop box is dimmed. */}
            <div className="pointer-events-none absolute inset-0"
                 style={{
                   background: 'rgb(0 0 0 / 0.55)',
                   clipPath: `polygon(0% 0%, 0% 100%, ${crop.x * 100}% 100%, ${crop.x * 100}% ${crop.y * 100}%, ${(crop.x + crop.w) * 100}% ${crop.y * 100}%, ${(crop.x + crop.w) * 100}% ${(crop.y + crop.h) * 100}%, ${crop.x * 100}% ${(crop.y + crop.h) * 100}%, ${crop.x * 100}% 100%, 100% 100%, 100% 0%)`,
                 }} />

            <div
              className="absolute cursor-move"
              style={{
                left: `${crop.x * 100}%`, top: `${crop.y * 100}%`,
                width: `${crop.w * 100}%`, height: `${crop.h * 100}%`,
                outline: '2px solid var(--accent)',
              }}
              onPointerDown={startDrag('move')}
            >
              {handles.map((corner) => (
                <span
                  key={corner}
                  onPointerDown={startDrag('resize', corner)}
                  className="absolute h-6 w-6 rounded-full border-2"
                  style={{
                    background: 'var(--accent)', borderColor: '#fff',
                    top: corner[0] === 'n' ? -12 : undefined,
                    bottom: corner[0] === 's' ? -12 : undefined,
                    left: corner[1] === 'w' ? -12 : undefined,
                    right: corner[1] === 'e' ? -12 : undefined,
                    cursor: `${corner}-resize`,
                    touchAction: 'none',
                  }}
                />
              ))}
            </div>
          </div>
        </div>

        <p className="text-center text-xs" style={{ color: 'var(--muted)' }}>
          Drag inside the box to move it, or the corners to resize. Rotating starts the
          crop again.
        </p>
      </div>
    </Modal>
  )
}
