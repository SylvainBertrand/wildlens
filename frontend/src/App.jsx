import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { fetchPhotos, fetchIngestStatus } from './api'
import MapView from './components/MapView'
import Gallery from './components/Gallery'
import Sidebar from './components/Sidebar'
import Lightbox from './components/Lightbox'
import UploadPanel from './components/UploadPanel'
import { groupByTripAndDay } from './lib/grouping'
import './App.css'

export default function App() {
  const [data, setData] = useState({ trips: [], photos: [] })
  const [view, setView] = useState('map') // 'map' | 'gallery'
  const [selectedId, setSelectedId] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [ingesting, setIngesting] = useState(false)
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

  const grouped = useMemo(() => groupByTripAndDay(data.photos), [data.photos])
  const navOrder = useMemo(() => {
    if (view === 'gallery') return grouped.order
    const located = new Set(data.photos.filter((p) => p.location).map((p) => p.id))
    return grouped.order.filter((id) => located.has(id))
  }, [view, grouped.order, data.photos])

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
      </header>

      {ingesting && <div className="ingest-banner">Processing new photos…</div>}

      <div className={`content ${view}`}>
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

        {!loading && !error && data.photos.length > 0 && view === 'map' && (
          <div className="map-layout">
            <Sidebar
              trips={data.trips}
              photos={data.photos}
              selectedId={selectedId}
              onSelect={setSelectedId}
              providerName={providerName}
            />
            <main className="main">
              <MapView photos={data.photos} onSelect={setSelectedId} />
            </main>
          </div>
        )}

        {!loading && !error && data.photos.length > 0 && view === 'gallery' && (
          <Gallery photos={data.photos} onSelect={setSelectedId} />
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
    </div>
  )
}
