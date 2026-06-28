import { useCallback, useEffect, useRef, useState } from 'react'
import { onedrive } from '../api'

export default function OneDriveModal({ trips, onClose, onImported }) {
  const [status, setStatus] = useState(null)
  const [device, setDevice] = useState(null) // {user_code, verification_uri}
  const [stack, setStack] = useState([{ id: null, name: 'OneDrive' }])
  const [listing, setListing] = useState(null)
  const [selected, setSelected] = useState(() => new Set())
  const [trip, setTrip] = useState('')
  const [newTrip, setNewTrip] = useState('')
  const [imp, setImp] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const pollRef = useRef(null)

  const current = stack[stack.length - 1]
  const effectiveTrip = trip === '__new__' ? newTrip.trim() : trip

  const loadListing = useCallback(async (itemId) => {
    setBusy(true)
    setError(null)
    try {
      setListing(await onedrive.browse(itemId))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    onedrive
      .status()
      .then((s) => {
        setStatus(s)
        if (s.connected) loadListing(null)
      })
      .catch((e) => setError(e.message))
    return () => pollRef.current && clearInterval(pollRef.current)
  }, [loadListing])

  async function startConnect() {
    setError(null)
    try {
      const dc = await onedrive.connect()
      setDevice(dc)
      pollRef.current = setInterval(async () => {
        try {
          const cs = await onedrive.connectStatus()
          if (cs.state === 'connected') {
            clearInterval(pollRef.current)
            setDevice(null)
            const s = await onedrive.status()
            setStatus(s)
            loadListing(null)
          } else if (cs.state === 'error') {
            clearInterval(pollRef.current)
            setError(cs.error || 'Connection failed')
            setDevice(null)
          }
        } catch {
          /* keep polling */
        }
      }, 3000)
    } catch (e) {
      setError(e.message)
    }
  }

  function openFolder(folder) {
    setStack((s) => [...s, { id: folder.id, name: folder.name }])
    loadListing(folder.id)
  }

  function goTo(index) {
    const target = stack[index]
    setStack(stack.slice(0, index + 1))
    loadListing(target.id)
  }

  function toggle(id) {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  async function startImport() {
    if (!effectiveTrip) {
      setError('Pick or name a trip first.')
      return
    }
    if (selected.size === 0) return
    setError(null)
    try {
      await onedrive.import(effectiveTrip, [...selected])
      setImp({ state: 'running', done: 0, total: selected.size })
      pollRef.current = setInterval(async () => {
        try {
          const st = await onedrive.importStatus()
          setImp(st)
          if (st.state === 'done' || st.state === 'error') {
            clearInterval(pollRef.current)
            setSelected(new Set())
            onImported?.()
          }
        } catch {
          /* keep polling */
        }
      }, 1500)
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="od-modal" onClick={(e) => e.stopPropagation()}>
        <button className="detail-close" onClick={onClose}>
          ×
        </button>
        <h2 className="od-title">Import from OneDrive</h2>

        {error && <div className="od-error">{error}</div>}

        {status && !status.configured && (
          <p className="muted">
            OneDrive isn’t configured. Set <code>WILDLENS_ONEDRIVE_CLIENT_ID</code> in{' '}
            <code>.env</code> (see README) and restart.
          </p>
        )}

        {status?.configured && !status.connected && !device && (
          <div className="od-connect">
            <p className="muted">Connect your Microsoft account to browse your photos.</p>
            <button className="upload-btn" onClick={startConnect}>
              Connect OneDrive
            </button>
          </div>
        )}

        {device && (
          <div className="od-device">
            <p>
              Go to{' '}
              <a href={device.verification_uri} target="_blank" rel="noreferrer">
                {device.verification_uri}
              </a>{' '}
              and enter this code:
            </p>
            <div className="od-code">{device.user_code}</div>
            <p className="muted">Waiting for you to sign in…</p>
          </div>
        )}

        {status?.connected && (
          <>
            <div className="od-bar">
              <nav className="od-crumbs">
                {stack.map((s, i) => (
                  <span key={i}>
                    {i > 0 && <span className="od-sep">/</span>}
                    <button className="od-crumb" onClick={() => goTo(i)}>
                      {s.name}
                    </button>
                  </span>
                ))}
              </nav>
              {status.account && (
                <span className="od-account">{status.account.email || status.account.name}</span>
              )}
            </div>

            {busy && <div className="muted od-pad">Loading…</div>}

            {listing && !busy && (
              <div className="od-browser">
                {listing.folders.map((f) => (
                  <button key={f.id} className="od-folder" onClick={() => openFolder(f)}>
                    📁 {f.name}
                    {f.count ? <span className="od-count">{f.count}</span> : null}
                  </button>
                ))}
                <div className="od-grid">
                  {listing.images.map((img) => (
                    <button
                      key={img.id}
                      className={`od-cell ${selected.has(img.id) ? 'sel' : ''}`}
                      onClick={() => toggle(img.id)}
                      title={img.name}
                    >
                      <img src={onedrive.thumbUrl(img.id)} alt={img.name} loading="lazy" />
                      <span className="od-check">{selected.has(img.id) ? '✓' : ''}</span>
                    </button>
                  ))}
                </div>
                {listing.folders.length === 0 && listing.images.length === 0 && (
                  <p className="muted od-pad">This folder is empty.</p>
                )}
              </div>
            )}

            <div className="od-actions">
              <select value={trip} onChange={(e) => setTrip(e.target.value)} className="upload-trip">
                <option value="">Trip…</option>
                {trips.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name}
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
                />
              )}
              <button
                className="upload-btn"
                disabled={selected.size === 0 || !effectiveTrip || imp?.state === 'running'}
                onClick={startImport}
              >
                {imp?.state === 'running'
                  ? `Importing ${imp.done}/${imp.total}…`
                  : `Import ${selected.size} photo${selected.size === 1 ? '' : 's'}`}
              </button>
            </div>

            {imp?.state === 'done' && (
              <div className="od-done">
                Imported {imp.done - (imp.errors?.length || 0)}/{imp.total}. Ingesting…
                {imp.errors?.length ? ` (${imp.errors.length} failed)` : ''}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
