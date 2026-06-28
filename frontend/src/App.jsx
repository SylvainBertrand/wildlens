import { useEffect, useMemo, useState } from 'react'
import { fetchPhotos } from './api'
import MapView from './components/MapView'
import Sidebar from './components/Sidebar'
import PhotoDetail from './components/PhotoDetail'
import './App.css'

export default function App() {
  const [data, setData] = useState({ trips: [], photos: [] })
  const [selectedId, setSelectedId] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPhotos()
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const selected = useMemo(
    () => data.photos.find((p) => p.id === selectedId) || null,
    [data.photos, selectedId]
  )

  const providerName = data.photos[0]?.identification?.provider

  return (
    <div className="app">
      <Sidebar
        trips={data.trips}
        photos={data.photos}
        selectedId={selectedId}
        onSelect={setSelectedId}
        providerName={providerName}
      />
      <main className="main">
        {loading && <div className="state">Loading photos…</div>}
        {error && (
          <div className="state error">
            {error}
            <p>Is the backend running and have you ingested photos?</p>
          </div>
        )}
        {!loading && !error && data.photos.length === 0 && (
          <div className="state">
            No photos yet. Add some under <code>data/photos/&lt;trip&gt;/</code> and run{' '}
            <code>python -m app.ingest</code>.
          </div>
        )}
        {!loading && !error && data.photos.length > 0 && (
          <MapView photos={data.photos} onSelect={setSelectedId} />
        )}
      </main>
      <PhotoDetail photo={selected} onClose={() => setSelectedId(null)} />
    </div>
  )
}
