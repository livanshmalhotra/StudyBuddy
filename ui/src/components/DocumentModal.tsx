import { useEffect, useState } from 'react'

const API = '/api'

interface ChunkDetail {
  id: number
  page: number | null
  heading: string | null
  topic: string | null
  text: string
}

interface DocumentDetails {
  id: number
  filename: string
  sha256: string
  status: string
  ingested_at: string | null
  chunk_count: number
  chunks: ChunkDetail[]
}

interface Props {
  filename: string
  onClose: () => void
}

export function DocumentModal({ filename, onClose }: Props) {
  const [details, setDetails] = useState<DocumentDetails | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filterQuery, setFilterQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'pdf' | 'chunks'>('pdf')

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  useEffect(() => {
    fetchDetails()
  }, [filename])

  const fetchDetails = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await fetch(`${API}/documents/${encodeURIComponent(filename)}/details`)
      if (!resp.ok) throw new Error(`Failed to load document details: ${resp.status}`)
      const data: DocumentDetails = await resp.json()
      setDetails(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error loading details')
    } finally {
      setLoading(false)
    }
  }

  const filteredChunks = details?.chunks.filter((c) =>
    filterQuery.trim() === ''
      ? true
      : c.text.toLowerCase().includes(filterQuery.toLowerCase()) ||
        (c.heading && c.heading.toLowerCase().includes(filterQuery.toLowerCase()))
  ) ?? []

  const isPdf = filename.toLowerCase().endsWith('.pdf')

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-window" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <div className="modal-badge-tag">// DOCUMENT INSPECTOR</div>
            <h2 className="modal-title">📄 {filename}</h2>
          </div>
          <button className="btn modal-close-btn" onClick={onClose} title="Close window (Esc)">
            ✕ CLOSE
          </button>
        </div>

        {/* Modal Content */}
        <div className="modal-body">
          {loading && (
            <div className="empty-state" style={{ padding: '40px 20px' }}>
              <div className="empty-icon">⏳</div>
              <div className="empty-text">Extracting document preview and passages…</div>
            </div>
          )}

          {error && (
            <div className="error-msg">
              ⚠ {error}
            </div>
          )}

          {!loading && !error && details && (
            <>
              {/* Metadata & Mode Toggle Strip */}
              <div className="modal-meta-strip">
                <div className="header-nav" style={{ gap: 8 }}>
                  {isPdf && (
                    <button
                      className={`nav-tab ${activeTab === 'pdf' ? 'active' : ''}`}
                      onClick={() => setActiveTab('pdf')}
                      style={{ padding: '6px 14px', fontSize: 11 }}
                    >
                      📄 PDF VIEWER
                    </button>
                  )}
                  <button
                    className={`nav-tab ${activeTab === 'chunks' || !isPdf ? 'active' : ''}`}
                    onClick={() => setActiveTab('chunks')}
                    style={{ padding: '6px 14px', fontSize: 11 }}
                  >
                    🧩 EXTRACTED PASSAGES ({details.chunk_count})
                  </button>
                </div>

                <div className="meta-item" style={{ marginLeft: 'auto' }}>
                  <span className="meta-key">// STATUS</span>
                  <span className={`status-chip status-${details.status}`}>{details.status}</span>
                </div>
              </div>

              {/* View: PDF IFrame Viewer */}
              {activeTab === 'pdf' && isPdf && (
                <div style={{ flex: 1, minHeight: 520, border: 'var(--border)', boxShadow: 'var(--shadow-hard)' }}>
                  <iframe
                    src={`${API}/documents/${encodeURIComponent(filename)}/file`}
                    title={filename}
                    width="100%"
                    height="100%"
                    style={{ border: 'none', minHeight: 520, background: '#fff', display: 'block' }}
                  />
                </div>
              )}

              {/* View: Chunks / Passages List */}
              {(activeTab === 'chunks' || !isPdf) && (
                <>
                  <div className="modal-filter-row">
                    <input
                      type="text"
                      className="search-input"
                      style={{ padding: '10px 14px', fontSize: 13 }}
                      placeholder="Filter passages in this file…"
                      value={filterQuery}
                      onChange={(e) => setFilterQuery(e.target.value)}
                    />
                    <span className="mono-tag" style={{ height: '100%', display: 'flex', alignItems: 'center' }}>
                      {filteredChunks.length} / {details.chunk_count} MATCHES
                    </span>
                  </div>

                  <div className="modal-chunks-list">
                    {filteredChunks.length === 0 ? (
                      <div className="doc-empty">No passages match your filter.</div>
                    ) : (
                      filteredChunks.map((chunk, idx) => (
                        <div key={chunk.id} className="modal-chunk-card">
                          <div className="result-meta">
                            <span className="badge badge-file">PASSAGE #{idx + 1}</span>
                            {chunk.page !== null && (
                              <span className="badge badge-file">P.{chunk.page + 1}</span>
                            )}
                            {chunk.heading && (
                              <span className="badge badge-heading">§ {chunk.heading}</span>
                            )}
                            {chunk.topic && (
                              <span className="badge badge-nollm">TOPIC: {chunk.topic}</span>
                            )}
                          </div>
                          <div className="modal-chunk-text">{chunk.text}</div>
                        </div>
                      ))
                    )}
                  </div>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  )
}
