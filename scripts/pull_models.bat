@echo off
REM ─────────────────────────────────────────────────────────────────────────────
REM scripts\pull_models.bat  — Windows equivalent of pull_models.sh
REM
REM Run AFTER:  docker compose up -d
REM Usage:      scripts\pull_models.bat
REM ─────────────────────────────────────────────────────────────────────────────

set OLLAMA_BASE_URL=http://localhost:11434
set EMBED_MODEL=bge-m3
set LLM_MODEL=gemma:2b

echo.
echo ===================================================
echo   StudyBuddy -- pulling Ollama models
echo   Ollama URL : %OLLAMA_BASE_URL%
echo   Embed model: %EMBED_MODEL%
echo   LLM model  : %LLM_MODEL%
echo ===================================================
echo.

REM ── Wait for Ollama ──────────────────────────────────────────────────────────
echo Waiting for Ollama to be reachable...
:WAIT_LOOP
curl -sf %OLLAMA_BASE_URL%/api/tags >nul 2>&1
if %ERRORLEVEL% EQU 0 goto OLLAMA_READY
echo   ... not ready yet, retrying in 5s
timeout /t 5 /nobreak >nul
goto WAIT_LOOP

:OLLAMA_READY
echo [OK] Ollama is up.

REM ── Pull embedding model ─────────────────────────────────────────────────────
echo.
echo Pulling %EMBED_MODEL% (~1.2 GB)...
curl -s -X POST %OLLAMA_BASE_URL%/api/pull ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"%EMBED_MODEL%\", \"stream\": false}"
echo.
echo [OK] %EMBED_MODEL% pull requested.

REM ── Pull LLM model ────────────────────────────────────────────────────────────
echo.
echo Pulling %LLM_MODEL% (~2.5 GB, please wait)...
curl -s -X POST %OLLAMA_BASE_URL%/api/pull ^
  -H "Content-Type: application/json" ^
  -d "{\"name\": \"%LLM_MODEL%\", \"stream\": false}"
echo.
echo [OK] %LLM_MODEL% pull requested.

REM ── List models ──────────────────────────────────────────────────────────────
echo.
echo Models in Ollama:
curl -s %OLLAMA_BASE_URL%/api/tags
echo.

echo.
echo ===================================================
echo   Done. Run:  python scripts\verify_infra.py
echo ===================================================
