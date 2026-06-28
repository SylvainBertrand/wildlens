import { useEffect } from 'react'
import { MapContainer, TileLayer, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { thumbUrl } from '../api'

// Default Leaflet marker icons don't resolve under bundlers; build a small
// photo-thumbnail divIcon instead so each pin shows the picture.
function photoIcon(photo) {
  return L.divIcon({
    className: 'photo-pin',
    html: `<div class="photo-pin-inner"><img src="${thumbUrl(photo)}" alt="" /></div>`,
    iconSize: [54, 54],
    iconAnchor: [27, 27],
    popupAnchor: [0, -28],
  })
}

function FitBounds({ photos }) {
  const map = useMap()
  useEffect(() => {
    const pts = photos.filter((p) => p.location).map((p) => [p.location.lat, p.location.lon])
    if (pts.length === 1) {
      map.setView(pts[0], 11)
    } else if (pts.length > 1) {
      map.fitBounds(pts, { padding: [50, 50] })
    }
  }, [photos, map])
  return null
}

export default function MapView({ photos, onSelect }) {
  const located = photos.filter((p) => p.location)
  const center = located[0]
    ? [located[0].location.lat, located[0].location.lon]
    : [44.6, -110.5] // Yellowstone-ish default

  return (
    <MapContainer center={center} zoom={9} className="map" scrollWheelZoom>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitBounds photos={located} />
      {located.map((p) => (
        <Marker
          key={p.id}
          position={[p.location.lat, p.location.lon]}
          icon={photoIcon(p)}
          eventHandlers={{ click: () => onSelect(p.id) }}
        >
          <Popup>
            <div className="popup">
              <img src={thumbUrl(p)} alt={p.filename} />
              <strong>{p.place_name || p.filename}</strong>
              {p.identification?.subjects?.[0] && (
                <span className="popup-id">
                  {p.identification.subjects.map((s) => s.label).join(' \u00b7 ')}
                </span>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}
