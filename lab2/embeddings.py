import os
import requests

from dotenv import load_dotenv
from langchain_core.embeddings import Embeddings

load_dotenv()


class OpenRouterEmbeddings(Embeddings):
    """
    Custom Embedding class that calls the OpenRouter Embeddings API.
    """

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY")

        self.base_url = os.getenv(
            "LLM_BASE_URL",
            "https://openrouter.ai/api/v1"
        )

        self.model = os.getenv(
            "EMBEDDING_MODEL",
            "google/gemini-embedding-001"
        )

        if not self.api_key:
            raise ValueError(
                "OPENROUTER_API_KEY not found in .env"
            )

    def _request_embedding(self, text: str):

        response = requests.post(
            f"{self.base_url}/embeddings",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "input": text,
                "encoding_format": "float"
            },
            timeout=60
        )

        response.raise_for_status()

        data = response.json()

        return data["data"][0]["embedding"]

    def embed_query(self, text: str):
        """
        Generate embedding for a single query.
        """
        return self._request_embedding(text)

    def embed_documents(self, texts):
        """
        Generate embeddings for multiple documents.
        """
        return [
            self._request_embedding(text)
            for text in texts
        ]