import { useEffect, useState, useCallback } from 'react'
import { Document } from '../types'
import { DocumentModal } from './DocumentModal'

const API = '/api'
const POLL_MS = 3000

interface Props {
  trigger?: number  // increment to force a refresh
}

export function UploadStatus({ trigger }: Props) {
  const [docs, setDocs] = useState<Document[]>([])
  const [error, setError] = useState(false)
  const [confirmId, setConfirmId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState<number | null>(null)
  const [shakeId, setShakeId] = useState<number | null>(null)
  const [selectedDocFilename, setSelectedDocFilename] = useState<string | null>(null)

  const fetchDocs = useCallback(async () => {
    try {
      const resp = await fetch(`${API}/documents`)
      if (!resp.ok) throw new Error()
      setDocs(await resp.json())
      setError(false)
    } catch {
      setError(true)
    }
  }, [])

  useEffect(() => {
    fetchDocs()
    const interval = setInterval(fetchDocs, POLL_MS)
    return () => clearInterval(interval)
  }, [fetchDocs, trigger])

  const handleDeleteClick = (e: React.MouseEvent, doc: Document) => {
    e.stopPropagation()
    if (confirmId === doc.id) {
      // Second click → actually delete
      performDelete(doc)
    } else {
      // First click → ask for confirmation (shake the card)
      setConfirmId(doc.id)
      setShakeId(doc.id)
      setTimeout(() => setShakeId(null), 500)
    }
  }

  const performDelete = async (doc: Document) => {
    setDeleting(doc.id)
    setConfirmId(null)
    try {
      const resp = await fetch(`${API}/documents/${encodeURIComponent(doc.filename)}`, {
        method: 'DELETE',
      })
      if (!resp.ok) throw new Error(`Delete failed: ${resp.status}`)
      // Remove from local state immediately for snappy UX
      setDocs((prev) => prev.filter((d) => d.id !== doc.id))
    } catch (err) {
      console.error(err)
    } finally {
      setDeleting(null)
    }
  }

  const cancelConfirm = (e: React.MouseEvent) => {
    e.stopPropagation()
    setConfirmId(null)
  }

  return (
    <>
      <div className="doc-list">
        {error && (
          <div className="doc-empty" style={{ color: '#f87171' }}>
            API offline
          </div>
        )}
        {!error && docs.length === 0 && (
          <div className="doc-empty">No documents yet — upload one above.</div>
        )}
        {docs.map((doc) => {
          const isConfirming = confirmId === doc.id
          const isDeleting = deleting === doc.id
          const isShaking = shakeId === doc.id

          return (
            <div
              key={doc.id}
              className={`doc-item${isConfirming ? ' doc-item--confirm' : ''}${isShaking ? ' doc-item--shake' : ''}`}
              onClick={() => setSelectedDocFilename(doc.filename)}
              title="Click to view full PDF details and extracted passages"
              style={{ cursor: 'pointer' }}
            >
              {/* File name */}
              <div className="doc-name" title={doc.filename}>
                📄 {doc.filename}
              </div>

              {/* Status row + delete button */}
              <div className="doc-status-row">
                <span className={`status-chip status-${doc.status}`}>{doc.status}</span>
                {doc.ingested_at && (
                  <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                    {new Date(doc.ingested_at).toLocaleTimeString()}
                  </span>
                )}

                {/* Delete button — far right */}
                <div className="doc-delete-wrap" onClick={(e) => e.stopPropagation()}>
                  {isConfirming && (
                    <span className="doc-confirm-label">Remove all context?</span>
                  )}
                  <button
                    className={`doc-delete-btn${isConfirming ? ' doc-delete-btn--danger' : ''}`}
                    title={isConfirming ? 'Click again to confirm delete' : 'Remove file & all its context'}
                    disabled={isDeleting}
                    onClick={(e) => handleDeleteClick(e, doc)}
                  >
                    {isDeleting
                      ? '⏳'
                      : isConfirming
                      ? '🗑️ Confirm'
                      : '🗑️'}
                  </button>
                  {isConfirming && (
                    <button
                      className="doc-cancel-btn"
                      title="Cancel"
                      onClick={cancelConfirm}
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>

              {/* Confirmation hint */}
              {isConfirming && (
                <div className="doc-warn-text">
                  ⚠️ This deletes all chunks, embeddings & cached answers for this file.
                </div>
              )}
            </div>
          )
        })}
      </div>

      {selectedDocFilename && (
        <DocumentModal
          filename={selectedDocFilename}
          onClose={() => setSelectedDocFilename(null)}
        />
      )}
    </>
  )
}
