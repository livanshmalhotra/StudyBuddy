import { useState, FormEvent } from 'react'
import { SearchResult, SearchResponsePayload } from '../types'
import { ResultCard } from './ResultCard'

const API = '/api'

export function SearchBox() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [aiAnswer, setAiAnswer] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searched, setSearched] = useState(false)
  const [showSources, setShowSources] = useState(false)

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!query.trim()) return

    setLoading(true)
    setError(null)
    setSearched(true)
    setAiAnswer(null)
    setShowSources(false)

    try {
      const resp = await fetch(`${API}/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), k: 2, synthesize: true }),
      })
      if (!resp.ok) throw new Error(`API error ${resp.status}`)
      const data: SearchResponsePayload = await resp.json()
      setAiAnswer(data.ai_answer)
      setResults((data.results ?? []).slice(0, 2))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
      setResults([])
      setAiAnswer(null)
    } finally {
      setLoading(false)
    }
  }

  const displayedSources = results.slice(0, 2)

  return (
    <div className="search-wrap">
      <div className="section-label">// HYBRID SEARCH & SYNTHESIS</div>
      <form className="search-row" onSubmit={handleSubmit}>
        <input
          id="search-input"
          className="search-input"
          type="text"
          placeholder="Ask anything about your notes…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
        />
        <button className="btn btn-primary" type="submit" disabled={loading || !query.trim()}>
          {loading ? 'Synthesizing…' : 'SEARCH →'}
        </button>
      </form>

      {error && <div className="error-msg">⚠ {error}</div>}

      {searched && !loading && displayedSources.length === 0 && !error && (
        <div className="empty-state">
          <div className="empty-icon">🔍</div>
          <div className="empty-text">No results found. Try a different query or upload more notes.</div>
        </div>
      )}

      {!searched && (
        <div className="empty-state">
          <div className="empty-title">SMALL IS THE NEW WHALE.</div>
          <div className="empty-text">Local-first AI retrieval with zero cloud dependency. Ask questions, get instant verified context from your uploaded notes.</div>
        </div>
      )}

      {aiAnswer && (
        <div className="ai-answer-card">
          <div className="ai-answer-header">
            <span className="badge badge-gemma">
              ✨ DIRECT ANSWER (GEMMA)
            </span>
          </div>
          <div className="ai-answer-body">{aiAnswer}</div>
        </div>
      )}

      {displayedSources.length > 0 && (
        <div className="sources-container">
          <button
            className="toggle-sources-btn"
            onClick={() => setShowSources(!showSources)}
          >
            <span>{showSources ? '▼' : '▶'}</span>
            <span>{showSources ? 'Hide Source Passages' : `Show Verified Source Passages (${displayedSources.length})`}</span>
          </button>

          {showSources && (
            <div className="results-list">
              <div className="results-header">// SOURCE PASSAGES ({displayedSources.length}) — RANKED BY RRF</div>
              {displayedSources.map((r, i) => (
                <ResultCard key={r.chunk_id} result={r} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
