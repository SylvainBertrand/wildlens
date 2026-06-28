import { useEffect, useState } from 'react'
import { imageUrl } from '../api'

const KIND_LABEL = {
  place: 'Place',
  fauna: 'Fauna',
  flora: 'Flora',
  landmark: 'Landmark',
  scene: 'Scene',
  unknown: 'Unknown',
}

const INFO_W = 320 // info panel width (px)

// Fit the media to its natural aspect ratio within the viewport, so the card
// hugs the media (no letterbox bands). Falls back to a 3:2 box if dims unknown.
function useMediaSize(photo) {
  const [vp, setVp] = useState({ w: window.innerWidth, h: window.innerHeight })
  useEffect(() => {
    const onResize = () => setVp({ w: window.innerWidth, h: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  const natW = photo?.width || 3
  const natH = photo?.height || 2
  const availH = vp.h * 0.92
  const availW = vp.w * 0.96 - INFO_W
  const scale = Math.min(availH / natH, availW / natW)
  return { w: Math.round(natW * scale), h: Math.round(natH * scale) }
}

export default function Lightbox({ photo, onClose, onPrev, onNext, hasPrev, hasNext }) {
  const size = useMediaSize(photo)

  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
      else if (e.key === 'ArrowLeft' && hasPrev) onPrev()
      else if (e.key === 'ArrowRight' && hasNext) onNext()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose, onPrev, onNext, hasPrev, hasNext])

  if (!photo) return null
  const subjects = photo.identification?.subjects || []

  return (
    <div className="detail-overlay" onClick={onClose}>
      {hasPrev && (
        <button
          className="nav-arrow nav-prev"
          onClick={(e) => {
            e.stopPropagation()
            onPrev()
          }}
          aria-label="Previous"
        >
          ‹
        </button>
      )}
      {hasNext && (
        <button
          className="nav-arrow nav-next"
          onClick={(e) => {
            e.stopPropagation()
            onNext()
          }}
          aria-label="Next"
        >
          ›
        </button>
      )}
      <div
        className="detail-card"
        onClick={(e) => e.stopPropagation()}
        style={{ width: size.w + INFO_W, height: size.h }}
      >
        <button className="detail-close" onClick={onClose}>
          ×
        </button>
        <div className="detail-media" style={{ width: size.w, height: size.h }}>
          {photo.media_type === 'video' ? (
            <video className="detail-img" src={imageUrl(photo)} controls autoPlay playsInline />
          ) : (
            <img className="detail-img" src={imageUrl(photo)} alt={photo.filename} />
          )}
        </div>
        <div className="detail-body">
          <h2>{photo.place_name || photo.filename}</h2>
          {photo.place_detail && <p className="detail-place">{photo.place_detail}</p>}
          <p className="detail-sub">
            {photo.taken_at ? new Date(photo.taken_at).toLocaleString() : 'date unknown'}
            {photo.location &&
              ` \u00b7 ${photo.location.lat.toFixed(4)}, ${photo.location.lon.toFixed(4)}`}
          </p>

          {subjects.length === 0 && (
            <p className="muted">No fun facts found for this spot yet.</p>
          )}

          {subjects.map((s, i) => (
            <div key={i} className="subject">
              <div className="subject-head">
                <span className="subject-kind">{KIND_LABEL[s.kind] || s.kind}</span>
                <span className="subject-label">{s.label}</span>
                {s.confidence < 1 && (
                  <span className="subject-conf">{Math.round(s.confidence * 100)}%</span>
                )}
              </div>
              {s.fun_fact && <p className="fun-fact">{s.fun_fact}</p>}
              {s.url && (
                <a className="subject-link" href={s.url} target="_blank" rel="noreferrer">
                  Read more ↗
                </a>
              )}
            </div>
          ))}

          <p className="provider-tag">via {photo.identification?.provider || 'n/a'}</p>
        </div>
      </div>
    </div>
  )
}
