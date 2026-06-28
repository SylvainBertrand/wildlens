// Group photos by trip, then by day. Returns an ordered structure the Gallery
// renders, plus a flat ordered id list for lightbox prev/next navigation.

function dayKey(photo) {
  if (!photo.taken_at) return 'Undated'
  return photo.taken_at.slice(0, 10) // YYYY-MM-DD
}

function dayLabel(key) {
  if (key === 'Undated') return 'Undated'
  const d = new Date(key + 'T00:00:00')
  if (Number.isNaN(d.getTime())) return key
  return d.toLocaleDateString(undefined, {
    weekday: 'short',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
}

function sortPhotos(a, b) {
  const ta = a.taken_at || ''
  const tb = b.taken_at || ''
  if (ta && tb) return ta.localeCompare(tb)
  if (ta) return -1
  if (tb) return 1
  return a.filename.localeCompare(b.filename)
}

// Returns { trips: [{ name, count, days: [{ key, label, photos }] }], order: [id,...] }
export function groupByTripAndDay(photos) {
  const byTrip = new Map()
  for (const p of photos) {
    if (!byTrip.has(p.trip)) byTrip.set(p.trip, [])
    byTrip.get(p.trip).push(p)
  }

  const trips = []
  const order = []
  for (const name of [...byTrip.keys()].sort()) {
    const tripPhotos = byTrip.get(name).slice().sort(sortPhotos)
    const byDay = new Map()
    for (const p of tripPhotos) {
      const k = dayKey(p)
      if (!byDay.has(k)) byDay.set(k, [])
      byDay.get(k).push(p)
    }
    const days = [...byDay.keys()]
      .sort((a, b) => (a === 'Undated' ? 1 : b === 'Undated' ? -1 : a.localeCompare(b)))
      .map((k) => {
        const dayPhotos = byDay.get(k)
        for (const p of dayPhotos) order.push(p.id)
        return { key: k, label: dayLabel(k), photos: dayPhotos }
      })
    trips.push({ name, count: tripPhotos.length, days })
  }

  return { trips, order }
}
