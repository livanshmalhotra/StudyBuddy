import httpx
from tenacity import retry, wait_exponential, stop_after_attempt
from core.config import settings

@retry(wait=wait_exponential(multiplier=2, min=2, max=10), stop=stop_after_attempt(3))
def embed_single(text: str, model: str) -> list[float]:
    url = f"{settings.OLLAMA_BASE_URL}/api/embeddings"
    payload = {
        "model": model,
        "prompt": text
    }
    with httpx.Client() as client:
        response = client.post(url, json=payload, timeout=60.0)
        response.raise_for_status()
        return response.json()["embedding"]

def embed_batch(texts: list[str], model: str = None, batch_size: int = None) -> list[list[float]]:
    """
    Calls POST /api/embeddings on Ollama in batches.
    Retries with exponential backoff (tenacity: 3 attempts, 2s base).
    Returns list of 1024-dim float vectors.
    """
    if model is None:
        model = settings.EMBED_MODEL
    if batch_size is None:
        batch_size = settings.EMBED_BATCH_SIZE
        
    results = []
    
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        for text in batch:
            vec = embed_single(text, model)
            results.append(vec)
            
    return results
