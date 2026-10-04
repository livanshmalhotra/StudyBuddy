export interface SearchResult {
  chunk_id: number
  text: string
  filename: string
  page: number | null
  heading: string | null
  fused_score: number
  vector_rank: number | null
  text_rank: number | null
  margin: number
  llm_used: boolean
}

export interface SearchResponsePayload {
  ai_answer: string | null
  results: SearchResult[]
}

export interface Document {
  id: number
  filename: string
  sha256: string
  status: 'queued' | 'processing' | 'ready' | 'failed'
  ingested_at: string | null
}
