// Thin API client. Uses relative URLs (Vite proxies /api to the backend in dev;
// in production the backend can serve the built frontend on the same origin).
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
