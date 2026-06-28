import { useCallback, useEffect, useRef, useState } from 'react'
import { onedrive } from '../api'

function fmtDuration(ms) {
  if (!ms) return ''
  const s = Math.round(ms / 1000)
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
}

export default function OneDriveModal({ trips, onClose, onImported }) {
  const [status, setStatus] = useState(null)
  const [device, setDevice] = useState(null)
  const [stack, setStack] = useState([{ id: null, name: 'OneDrive' }])
  const [folders, setFolders] = useState([])
  const [media, setMedia] = useState([])
  const [cursor, setCursor] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(() => new Set())
  const [anchor, setAnchor] = useState(null)
  const [trip, setTrip] = useState('')
  const [newTrip, setNewTrip] = useState('')
  const [imp, setImp] = useState(null)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)
  const sentinelRef = useRef(null)

  const current = stack[stack.length - 1]
  const effectiveTrip = trip === '__new__' ? newTrip.trim() : trip

  const openFolderId = useCallback(async (itemId) => {
    setLoading(true)
    setError(null)
    setMedia([])
    setFolders([])
    setCursor(null)
    setSelected(new Set())
    setAnchor(null)
    try {
      const page = await onedrive.browse(itemId, null)
      setFolders(page.folders || [])
      setMedia(page.media || [])
      setCursor(page.next || null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const loadMore = useCallback(async () => {
    if (!cursor || loading) return
    setLoading(true)
    try {
      const page = await onedrive.browse(current.id, cursor)
      setMedia((m) => [...m, ...(page.media || [])])
      setCursor(page.next || null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [cursor, loading, current.id])

  useEffect(() => {
    onedrive
      .status()
      .then((s) => {
        setStatus(s)
        if (s.connected) openFolderId(null)
      })
      .catch((e) => setError(e.message))
    return () => pollRef.current && clearInterval(pollRef.current)
  }, [openFolderId])

  // Infinite scroll: load the next page when the sentinel scrolls into view.
  useEffect(() => {
    const el = sentinelRef.current
    if (!el) return
    const io = new IntersectionObserver((entries) => {
      if (entries[0].isIntersecting) loadMore()
    }, { rootMargin: '300px' })
    io.observe(el)
    return () => io.disconnect()
  }, [loadMore])

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
            setStatus(await onedrive.status())
            openFolderId(null)
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
    openFolderId(folder.id)
  }

  function goTo(index) {
    setStack(stack.slice(0, index + 1))
    openFolderId(stack[index].id)
  }

  function clickItem(index, e) {
    const id = media[index].id
    if (e.shiftKey && anchor !== null) {
      const [lo, hi] = anchor < index ? [anchor, index] : [index, anchor]
      setSelected((prev) => {
        const next = new Set(prev)
        for (let i = lo; i <= hi; i++) next.add(media[i].id)
        return next
      })
    } else {
      setSelected((prev) => {
        const next = new Set(prev)
        next.has(id) ? next.delete(id) : next.add(id)
        return next
      })
      setAnchor(index)
    }
  }

  function selectAllLoaded() {
    setSelected(new Set(media.map((m) => m.id)))
  }
  function clearSelection() {
    setSelected(new Set())
    setAnchor(null)
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
            clearSelection()
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

  const thumbFor = (m) => m.thumb_url || onedrive.thumbUrl(m.id)

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
            <code>.env</code> and restart.
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
              <span className="od-hint muted">Shift-click to select a range</span>
            </div>

            <div className="od-browser">
              {folders.map((f) => (
                <button key={f.id} className="od-folder" onClick={() => openFolder(f)}>
                  📁 {f.name}
                  {f.count ? <span className="od-count">{f.count}</span> : null}
                </button>
              ))}
              <div className="od-grid">
                {media.map((m, i) => (
                  <button
                    key={m.id}
                    className={`od-cell ${selected.has(m.id) ? 'sel' : ''}`}
                    onClick={(e) => clickItem(i, e)}
                    title={m.name}
                  >
                    <img src={thumbFor(m)} alt={m.name} loading="lazy" />
                    {m.media_type === 'video' && (
                      <span className="od-vbadge">▶ {fmtDuration(m.duration)}</span>
                    )}
                    <span className="od-check">{selected.has(m.id) ? '✓' : ''}</span>
                  </button>
                ))}
              </div>
              {loading && <div className="muted od-pad">Loading…</div>}
              {!loading && media.length === 0 && folders.length === 0 && (
                <p className="muted od-pad">This folder is empty.</p>
              )}
              <div ref={sentinelRef} className="od-sentinel" />
            </div>

            <div className="od-actions">
              <button className="od-mini" onClick={selectAllLoaded} disabled={media.length === 0}>
                Select loaded
              </button>
              <button className="od-mini" onClick={clearSelection} disabled={selected.size === 0}>
                Clear
              </button>
              <span className="od-selcount muted">{selected.size} selected</span>
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
                  : `Import ${selected.size}`}
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
