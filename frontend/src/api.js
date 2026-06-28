// Thin API client. Uses relative URLs (Vite proxies /api to the backend in dev;
// in production the backend serves the built frontend on the same origin).
export async function fetchPhotos(trip) {
  const url = trip ? `/api/photos?trip=${encodeURIComponent(trip)}` : '/api/photos'
  const res = await fetch(url)
  if (!res.ok) throw new Error(`Failed to load photos (${res.status})`)
  return res.json()
}

export function thumbUrl(photo) {
  return photo.thumb_url
}

export function imageUrl(photo) {
  return photo.image_url
}

export async function uploadPhotos(files, trip) {
  const form = new FormData()
  if (trip) form.append('trip', trip)
  for (const f of files) form.append('files', f)
  const res = await fetch('/api/upload', { method: 'POST', body: form })
  if (!res.ok) {
    let detail
    try {
      detail = (await res.json())?.detail
    } catch {
      detail = null
    }
    const msg = typeof detail === 'string' ? detail : detail?.message
    throw new Error(msg || `Upload failed (${res.status})`)
  }
  return res.json()
}

export async function triggerIngest() {
  const res = await fetch('/api/ingest', { method: 'POST' })
  if (!res.ok) throw new Error(`Failed to trigger ingest (${res.status})`)
  return res.json()
}

export async function fetchIngestStatus() {
  const res = await fetch('/api/ingest/status')
  if (!res.ok) throw new Error(`Failed to fetch ingest status (${res.status})`)
  return res.json()
}

// --- OneDrive import source ---
const ONEDRIVE = '/api/sources/onedrive'

async function odJson(path, opts) {
  const res = await fetch(`${ONEDRIVE}${path}`, opts)
  if (!res.ok) {
    let detail
    try {
      detail = (await res.json())?.detail
    } catch {
      detail = null
    }
    throw new Error((typeof detail === 'string' && detail) || `Request failed (${res.status})`)
  }
  return res.json()
}

export const onedrive = {
  status: () => odJson('/status'),
  connect: () => odJson('/connect', { method: 'POST' }),
  connectStatus: () => odJson('/connect/status'),
  disconnect: () => odJson('/disconnect', { method: 'POST' }),
  browse: (itemId, cursor) =>
    odJson(
      `/browse?${new URLSearchParams({
        ...(itemId ? { item_id: itemId } : {}),
        ...(cursor ? { cursor } : {}),
      }).toString()}`
    ),
  thumbUrl: (itemId) => `${ONEDRIVE}/thumb/${encodeURIComponent(itemId)}`,
  import: (trip, itemIds) =>
    odJson('/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trip, item_ids: itemIds }),
    }),
  importStatus: () => odJson('/import/status'),
}
