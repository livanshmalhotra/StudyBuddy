import { useState, useEffect } from 'react'

const API = '/api'

interface WeakTopic {
  topic: string
  predicted_wrong_probability: number
  priority: string
  attempt_count: number
}

interface Stats {
  documents_ingested: number
  total_chunks: number
  cached_answers: number
  quiz_questions: number
  quiz_attempts: number
  quiz_accuracy: number
  pct_answered_without_llm: number
  p50_latency_ms: number
  p95_latency_ms: number
}

export function DashboardView() {
  const [weakTopics, setWeakTopics] = useState<WeakTopic[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const [wResp, sResp] = await Promise.all([
        fetch(`${API}/weak-topics`),
        fetch(`${API}/stats`),
      ])
      if (wResp.ok) setWeakTopics(await wResp.json())
      if (sResp.ok) setStats(await sResp.json())
    } catch (err) {
      console.error('Failed to fetch dashboard stats', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div style={{ padding: 20, textAlign: 'center' }}>Loading Dashboard & Weak Topics…</div>

  return (
    <div className="dashboard-container">
      <div className="section-label">// PREDICTIVE ANALYTICS & DASHBOARD</div>

      {/* ── Operational Metrics ── */}
      {stats && (
        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-label">// NO-LLM ANSWERED %</div>
            <div className="metric-value text-coral">{stats.pct_answered_without_llm}%</div>
            <div className="metric-sub">Confidence Gate + Cache</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">// DOCUMENTS / CHUNKS</div>
            <div className="metric-value text-abyss">{stats.documents_ingested} / {stats.total_chunks}</div>
            <div className="metric-sub">Ingested Notes Corpus</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">// QUIZ ACCURACY</div>
            <div className="metric-value">{ (stats.quiz_accuracy * 100).toFixed(0) }%</div>
            <div className="metric-sub">{stats.quiz_attempts} Attempts Recorded</div>
          </div>

          <div className="metric-card">
            <div className="metric-label">// LATENCY P50 / P95</div>
            <div className="metric-value">{stats.p50_latency_ms} / {stats.p95_latency_ms}<span style={{ fontSize: 16 }}>ms</span></div>
            <div className="metric-sub">Retrieval & Synthesis Latency</div>
          </div>
        </div>
      )}

      {/* ── TabPFN Weak Topics Ranking ── */}
      <div className="result-card">
        <div className="section-label" style={{ marginBottom: 4 }}>// TABPFN PREDICTED WEAK TOPICS</div>
        <p className="card-desc">
          Topics prioritized by predicted probability of error P(wrong). Focus your review here.
        </p>

        <div className="weak-topics-list">
          {weakTopics.map((t, idx) => (
            <div key={idx} className="weak-topic-item">
              <div>
                <div className="doc-name">{t.topic}</div>
                <div className="metric-sub">{t.attempt_count} practice attempts</div>
              </div>

              <div className="weak-topic-right">
                <span className={`status-chip priority-${t.priority}`}>
                  {t.priority.toUpperCase()} PRIORITY
                </span>
                <span className="p-wrong-val">
                  {(t.predicted_wrong_probability * 100).toFixed(0)}% P(WRONG)
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
