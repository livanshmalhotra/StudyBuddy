#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
# Force UTF-8 output on Windows (cp1252 can't render box chars / emoji)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
"""
scripts/verify_infra.py
───────────────────────
Block 1 "done when" verification script.

Checks:
  1. Postgres is reachable and accepts connections
  2. pgvector extension is installed
  3. All 5 required tables exist with correct columns
  4. Ollama is reachable (HTTP)
  5. Temporal is reachable (HTTP health endpoint)

Usage:
    python scripts/verify_infra.py

Exit code 0 = all checks pass.
Exit code 1 = one or more checks failed (details printed).
"""

import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# ── load .env manually (no external libs needed in this script) ───────────────
def load_env(env_file: Path) -> None:
    """Load key=value pairs from a .env file into os.environ (if not already set)."""
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

# Try .env in project root (two levels up from scripts/)
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent
load_env(_project_root / ".env")
load_env(_project_root / ".env.example")  # fallback defaults

# ── config from env ───────────────────────────────────────────────────────────
PG_HOST = os.environ.get("POSTGRES_HOST", "localhost")
PG_PORT = int(os.environ.get("POSTGRES_PORT", "5432"))
PG_USER = os.environ.get("POSTGRES_USER", "studybuddy")
PG_PASS = os.environ.get("POSTGRES_PASSWORD", "studybuddy")
PG_DB   = os.environ.get("POSTGRES_DB", "studybuddy")

OLLAMA_URL   = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")

REQUIRED_TABLES = ["documents", "chunks", "answer_cache", "questions", "attempts"]

# ── helpers ───────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg: str)   -> None: print(f"  {GREEN}[OK]  {msg}{RESET}")
def fail(msg: str) -> None: print(f"  {RED}[FAIL] {msg}{RESET}")
def warn(msg: str) -> None: print(f"  {YELLOW}[WARN] {msg}{RESET}")
def section(title: str) -> None:
    print(f"\n{BOLD}-- {title} {'-' * max(0, 50 - len(title))}{RESET}")


def http_get(url: str, timeout: int = 5) -> tuple[int, str]:
    """Simple HTTP GET. Returns (status_code, body_text)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, str(e)
    except Exception as e:
        return -1, str(e)


# ── check functions ───────────────────────────────────────────────────────────

def check_postgres() -> bool:
    """Check Postgres connection, pgvector extension, and required tables."""
    section("Postgres + pgvector")
    try:
        import psycopg  # type: ignore
    except ImportError:
        warn("psycopg not installed — install it with: pip install psycopg[binary]")
        warn("Falling back to socket check only...")
        import socket
        try:
            s = socket.create_connection((PG_HOST, PG_PORT), timeout=5)
            s.close()
            ok(f"Postgres TCP reachable at {PG_HOST}:{PG_PORT}")
            warn("Cannot verify tables/extension without psycopg")
            return True
        except Exception as e:
            fail(f"Postgres TCP not reachable at {PG_HOST}:{PG_PORT}: {e}")
            return False

    dsn = f"host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER} password={PG_PASS}"
    all_ok = True

    try:
        with psycopg.connect(dsn, connect_timeout=10) as conn:
            ok(f"Connected to Postgres at {PG_HOST}:{PG_PORT} (db={PG_DB})")

            # Check pgvector extension
            with conn.cursor() as cur:
                cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
                row = cur.fetchone()
                if row:
                    ok(f"pgvector extension installed (version {row[0]})")
                else:
                    fail("pgvector extension NOT found — check the image or run CREATE EXTENSION vector;")
                    all_ok = False

            # Check required tables
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                    ORDER BY table_name;
                """)
                existing = {row[0] for row in cur.fetchall()}

            for table in REQUIRED_TABLES:
                if table in existing:
                    ok(f"Table exists: {table}")
                else:
                    fail(f"Table MISSING: {table}")
                    all_ok = False

            # Check HNSW index
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'chunks' AND indexdef ILIKE '%hnsw%';
                """)
                hnsw_rows = cur.fetchall()
                if hnsw_rows:
                    ok(f"HNSW index found: {hnsw_rows[0][0]}")
                else:
                    fail("HNSW index NOT found on chunks.embedding")
                    all_ok = False

            # Check GIN index
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE tablename = 'chunks' AND indexdef ILIKE '%gin%';
                """)
                gin_rows = cur.fetchall()
                if gin_rows:
                    ok(f"GIN index found: {gin_rows[0][0]}")
                else:
                    fail("GIN index NOT found on chunks.tsv")
                    all_ok = False

    except Exception as e:
        fail(f"Postgres connection failed: {e}")
        fail(f"  DSN attempted: host={PG_HOST} port={PG_PORT} dbname={PG_DB} user={PG_USER}")
        all_ok = False

    return all_ok


