import { useState } from 'react'
import { useResources } from './hooks/useResources'
import { useTheme } from './hooks/useTheme.jsx'
import { BubbleMap } from './components/BubbleMap'
import { AddResourceModal } from './components/AddResourceModal'

export default function App() {
  const { resources, loading, error, addResource } = useResources()
  const { toggleTheme, isDark } = useTheme()
  const [showModal, setShowModal] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  if (loading) return (
    <div className="app-loading" style={{ background: 'var(--bg)' }}>
      <div className="loading-dot" />
      <span style={{ color: 'var(--muted)', fontSize: 13 }}>Loading resources…</span>
    </div>
  )

  if (error) return (
    <div className="app-loading" style={{ background: 'var(--bg)' }}>
      <span style={{ color: '#fb923c', fontSize: 13 }}>Error: {error}</span>
    </div>
  )

  return (
    <div className="app-shell" style={{ background: 'var(--bg)', color: 'var(--fg)' }}>
      <header className="app-header">
        <div>
          <h1 className="app-title">SMCCD <em>Resource Map</em></h1>
          <p className="app-subtitle">
            {resources.length} opportunities across Cañada, CSM & Skyline
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <button
            className="btn-icon"
            onClick={toggleTheme}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {isDark ? '☀' : '☾'}
          </button>
          <button className="btn btn-primary" onClick={() => setShowModal(true)}>
            + Add link
          </button>
        </div>
      </header>

      <div className="search-bar">
        <div className="search-wrap">
          <span className="search-icon">⌕</span>
          <input
            className="search-input"
            type="text"
            placeholder="Search resources…"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <BubbleMap resources={resources} searchQuery={searchQuery} />

      {showModal && (
        <AddResourceModal
          onClose={() => setShowModal(false)}
          onAdded={res => { addResource(res); setShowModal(false) }}
        />
      )}
    </div>
  )
}
