import { thumbUrl } from '../api'

const KIND_EMOJI = {
  fauna: '\u{1F43E}',
  flora: '\u{1F33F}',
  landmark: '\u{1F3DE}\uFE0F',
  scene: '\u{1F305}',
  unknown: '\u2753',
}

export default function Sidebar({ trips, photos, selectedId, onSelect, providerName }) {
  return (
    <aside className="sidebar">
      <header className="brand">
        <h1>wildlens</h1>
        <p className="tagline">your trips on a map</p>
      </header>

      {trips.map((t) => (
        <div key={t.name} className="trip-block">
          <h2>{t.name}</h2>
          <span className="trip-meta">
            {t.photo_count} photos · {t.located_count} geotagged
          </span>
        </div>
      ))}

      <ul className="photo-list">
        {photos.map((p) => (
          <li
            key={p.id}
            className={p.id === selectedId ? 'selected' : ''}
            onClick={() => onSelect(p.id)}
          >
            <img src={thumbUrl(p)} alt={p.filename} />
            <div className="photo-list-meta">
              <strong>{p.filename}</strong>
              <span>
                {p.identification?.subjects
                  ?.map((s) => `${KIND_EMOJI[s.kind] || ''} ${s.label}`)
                  .join('  ') || (p.location ? 'geotagged' : 'no location')}
              </span>
            </div>
          </li>
        ))}
      </ul>

      <footer className="provider-note">
        identification: <code>{providerName || 'mock'}</code>
      </footer>
    </aside>
  )
}
