import { SearchResult } from '../types'

interface Props {
  result: SearchResult
  index: number
}

function parsePointers(text: string): string[] {
  if (!text) return []

  // Split by bullet symbols, newlines, or inline bullet patterns
  const rawParts = text.split(/(?=[•▪⁃])|\n+/)
  const pointers: string[] = []

  for (let part of rawParts) {
    let cleaned = part.replace(/^[•▪⁃*\s]+/, '').trim()
    if (!cleaned) continue

    // Split concatenated numbered points if present
    if (/\b\d+\s+[A-Z]/.test(cleaned) && cleaned.length > 100) {
      const subParts = cleaned.split(/(?=\b\d+\s+[A-Z])/)
      for (let sp of subParts) {
        sp = sp.trim()
        if (sp) pointers.push(sp)
      }
    } else if (cleaned.length > 180 && !cleaned.includes('•')) {
      const sentences = cleaned.split(/(?<=[.!?])\s+/)
      for (let s of sentences) {
        s = s.trim()
        if (s) pointers.push(s)
      }
    } else {
      pointers.push(cleaned)
    }
  }

  return pointers.length > 0 ? pointers : [text]
}

export function ResultCard({ result, index }: Props) {
  const pointers = parsePointers(result.text)

  return (
    <div className="result-card" style={{ animationDelay: `${index * 40}ms` }}>
      <div className="result-meta">
        <span className="badge badge-nollm">⚡ NO LLM</span>
        <span className="badge badge-file">📄 {result.filename}</span>
        {result.heading && (
          <span className="badge badge-heading">§ {result.heading}</span>
        )}
        {result.page !== null && (
          <span className="badge badge-file">P.{result.page + 1}</span>
        )}
        <span className="result-score">SCORE {result.fused_score.toFixed(4)}</span>
      </div>

      <ul className="pointer-list">
        {pointers.map((item, idx) => (
          <li key={idx} className="pointer-item">
            {item}
          </li>
        ))}
      </ul>

      <div className="result-ranks">
        {result.vector_rank !== null && <>VEC #{result.vector_rank}</>}
        {result.vector_rank !== null && result.text_rank !== null && <> · </>}
        {result.text_rank !== null && <>BM25 #{result.text_rank}</>}
        {result.margin > 0 && <> · MARGIN {result.margin.toFixed(4)}</>}
      </div>
    </div>
  )
}
