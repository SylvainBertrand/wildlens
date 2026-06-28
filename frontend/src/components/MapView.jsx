import { useEffect } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet.markercluster'
import { thumbUrl } from '../api'

// Default Leaflet marker icons don't resolve under bundlers; build a small
// photo-thumbnail divIcon instead so each pin shows the picture.
function photoIcon(photo) {
  return L.divIcon({
    className: 'photo-pin',
    html: `<div class="photo-pin-inner"><img src="${thumbUrl(photo)}" alt="" /></div>`,
    iconSize: [54, 54],
    iconAnchor: [27, 27],
  })
}

// Imperatively manage a marker-cluster layer (the markercluster plugin isn't a
// React component, so we drive it directly and keep React out of the markers).
function ClusterLayer({ photos, onSelect }) {
  const map = useMap()

  useEffect(() => {
    const located = photos.filter((p) => p.location)
    const group = L.markerClusterGroup({
      showCoverageOnHover: false,
      maxClusterRadius: 50,
      spiderfyOnMaxZoom: true,
    })

    for (const p of located) {
      const marker = L.marker([p.location.lat, p.location.lon], { icon: photoIcon(p) })
      marker.on('click', () => onSelect(p.id))
      const facts = p.identification?.subjects?.map((s) => s.label).join(' \u00b7 ') || ''
      marker.bindTooltip(
        `<strong>${p.place_name || p.filename}</strong>${facts ? `<br/>${facts}` : ''}`,
        { direction: 'top', offset: [0, -28] }
      )
      group.addLayer(marker)
    }

    map.addLayer(group)

    if (located.length === 1) {
      map.setView([located[0].location.lat, located[0].location.lon], 12)
    } else if (located.length > 1) {
      map.fitBounds(group.getBounds(), { padding: [60, 60] })
    }

    return () => {
      map.removeLayer(group)
    }
  }, [photos, map, onSelect])

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
      <ClusterLayer photos={photos} onSelect={onSelect} />
    </MapContainer>
  )
}
