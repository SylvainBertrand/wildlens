import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchPhotos, fetchIngestStatus, onedrive } from './api'
import MapView from './components/MapView'
import Gallery from './components/Gallery'
import Sidebar from './components/Sidebar'
import Lightbox from './components/Lightbox'
import UploadPanel from './components/UploadPanel'
import OneDriveModal from './components/OneDriveModal'
import { groupByTripAndDay } from './lib/grouping'
import './App.css'

export default function App() {
  const [data, setData] = useState({ trips: [], photos: [] })
  const [view, setView] = useState('map') // 'map' | 'gallery'
  const [selectedId, setSelectedId] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
  const [odConfigured, setOdConfigured] = useState(false)
  const [showOneDrive, setShowOneDrive] = useState(false)
  const [hiddenTrips, setHiddenTrips] = useState(() => new Set())
  const pollRef = useRef(null)

  const load = useCallback(async () => {
    const d = await fetchPhotos()
    setData(d)
    return d
  }, [])

  useEffect(() => {
    load()
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
    onedrive
      .status()
      .then((s) => setOdConfigured(!!s.configured))
      .catch(() => setOdConfigured(false))
  }, [load])

  // After an upload, poll ingest status until idle, then refresh the photos.
  const watchIngest = useCallback(() => {
    setIngesting(true)
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const st = await fetchIngestStatus()
        if (st.state === 'idle' || st.state === 'error') {
          clearInterval(pollRef.current)
          pollRef.current = null
          setIngesting(false)
          await load()
        }
      } catch {
        // keep polling; transient errors are fine
      }
    }, 1500)
  }, [load])

  useEffect(() => () => pollRef.current && clearInterval(pollRef.current), [])

  // Trip visibility (applies to map + gallery; the tree always lists all trips).
  const visiblePhotos = useMemo(
    () => data.photos.filter((p) => !hiddenTrips.has(p.trip)),
    [data.photos, hiddenTrips]
  )
  const toggleTrip = useCallback((name) => {
    setHiddenTrips((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })
  }, [])
  const showOnlyTrip = useCallback(
    (name) => setHiddenTrips(new Set(data.trips.map((t) => t.name).filter((n) => n !== name))),
    [data.trips]
  )

  const grouped = useMemo(() => groupByTripAndDay(visiblePhotos), [visiblePhotos])
  const navOrder = useMemo(() => {
    if (view === 'gallery') return grouped.order
    const located = new Set(visiblePhotos.filter((p) => p.location).map((p) => p.id))
    return grouped.order.filter((id) => located.has(id))
  }, [view, grouped.order, visiblePhotos])

  const byId = useMemo(() => new Map(data.photos.map((p) => [p.id, p])), [data.photos])
  const selected = selectedId ? byId.get(selectedId) : null
  const navIndex = selectedId ? navOrder.indexOf(selectedId) : -1

  const providerName = data.photos[0]?.identification?.provider

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-brand">
          <h1>wildlens</h1>
          <span className="tagline">your trips on a map</span>
        </div>
        <div className="view-toggle">
          <button
            className={view === 'map' ? 'active' : ''}
            onClick={() => setView('map')}
          >
            🗺️ Map
          </button>
          <button
            className={view === 'gallery' ? 'active' : ''}
            onClick={() => setView('gallery')}
          >
            ▦ Gallery
          </button>
        </div>
        <UploadPanel trips={data.trips} onUploaded={watchIngest} />
        {odConfigured && (
          <button className="od-open-btn" onClick={() => setShowOneDrive(true)}>
            ☁ OneDrive
          </button>
        )}
      </header>

      {ingesting && <div className="ingest-banner">Processing new photos…</div>}

      <div className="content">
        {loading && <div className="state">Loading photos…</div>}
        {error && (
          <div className="state error">
            {error}
            <p>Is the backend running and have you ingested photos?</p>
          </div>
        )}
        {!loading && !error && data.photos.length === 0 && (
          <div className="state">
            No photos yet. Use <strong>Upload photos</strong> above, or drop a folder into{' '}
            <code>data/photos/&lt;trip&gt;/</code>.
          </div>
        )}

        {!loading && !error && data.photos.length > 0 && (
          <div className="map-layout">
            <Sidebar
              photos={data.photos}
              selectedId={selectedId}
              onSelect={setSelectedId}
              hiddenTrips={hiddenTrips}
              onToggleTrip={toggleTrip}
              onShowOnlyTrip={showOnlyTrip}
              providerName={providerName}
            />
            <main className="main">
              {visiblePhotos.length === 0 ? (
                <div className="state">All trips hidden — enable one in the sidebar.</div>
              ) : view === 'map' ? (
                <MapView photos={visiblePhotos} onSelect={setSelectedId} />
              ) : (
                <Gallery photos={visiblePhotos} onSelect={setSelectedId} />
              )}
            </main>
          </div>
        )}
      </div>

      <Lightbox
        photo={selected}
        onClose={() => setSelectedId(null)}
        onPrev={() => navIndex > 0 && setSelectedId(navOrder[navIndex - 1])}
        onNext={() =>
          navIndex >= 0 && navIndex < navOrder.length - 1 && setSelectedId(navOrder[navIndex + 1])
        }
        hasPrev={navIndex > 0}
        hasNext={navIndex >= 0 && navIndex < navOrder.length - 1}
      />

      {showOneDrive && (
        <OneDriveModal
          trips={data.trips}
          onClose={() => setShowOneDrive(false)}
          onImported={watchIngest}
        />
      )}
    </div>
  )
}