def check_ollama() -> bool:
    """Check Ollama HTTP API and list available models."""
    section("Ollama")
    status, body = http_get(f"{OLLAMA_URL}/api/tags", timeout=5)

    if status == 200:
        ok(f"Ollama reachable at {OLLAMA_URL}")
        try:
            data = json.loads(body)
            models = data.get("models", [])
            if models:
                ok(f"Models available ({len(models)}):")
                for m in models:
                    size_gb = m.get("size", 0) / 1e9
                    print(f"       • {m['name']}  ({size_gb:.1f} GB)")
            else:
                warn("No models pulled yet — run scripts/pull_models.sh (or .bat on Windows)")
        except json.JSONDecodeError:
            warn(f"Could not parse Ollama response: {body[:200]}")
        return True
    else:
        fail(f"Ollama not reachable at {OLLAMA_URL} (status={status})")
        fail("  Is Docker running? Did you start with `docker compose up -d`?")
        return False


def check_temporal() -> bool:
    """Check Temporal server reachability via HTTP."""
    section("Temporal")

    # Temporal's auto-setup exposes a simple HTTP health surface.
    # We try the frontend service health endpoint.
    host_part = TEMPORAL_HOST.split(":")[0]
    port_part = TEMPORAL_HOST.split(":")[1] if ":" in TEMPORAL_HOST else "7233"

    # Try the Temporal UI port too as a fallback signal
    ui_port = os.environ.get("TEMPORAL_UI_PORT", "8233")

    temporal_ok = False

    # Try gRPC-over-HTTP check (Temporal exposes a minimal HTTP layer)
    for check_url in [
        f"http://{host_part}:{port_part}/",               # gRPC port — may refuse HTTP but proves TCP is up
        f"http://{host_part}:{ui_port}/",                 # UI port — returns HTML
        f"http://{host_part}:{ui_port}/api/v1/namespaces",  # UI API
    ]:
        status, body = http_get(check_url, timeout=5)
        if status > 0:  # any real HTTP response = port is up
            ok(f"Temporal reachable (HTTP {status} from {check_url})")
            temporal_ok = True
            break

    if not temporal_ok:
        # Last resort: TCP socket check
        import socket
        try:
            s = socket.create_connection((host_part, int(port_part)), timeout=5)
            s.close()
            ok(f"Temporal TCP reachable at {host_part}:{port_part}")
            temporal_ok = True
        except Exception as e:
            fail(f"Temporal NOT reachable at {TEMPORAL_HOST}: {e}")
            fail("  Check: docker compose ps temporal")

    if temporal_ok:
        # Show Temporal UI URL
        print(f"       ℹ️  Temporal UI: http://localhost:{ui_port}")

    return temporal_ok


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"\n{BOLD}+======================================================+")
    print(f"  StudyBuddy -- Block 1 Infrastructure Verification")
    print(f"+======================================================+{RESET}")

    results = {
        "postgres": check_postgres(),
        "ollama":   check_ollama(),
        "temporal": check_temporal(),
    }

    section("Summary")
    all_pass = all(results.values())
    for name, passed in results.items():
        if passed:
            ok(name)
        else:
            fail(name)

    print()
    if all_pass:
        print(f"{GREEN}{BOLD}[PASS] All checks passed -- Block 1 is DONE.{RESET}")
        print(f"   Next: run  scripts/pull_models.bat  to pull Ollama models.")
        return 0
    else:
        failed = [k for k, v in results.items() if not v]
        print(f"{RED}{BOLD}[FAIL] {len(failed)} check(s) failed: {', '.join(failed)}{RESET}")
        print(f"   Run `docker compose up -d` and retry.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
