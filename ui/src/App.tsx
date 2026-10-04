import { useState } from 'react'
import { SearchBox } from './components/SearchBox'
import { DropZone } from './components/DropZone'
import { UploadStatus } from './components/UploadStatus'
import { QuizView } from './components/QuizView'
import { DashboardView } from './components/DashboardView'

export default function App() {
  const [uploadTrigger, setUploadTrigger] = useState(0)
  const [activeTab, setActiveTab] = useState<'search' | 'quiz' | 'dashboard'>('search')

  return (
    <div className="app">
      {/* ── Header ── */}
      <header className="header">
        <div className="header-brand">
          <div className="header-logo">$STUDYBUDDY</div>
          <div className="header-tags">
            <span className="mono-tag">// LOCAL RAG</span>
            <span className="mono-tag">// TABPFN</span>
            <span className="mono-tag">// 2026</span>
          </div>
        </div>

        <nav className="header-nav">
          <button
            className={`nav-tab ${activeTab === 'search' ? 'active' : ''}`}
            onClick={() => setActiveTab('search')}
          >
            🔍 ASK / SEARCH
          </button>
          <button
            className={`nav-tab ${activeTab === 'quiz' ? 'active' : ''}`}
            onClick={() => setActiveTab('quiz')}
          >
            📝 PRACTICE QUIZ
          </button>
          <button
            className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            📊 WEAK TOPICS
          </button>
        </nav>
      </header>

      {/* ── Ticker Marquee Strip ── */}
      <div className="ticker-strip">
        <div className="ticker-track">
          <span>⚡ STUDYBUDDY</span>
          <span className="ticker-sep">●</span>
          <span>LOCAL-FIRST RAG</span>
          <span className="ticker-sep">●</span>
          <span>TABPFN PREDICTIVE ANALYTICS</span>
          <span className="ticker-sep">●</span>
          <span>HYBRID VECTOR + BM25</span>
          <span className="ticker-sep">●</span>
          <span>OLLAMA GEMMA SYNTHESIS</span>
          <span className="ticker-sep">●</span>
          <span>NO CLOUD DEPENDENCY</span>
          <span className="ticker-sep">●</span>
          <span>⚡ STUDYBUDDY</span>
          <span className="ticker-sep">●</span>
          <span>LOCAL-FIRST RAG</span>
          <span className="ticker-sep">●</span>
          <span>TABPFN PREDICTIVE ANALYTICS</span>
          <span className="ticker-sep">●</span>
          <span>HYBRID VECTOR + BM25</span>
          <span className="ticker-sep">●</span>
          <span>OLLAMA GEMMA SYNTHESIS</span>
          <span className="ticker-sep">●</span>
          <span>NO CLOUD DEPENDENCY</span>
          <span className="ticker-sep">●</span>
        </div>
      </div>

      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="sidebar-title">// YOUR FILES</div>
        <DropZone onUploaded={() => setUploadTrigger((t) => t + 1)} />
        <UploadStatus trigger={uploadTrigger} />
      </aside>

      {/* ── Main content area ── */}
      <main className="main">
        {activeTab === 'search' && <SearchBox />}
        {activeTab === 'quiz' && <QuizView />}
        {activeTab === 'dashboard' && <DashboardView />}
      </main>
    </div>
  )
}
