import os
import logging
from typing import List, Any, Type
from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict

from ..core.mcp_client import MCPClient
from ..core.schemas import SourceDocument, AssetType

logger = logging.getLogger(__name__)

class RAGToolInput(BaseModel):
    session_id: str
    query: str
    asset_type: str = "GENERAL"
    top_k: int = 5

class RAGTool(BaseTool):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "Agricultural_Knowledge_Search"
    description: str = (
        "Search the agricultural knowledge base for relevant information. "
        "Use session_id to store results in the MCPContext."
    )
    args_schema: Type[BaseModel] = RAGToolInput
    mcp_client: MCPClient = Field(default=None, description="The Multi-Context Processor client instance for state management.")
    
    _pc: Any = PrivateAttr()
    _index: Any = PrivateAttr()
    _cohere: Any = PrivateAttr()

    def __init__(self, mcp_client: MCPClient = None, **kwargs):
        # Pass mcp_client as a keyword argument to super().__init__
        super().__init__(mcp_client=mcp_client, **kwargs)

        try:
            from pinecone import Pinecone
            import cohere

            # Load environment variables
            api_key = os.getenv("PINECONE_API_KEY")
            index_name = os.getenv("PINECONE_INDEX_NAME")
            cohere_key = os.getenv("COHERE_API_KEY")

            if not api_key or not index_name or not cohere_key:
                raise ValueError("Pinecone or Cohere API keys missing!")

            # Initialize Pinecone with new SDK
            self._pc = Pinecone(api_key=api_key)
            
            # Connect to the index
            self._index = self._pc.Index(index_name)

            # Initialize Cohere
            self._cohere = cohere.Client(cohere_key)

            logger.info(f"✅ RAGTool connected to Pinecone index '{index_name}' + Cohere embeddings.")

        except Exception as e:
            # Fallback to mock mode if real services fail
            self._pc = None
            self._index = None
            self._cohere = None
            logger.warning(f"⚠️ RAGTool using MOCK mode. Reason: {e}")

    def _generate_embedding(self, text: str) -> list[float]:
        if self._cohere:
            response = self._cohere.embed(
                texts=[text], 
                model="embed-english-v3.0",
                input_type="search_query"
            )
            return response.embeddings[0]
        else:
            return [0.0] * 1024  # mock embedding (Cohere embed-english-v3.0 uses 1024 dimensions)

    def _run(self, session_id: str, query: str, asset_type: str = "GENERAL", top_k: int = 5) -> str:
        if not self._index:
            return self._run_mock(session_id, query, asset_type, top_k)

        try:
            embedding = self._generate_embedding(query)

            # Query Pinecone
            results = self._index.query(
                vector=embedding,
                top_k=top_k,
                filter={"asset_type": {"$eq": asset_type.upper()}},
                include_metadata=True
            )

            retrieved_docs = []
            for match in results.matches:
                meta = match.metadata
                retrieved_docs.append(
                    SourceDocument(
                        content=meta.get("text", "No content"),
                        source=meta.get("source", "Pinecone"),
                        page=int(meta.get("page", 0)),
                        asset_type=AssetType(meta.get("asset_type", "GENERAL").upper()),
                        score=match.score,
                    )
                )

            self.mcp_client.update_context(session_id, retrieved_context=retrieved_docs)
            logger.info(f"✅ Retrieved {len(retrieved_docs)} documents from Pinecone for session {session_id}.")
            return f"✅ Retrieved {len(retrieved_docs)} documents from Pinecone for session {session_id}."
        
        except Exception as e:
            logger.error(f"Error querying Pinecone: {e}")
            return self._run_mock(session_id, query, asset_type, top_k)

    def _run_mock(self, session_id: str, query: str, asset_type: str, top_k: int) -> str:
        logger.info(f"RAGTool running in MOCK mode for session {session_id}.")
        retrieved_docs = [
            SourceDocument(
                content="Mock document content for query.",
                source="MOCK_SOURCE",
                page=1,
                asset_type=AssetType.GENERAL,
                score=1.0
            )
        ]
        self.mcp_client.update_context(session_id, retrieved_context=retrieved_docs)
        return f"MOCK SUCCESS: {len(retrieved_docs)} mock documents retrieved for session {session_id}."