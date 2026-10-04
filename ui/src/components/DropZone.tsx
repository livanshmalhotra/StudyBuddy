import { useCallback, useState, DragEvent, useRef } from 'react'

const API = '/api'
const ACCEPTED = '.pdf,.docx,.md,.txt,.png,.jpg,.jpeg'

interface Props {
  onUploaded?: (filename: string) => void
}

export function DropZone({ onUploaded }: Props) {
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const uploadFile = useCallback(async (file: File) => {
    setUploading(true)
    setMessage(null)
    const form = new FormData()
    form.append('file', file)
    try {
      const resp = await fetch(`${API}/upload`, { method: 'POST', body: form })
      if (!resp.ok) throw new Error(`Upload failed: ${resp.status}`)
      const data = await resp.json()
      setMessage(`✓ ${data.filename} uploaded`)
      onUploaded?.(data.filename)
    } catch (err) {
      setMessage(`✗ ${err instanceof Error ? err.message : 'Upload failed'}`)
    } finally {
      setUploading(false)
    }
  }, [onUploaded])

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  const onFileChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) uploadFile(file)
  }, [uploadFile])

  return (
    <div
      id="dropzone"
      className={`dropzone${dragging ? ' dragging' : ''}`}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      role="button"
      tabIndex={0}
      aria-label="Upload file"
    >
      <div className="dropzone-icon">{uploading ? '⏳' : '⬆️'}</div>
      <div>{uploading ? 'Uploading…' : message ?? 'Drop a file or click to upload'}</div>
      <input ref={inputRef} type="file" accept={ACCEPTED} onChange={onFileChange} />
    </div>
  )
}
