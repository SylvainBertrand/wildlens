import { imageUrl } from '../api'

const KIND_LABEL = {
  fauna: 'Fauna',
  flora: 'Flora',
  landmark: 'Landmark',
  scene: 'Scene',
  unknown: 'Unknown',
}

export default function PhotoDetail({ photo, onClose }) {
  if (!photo) return null
  const subjects = photo.identification?.subjects || []

  return (
    <div className="detail-overlay" onClick={onClose}>
      <div className="detail-card" onClick={(e) => e.stopPropagation()}>
        <button className="detail-close" onClick={onClose}>
          ×
        </button>
        <img className="detail-img" src={imageUrl(photo)} alt={photo.filename} />
        <div className="detail-body">
          <h2>{photo.place_name || photo.filename}</h2>
          <p className="detail-sub">
            {photo.taken_at ? new Date(photo.taken_at).toLocaleString() : 'date unknown'}
            {photo.location &&
              ` \u00b7 ${photo.location.lat.toFixed(4)}, ${photo.location.lon.toFixed(4)}`}
          </p>

          {subjects.length === 0 && <p className="muted">No identification yet.</p>}

          {subjects.map((s, i) => (
            <div key={i} className="subject">
              <div className="subject-head">
                <span className="subject-kind">{KIND_LABEL[s.kind] || s.kind}</span>
                <span className="subject-label">{s.label}</span>
                <span className="subject-conf">{Math.round(s.confidence * 100)}%</span>
              </div>
              {s.fun_fact && <p className="fun-fact">{s.fun_fact}</p>}
            </div>
          ))}

          <p className="provider-tag">
            via {photo.identification?.provider || 'n/a'}
          </p>
        </div>
      </div>
    </div>
  )
}
