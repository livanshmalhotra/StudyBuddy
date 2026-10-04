"""
watcher/watcher.py — watchdog file system watcher
Monitors UPLOAD_DIR for new/modified files, calls POST /ingest.
Monitors deletions, calls DELETE /documents/{filename}.
Debounce: waits 2s after last event before firing (avoids partial file reads).
Run: python watcher/watcher.py  (from the project root)
"""
from __future__ import annotations

import logging
import sys
import time
import threading
from pathlib import Path

# Ensure the project root is on sys.path so `core.*` is importable when this
# script is run directly (e.g. `python watcher/watcher.py`).
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import httpx
from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from core.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

API_BASE = f"http://{settings.API_HOST if settings.API_HOST != '0.0.0.0' else 'localhost'}:{settings.API_PORT}"
DEBOUNCE_SECONDS = 2.0
IGNORED_NAMES = {".gitkeep", ".DS_Store", "Thumbs.db"}
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".png", ".jpg", ".jpeg"}


class DebounceHandler(FileSystemEventHandler):
    """Debounces file events — only fires after DEBOUNCE_SECONDS of quiet per path."""

    def __init__(self):
        super().__init__()
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _schedule(self, path: str, action: str):
        with self._lock:
            if path in self._timers:
                self._timers[path].cancel()
            timer = threading.Timer(DEBOUNCE_SECONDS, self._fire, args=(path, action))
            self._timers[path] = timer
            timer.start()

    def _fire(self, path: str, action: str):
        with self._lock:
            self._timers.pop(path, None)
        if action == "ingest":
            _post_ingest(path)
        elif action == "delete":
            _delete_document(Path(path).name)

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.name in IGNORED_NAMES or p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        logger.info(f"[created] {p.name} — scheduling ingest in {DEBOUNCE_SECONDS}s")
        self._schedule(str(p), "ingest")

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.name in IGNORED_NAMES or p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return
        logger.info(f"[modified] {p.name} — scheduling ingest in {DEBOUNCE_SECONDS}s")
        self._schedule(str(p), "ingest")

    def on_deleted(self, event: FileSystemEvent):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if p.name in IGNORED_NAMES:
            return
        logger.info(f"[deleted] {p.name} — scheduling delete in {DEBOUNCE_SECONDS}s")
        self._schedule(str(p), "delete")


def _post_ingest(abs_path: str):
    url = f"{API_BASE}/ingest"
    try:
        resp = httpx.post(url, json={"path": abs_path}, timeout=10.0)
        resp.raise_for_status()
        logger.info(f"[ingest] {Path(abs_path).name} → {resp.json()}")
    except Exception as exc:
        logger.error(f"[ingest] failed for {abs_path}: {exc}")


def _delete_document(filename: str):
    url = f"{API_BASE}/documents/{filename}"
    try:
        resp = httpx.delete(url, timeout=10.0)
        if resp.status_code == 404:
            logger.info(f"[delete] {filename} not in DB (already gone)")
        else:
            resp.raise_for_status()
            logger.info(f"[delete] {filename} removed from DB")
    except Exception as exc:
        logger.error(f"[delete] failed for {filename}: {exc}")


def main():
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Watching {upload_dir} — API at {API_BASE}")

    event_handler = DebounceHandler()
    observer = Observer()
    observer.schedule(event_handler, str(upload_dir), recursive=False)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Watcher stopping...")
        observer.stop()
    observer.join()


if __name__ == "__main__":
    main()
