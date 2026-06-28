import { useMemo, useState } from 'react'
import { thumbUrl } from '../api'
import { groupByTripAndDay } from '../lib/grouping'

export default function Sidebar({
  photos,
  selectedId,
  onSelect,
  hiddenTrips,
  onToggleTrip,
  onShowOnlyTrip,
  providerName,
}) {
  const grouped = useMemo(() => groupByTripAndDay(photos), [photos])

  // Expand state. Default: expand trips when there's only one; collapse days.
  const [openTrips, setOpenTrips] = useState(() =>
    new Set(grouped.trips.length === 1 ? grouped.trips.map((t) => t.name) : [])
  )
  const [openDays, setOpenDays] = useState(() => new Set())

  const toggle = (set, setter, key) => {
    const next = new Set(set)
    next.has(key) ? next.delete(key) : next.add(key)
    setter(next)
  }

  return (
    <aside className="sidebar">
      <div className="tree">
        {grouped.trips.map((trip) => {
          const tripOpen = openTrips.has(trip.name)
          const hidden = hiddenTrips.has(trip.name)
          return (
            <div key={trip.name} className="tree-trip">
              <div className="tree-row tree-row-trip">
                <input
                  type="checkbox"
                  className="tree-check"
                  checked={!hidden}
                  title={hidden ? 'Show on map/gallery' : 'Hide from map/gallery'}
                  onChange={() => onToggleTrip(trip.name)}
                  onClick={(e) => e.stopPropagation()}
                />
                <button
                  className="tree-label"
                  onClick={() => toggle(openTrips, setOpenTrips, trip.name)}
                >
                  <span className={`caret ${tripOpen ? 'open' : ''}`}>▸</span>
                  <span className="tree-name">{trip.name}</span>
                  <span className="tree-count">{trip.count}</span>
                </button>
                <button
                  className="tree-only"
                  title="Show only this trip"
                  onClick={() => onShowOnlyTrip(trip.name)}
                >
                  only
                </button>
              </div>

              {tripOpen &&
                trip.days.map((day) => {
                  const dayKey = `${trip.name}\u0000${day.key}`
                  const dayOpen = openDays.has(dayKey)
                  return (
                    <div key={dayKey} className="tree-day">
                      <button
                        className="tree-row tree-row-day"
                        onClick={() => toggle(openDays, setOpenDays, dayKey)}
                      >
                        <span className={`caret ${dayOpen ? 'open' : ''}`}>▸</span>
                        <span className="tree-name">{day.label}</span>
                        <span className="tree-count">{day.photos.length}</span>
                      </button>
                      {dayOpen && (
                        <ul className="tree-photos">
                          {day.photos.map((p) => (
                            <li
                              key={p.id}
                              className={`tree-photo ${p.id === selectedId ? 'selected' : ''}`}
                              onClick={() => onSelect(p.id)}
                              title={p.place_name || p.filename}
                            >
                              <img src={thumbUrl(p)} alt="" loading="lazy" />
                              {p.media_type === 'video' && <span className="tree-vbadge">▶</span>}
                              <span className="tree-photo-name">
                                {p.place_name || p.filename}
                              </span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )
                })}
            </div>
          )
        })}
      </div>

      <footer className="provider-note">
        identification: <code>{providerName || 'none'}</code>
      </footer>
    </aside>
  )
}
