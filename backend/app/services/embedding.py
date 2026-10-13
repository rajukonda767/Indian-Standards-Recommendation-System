"""
embedding.py
============
Persistent singleton service for BAAI/bge-m3 embedding inference on NVIDIA GPU.
"""

import os
import logging
import time
from typing import List

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import torch
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    _instance = None

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Loading embedding model '{settings.EMBEDDING_MODEL_NAME}' on {self.device.upper()}...")
        t0 = time.time()
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME, device=self.device)
        if self.device == "cuda":
            self.model.half()  # FP16 mode for RTX 3050 VRAM efficiency and 2x speed
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"Loaded '{settings.EMBEDDING_MODEL_NAME}' on {gpu_name} (FP16) in {time.time() - t0:.2f}s")
        else:
            logger.info(f"Loaded '{settings.EMBEDDING_MODEL_NAME}' on CPU in {time.time() - t0:.2f}s")

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def embed_query(self, text: str) -> List[float]:
        """Encodes query into 1024-dimensional normalized float list."""
        embeddings = self.model.encode(
            [text],
            normalize_embeddings=True,
            show_progress_bar=False
        )
        return embeddings[0].tolist()

embedding_service = EmbeddingService.get_instance
