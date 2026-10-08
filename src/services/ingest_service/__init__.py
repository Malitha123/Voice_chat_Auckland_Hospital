"""
Ingest services — web crawling, document chunking, Qdrant pipeline.
"""

from .chunkers import (
    ChunkingService,
    semantic_chunk,
    fixed_chunk,
    sliding_chunk,
    parent_child_chunk,
    late_chunk_index,
    late_chunk_split,
    count_tokens,
)
from .web_crawler import AucklandHospitalWebCrawler
from .pipeline import run_ingest

__all__ = [
    # Chunking
    "ChunkingService",
    "semantic_chunk",
    "fixed_chunk",
    "sliding_chunk",
    "parent_child_chunk",
    "late_chunk_index",
    "late_chunk_split",
    "count_tokens",
    # Web crawling
    "AucklandHospitalWebCrawler",
    # Ingestion pipeline
    "run_ingest",
]
