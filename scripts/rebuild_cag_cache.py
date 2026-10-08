import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Add the source directory to the module search path.
sys.path.insert(0, os.path.abspath('src'))

from loguru import logger
from infrastructure.llm import get_chat_llm, get_default_embeddings
from infrastructure.config import load_faqs
from agents.tools.rag_tool import RAGTool

def rebuild_cag_cache():
    logger.info("Initializing Embedder and RAG Tool...")
    # RAGTool initializes the CRAG service with an LLM even when cache entries
    # already contain deterministic FAQ answers.
    llm = get_chat_llm()
    embedder = get_default_embeddings()
    
    rag_tool = RAGTool(embedder=embedder, llm=llm)
    
    logger.info("Clearing the existing CAG cache...")
    rag_tool.clear_cache()
    
    logger.info("Loading FAQ entries from config/faqs.yaml...")
    faqs = load_faqs()
    logger.info(f"   Loaded {len(faqs)} explicit query/answer pairs.")
    
    if not faqs:
        logger.error("No FAQs loaded. Make sure config/faqs.yaml exists and is formatted correctly.")
        return

    logger.info("Warming the CAG cache...")
    cached_count = rag_tool.warm_cache(faqs)
    
    logger.success(f"Successfully cached {cached_count} items into the cag_cache.")
    
    logger.info("Checking the cache with a known query...")
    # Query one configured FAQ entry to confirm cache retrieval.
    test_query = faqs[0]['query']
    result = rag_tool.search(test_query)
    logger.info(f"Test Query: {test_query}")
    logger.info(f"Output Answer from Cache: {result}")

if __name__ == "__main__":
    rebuild_cag_cache()
