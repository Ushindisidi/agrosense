import os
import time
import logging
import hashlib
from typing import List, Optional
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

# Import dependencies
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_cohere import CohereEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from pinecone.exceptions import PineconeException
from langchain_core.documents import Document

# Load environment variables
load_dotenv()

# configurations
DOCUMENTS_PATH = os.getenv("DOCUMENTS_PATH", "knowledge")
INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "agrosense")
COHERE_MODEL = os.getenv("COHERE_EMBEDDING_MODEL", "embed-english-v3.0")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1024"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
CLEAR_INDEX_BEFORE_INGEST = os.getenv("CLEAR_INDEX_BEFORE_INGEST", "false").lower() == "true"

#setting logging
LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"ingest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
#custom exception for ingestion errors
class IngestionError(Exception):
    pass
#initializing pinecone client and index
def initialize_pinecone() -> Optional[Pinecone]:
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        logger.error("PINECONE_API_KEY is not set in the environment.")
        return None
    try:
        pc = Pinecone(api_key=api_key)
        logger.info("Pinecone client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone client: {e}")
        return None

    existing_indexes = pc.list_indexes().names()
    if INDEX_NAME not in existing_indexes:
        logger.info(f"Creating new Pinecone index: '{INDEX_NAME}'...")
        try:
            pc.create_index(
                name=INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric='cosine',
                spec=ServerlessSpec(cloud='aws', region='us-east-1')
            )
            logger.info(f"Index '{INDEX_NAME}' created successfully.")
            time.sleep(5)
        except PineconeException as e:
            logger.error(f"Failed to create Pinecone index: {e}")
            return None
    else:
        logger.info(f"Pinecone index '{INDEX_NAME}' already exists.")
        if CLEAR_INDEX_BEFORE_INGEST:
            logger.warning(f"Clearing all vectors from index '{INDEX_NAME}'...")
            try:
                index = pc.Index(INDEX_NAME)
                index.delete(delete_all=True)
                logger.info("Index cleared successfully.")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to clear index: {e}")
    return pc
#determine asset type based on filename keywords.
def determine_asset_type(filename: str) -> str:
    filename_lower = filename.lower()
    livestock_keywords = ['livestock', 'animal', 'cattle', 'poultry', 'chicken', 'goat', 'sheep', 'pig', 'dairy']
    crop_keywords = ['crop', 'maize', 'corn', 'fertilizer', 'planting', 'harvest', 'seed', 'coffee', 'tea']
    if any(k in filename_lower for k in livestock_keywords):
        return 'LIVESTOCK'
    if any(k in filename_lower for k in crop_keywords):
        return 'CROP'
    return 'GENERAL'

#  Load and Chunk Documents
def load_and_chunk_documents() -> List[Document]:
    if not os.path.exists(DOCUMENTS_PATH):
        raise IngestionError(f"Documents directory not found: {DOCUMENTS_PATH}")
    pdf_files = [f for f in os.listdir(DOCUMENTS_PATH) if f.endswith(".pdf")]
    if not pdf_files:
        logger.warning(f"No PDF files found in '{DOCUMENTS_PATH}'.")
        return []
    documents = []
    for filename in pdf_files:
        file_path = os.path.join(DOCUMENTS_PATH, filename)
        asset_type = determine_asset_type(filename)
        try:
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            for page_num, page in enumerate(pages):
                page.metadata.update({
                    "source": filename,
                    "page": page_num + 1,
                    "asset_type": asset_type
                })
                documents.append(page)
        except Exception as e:
            logger.error(f"Error loading '{filename}': {e}")
    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(documents)
    logger.info(f"Created {len(chunks)} chunks total.")
    return chunks

#ingestion into pinecone in batches
def ingest_data(chunks: List[Document]) -> None:
    if not chunks:
        logger.warning("No chunks to ingest.")
        return
    embeddings = CohereEmbeddings(
        model=COHERE_MODEL,
        cohere_api_key=os.getenv("COHERE_API_KEY")
    )
    total_batches = (len(chunks) - 1) // BATCH_SIZE + 1
    for i in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        try:
            PineconeVectorStore.from_documents(
                documents=batch,
                embedding=embeddings,
                index_name=INDEX_NAME
            )
            logger.info(f"Batch {batch_num}/{total_batches} ingested successfully.")
        except Exception as e:
            logger.error(f"Batch {batch_num} failed: {e}")

def load_index():
    """
    Loads existing data from Pinecone index and allows user to query it.
    """
    try:
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
        index = pc.Index(INDEX_NAME)
        stats = index.describe_index_stats()
        logger.info(f"📦 Index '{INDEX_NAME}' info:")
        logger.info(f"→ Vector count: {stats.get('total_vector_count', 0)}")
        logger.info(f"→ Namespaces: {stats.get('namespaces', {})}")

        embeddings = CohereEmbeddings(
            model=COHERE_MODEL,
            cohere_api_key=os.getenv("COHERE_API_KEY")
        )

        # Interactive query mode
        logger.info("\n🧠 Enter your question below to query the knowledge base.")
        logger.info("Type 'exit' to quit.\n")

        while True:
            query = input("🔍 Your question: ").strip()
            if query.lower() in ["exit", "quit"]:
                logger.info("Goodbye! 👋")
                break

            try:
                # Convert question to embedding
                query_vector = embeddings.embed_query(query)

                # Query Pinecone index
                results = index.query(vector=query_vector, top_k=3, include_metadata=True)

                if not results.matches:
                    logger.info("No relevant results found.")
                    continue

                logger.info("\n=== TOP MATCHES ===")
                for match in results.matches:
                    metadata = match.metadata or {}
                    source = metadata.get("source", "Unknown source")
                    page = metadata.get("page", "?")
                    asset_type = metadata.get("asset_type", "?")
                    score = round(match.score, 4)
                    logger.info(f"\n📄 {source} (Page {page}) | Type: {asset_type} | Score: {score}")
                    logger.info(f"Content: {metadata.get('text', '')[:400]}...")
                logger.info("=" * 50)

            except Exception as e:
                logger.error(f"Error during query: {e}")

    except Exception as e:
        logger.error(f"Error loading index: {e}")

# --- Main Pipeline ---
def run_ingestion() -> bool:
    try:
        pc = initialize_pinecone()
        chunks = load_and_chunk_documents()
        ingest_data(chunks)
        return True
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return False

# --- CLI Entrypoint ---
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🌾 AGROSENSE VECTOR STORE TOOL")
    logger.info("=" * 60)

    choice = input("Enter mode [ingest/load]: ").strip().lower()
    if choice == "ingest":
        success = run_ingestion()
        exit(0 if success else 1)
    elif choice == "load":
        load_index()
    else:
        logger.warning("Invalid choice. Please use 'ingest' or 'load'.")
