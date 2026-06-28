import { useRef, useState } from 'react'
import { uploadPhotos } from '../api'

export default function UploadPanel({ trips, onUploaded }) {
  const [trip, setTrip] = useState('')
  const [newTrip, setNewTrip] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const inputRef = useRef(null)

  const tripNames = trips.map((t) => t.name)
  const effectiveTrip = trip === '__new__' ? newTrip.trim() : trip

  async function handleFiles(fileList) {
    const files = Array.from(fileList || [])
    if (files.length === 0) return
    if (!effectiveTrip) {
      setMsg({ type: 'error', text: 'Pick or name a trip first.' })
      return
    }
    setBusy(true)
    setMsg({ type: 'info', text: `Uploading ${files.length} photo(s)\u2026` })
    try {
      const res = await uploadPhotos(files, effectiveTrip)
      const rej = res.rejected?.length ? `, ${res.rejected.length} rejected` : ''
      setMsg({ type: 'ok', text: `Uploaded ${res.saved.length} to "${res.trip}"${rej}. Ingesting\u2026` })
      onUploaded?.(res)
    } catch (e) {
      setMsg({ type: 'error', text: e.message })
    } finally {
      setBusy(false)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <div className="upload-panel">
      <div className="upload-row">
        <select
          className="upload-trip"
          value={trip}
          onChange={(e) => setTrip(e.target.value)}
          disabled={busy}
        >
          <option value="">Trip…</option>
          {tripNames.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
          <option value="__new__">+ New trip…</option>
        </select>
        {trip === '__new__' && (
          <input
            className="upload-newtrip"
            placeholder="new trip name"
            value={newTrip}
            onChange={(e) => setNewTrip(e.target.value)}
            disabled={busy}
          />
        )}
        <button
          className="upload-btn"
          onClick={() => inputRef.current?.click()}
          disabled={busy || !effectiveTrip}
        >
          {busy ? 'Uploading\u2026' : 'Upload photos'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          hidden
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>
      {msg && <div className={`upload-msg ${msg.type}`}>{msg.text}</div>}
    </div>
  )
}
