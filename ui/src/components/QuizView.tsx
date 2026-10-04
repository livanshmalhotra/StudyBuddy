import { useState, useEffect } from 'react'

const API = '/api'

interface Question {
  id: number
  type: string
  stem: string
  options: Record<string, string>
  answer: string
  difficulty: string
  topic: string
}

export function QuizView() {
  const [questions, setQuestions] = useState<Question[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [selectedOption, setSelectedOption] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [score, setScore] = useState(0)

  useEffect(() => {
    fetchQuiz()
  }, [])

  const fetchQuiz = async () => {
    setLoading(true)
    try {
      const resp = await fetch(`${API}/quiz?count=5`)
      if (resp.ok) {
        const data = await resp.json()
        setQuestions(data)
        setCurrentIndex(0)
        setSelectedOption(null)
        setSubmitted(false)
        setScore(0)
      }
    } catch (err) {
      console.error('Failed to fetch quiz', err)
    } finally {
      setLoading(false)
    }
  }

  const handleOptionSelect = (optKey: string) => {
    if (submitted) return
    setSelectedOption(optKey)
  }

  const handleSubmit = async () => {
    if (!selectedOption || submitted) return
    setSubmitted(true)
    const currentQ = questions[currentIndex]
    const isCorrect = selectedOption === currentQ.answer

    if (isCorrect) setScore((s) => s + 1)

    // Log attempt to backend
    try {
      await fetch(`${API}/attempts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: currentQ.id,
          topic: currentQ.topic,
          correct: isCorrect,
          seconds_taken: 12,
        }),
      })
    } catch (e) {
      console.error('Failed to record attempt', e)
    }
  }

  const handleNext = () => {
    if (currentIndex + 1 < questions.length) {
      setCurrentIndex((i) => i + 1)
      setSelectedOption(null)
      setSubmitted(false)
    }
  }

  if (loading) return <div style={{ padding: 20, textAlign: 'center' }}>Loading Quiz Questions…</div>
  if (!questions.length) return <div style={{ padding: 20 }}>No quiz questions available yet. Upload notes to generate quiz questions.</div>

  const currentQ = questions[currentIndex]
  const isFinished = submitted && currentIndex + 1 >= questions.length

  return (
    <div className="quiz-container">
      <div className="section-header">
        <div className="section-label">// PRACTICE QUIZ & EVALUATION</div>
        <span className="badge badge-file">QUESTION {currentIndex + 1} OF {questions.length}</span>
      </div>

      <div className="quiz-card">
        <div className="result-meta">
          <span className="badge badge-heading">TOPIC: {currentQ.topic}</span>
          <span className="badge badge-file">{currentQ.difficulty.toUpperCase()}</span>
        </div>

        <h3 className="quiz-question-stem">{currentQ.stem}</h3>

        <div className="quiz-options">
          {Object.entries(currentQ.options).map(([key, text]) => {
            let stateClass = ''
            if (selectedOption === key) stateClass = 'selected'
            if (submitted) {
              if (key === currentQ.answer) stateClass = 'correct'
              else if (selectedOption === key) stateClass = 'wrong'
            }

            return (
              <button
                key={key}
                className={`quiz-option-btn ${stateClass}`}
                onClick={() => handleOptionSelect(key)}
                disabled={submitted}
              >
                <span className="option-key">{key}.</span> {text}
              </button>
            )
          })}
        </div>

        <div className="quiz-actions">
          {!submitted ? (
            <button className="btn btn-primary" onClick={handleSubmit} disabled={!selectedOption}>
              SUBMIT ANSWER →
            </button>
          ) : !isFinished ? (
            <button className="btn btn-primary" onClick={handleNext}>
              NEXT QUESTION →
            </button>
          ) : (
            <button className="btn btn-primary" onClick={fetchQuiz}>
              RESTART QUIZ 🔄 (SCORE: {score}/{questions.length})
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
