import { useMemo } from 'react'
import { thumbUrl } from '../api'
import { groupByTripAndDay } from '../lib/grouping'

export default function Gallery({ photos, onSelect }) {
  const grouped = useMemo(() => groupByTripAndDay(photos), [photos])

  return (
    <div className="gallery">
      {grouped.trips.map((trip) => (
        <section key={trip.name} className="gallery-trip">
          <h2 className="gallery-trip-title">
            {trip.name}
            <span className="gallery-trip-count">{trip.count}</span>
          </h2>
          {trip.days.map((day) => (
            <div key={day.key} className="gallery-day">
              <h3 className="gallery-day-title">{day.label}</h3>
              <div className="gallery-grid">
                {day.photos.map((p) => (
                  <button
                    key={p.id}
                    className="gallery-cell"
                    onClick={() => onSelect(p.id)}
                    title={p.place_name || p.filename}
                  >
                    <img src={thumbUrl(p)} alt={p.place_name || p.filename} loading="lazy" />
                    {p.media_type === 'video' && <span className="gallery-play">▶</span>}
                    {!p.location && <span className="gallery-badge" title="No location">⌖</span>}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
