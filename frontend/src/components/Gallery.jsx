import { useMemo, useState } from 'react'
import { thumbUrl } from '../api'
import { groupByTripAndDay } from '../lib/grouping'

// Collapse consecutive photos that share a group_id into one unit.
function toUnits(photos) {
  const units = []
  let i = 0
  while (i < photos.length) {
    const p = photos[i]
    if (p.group_id) {
      const members = [p]
      let j = i + 1
      while (j < photos.length && photos[j].group_id === p.group_id) {
        members.push(photos[j])
        j++
      }
      units.push(
        members.length > 1
          ? { type: 'group', key: p.group_id, members }
          : { type: 'single', key: p.id, photo: p }
      )
      i = j
    } else {
      units.push({ type: 'single', key: p.id, photo: p })
      i++
    }
  }
  return units
}

function Cell({ photo, onSelect, badge, onBadge }) {
  return (
    <button
      className="gallery-cell"
      onClick={() => onSelect(photo.id)}
      title={photo.place_name || photo.filename}
    >
      <img src={thumbUrl(photo)} alt={photo.place_name || photo.filename} loading="lazy" />
      {photo.media_type === 'video' && <span className="gallery-play">▶</span>}
      {!photo.location && <span className="gallery-badge" title="No location">⌖</span>}
      {badge ? (
        <span
          className="gallery-group-badge"
          title="Show similar"
          onClick={(e) => {
            e.stopPropagation()
            onBadge()
          }}
        >
          +{badge}
        </span>
      ) : null}
    </button>
  )
}

export default function Gallery({ photos, onSelect }) {
  const grouped = useMemo(() => groupByTripAndDay(photos), [photos])
  const [expanded, setExpanded] = useState(() => new Set())

  const toggle = (key) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })

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
                {toUnits(day.photos).flatMap((u) => {
                  if (u.type === 'single') {
                    return [<Cell key={u.key} photo={u.photo} onSelect={onSelect} />]
                  }
                  if (expanded.has(u.key)) {
                    return [
                      ...u.members.map((m) => (
                        <Cell key={m.id} photo={m} onSelect={onSelect} />
                      )),
                      <button
                        key={`${u.key}-collapse`}
                        className="gallery-collapse"
                        onClick={() => toggle(u.key)}
                        title="Collapse group"
                      >
                        ⤡
                      </button>,
                    ]
                  }
                  return [
                    <Cell
                      key={u.key}
                      photo={u.members[0]}
                      onSelect={onSelect}
                      badge={u.members.length - 1}
                      onBadge={() => toggle(u.key)}
                    />,
                  ]
                })}
              </div>
            </div>
          ))}
        </section>
      ))}
    </div>
  )
}
