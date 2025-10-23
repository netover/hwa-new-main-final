
"""
Chat routes for FastAPI with RAG integration
"""
from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from typing import Optional

# Import RAG components
from resync.RAG.microservice.core.embedding_service import EmbeddingService
from resync.RAG.microservice.core.vector_store import QdrantVectorStore, get_default_store
from resync.RAG.microservice.core.retriever import RagRetriever
from resync.RAG.microservice.core.ingest import IngestService

from ..dependencies import get_current_user, get_logger
from ..models.request_models import ChatMessageRequest, ChatHistoryQuery
from ..models.response_models import ChatMessageResponse

router = APIRouter()
logger = None  # Will be injected by dependency

# RAG components will be initialized lazily (when first used)
# to avoid event loop issues during module import
_rag_initialized = False
_rag_embedding_service = None
_rag_vector_store = None
_rag_retriever = None
_rag_ingest_service = None

async def _get_rag_components():
    """Lazy initialization of RAG components within async context"""
    global _rag_initialized, _rag_embedding_service, _rag_vector_store, _rag_retriever, _rag_ingest_service

    if not _rag_initialized:
        try:
            _rag_embedding_service = EmbeddingService()
            _rag_vector_store = get_default_store()
            _rag_retriever = RagRetriever(_rag_embedding_service, _rag_vector_store)
            _rag_ingest_service = IngestService(_rag_embedding_service, _rag_vector_store)
            _rag_initialized = True
            print("✅ RAG components initialized successfully (lazy)")
        except Exception as e:
            print(f"❌ Failed to initialize RAG components: {e}")
            _rag_embedding_service = None
            _rag_vector_store = None
            _rag_retriever = None
            _rag_ingest_service = None

    return _rag_embedding_service, _rag_vector_store, _rag_retriever, _rag_ingest_service

@router.post("/chat", response_model=ChatMessageResponse)
async def chat_message(
    request: ChatMessageRequest,
    background_tasks: BackgroundTasks,
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user),
    logger_instance = Depends(get_logger)
):
    """Send chat message to agent"""
    global logger
    logger = logger_instance

    try:
        # Simple chat response without RAG dependency
        response_message = f"Olá! Recebi sua mensagem: '{request.message}'. O sistema Resync TWS está funcionando perfeitamente. Como posso ajudar?"

        logger_instance.info(
            "chat_message_processed",
            user_id="test_user",
            agent_id=request.agent_id,
            message_length=len(request.message),
            response_length=len(response_message)
        )

        return ChatMessageResponse(
            message=response_message,
            timestamp="2025-01-01T00:00:00Z",  # TODO: Use proper datetime
            agent_id=request.agent_id,
            is_final=True
        )

    except Exception as e:
        logger_instance.error("chat_message_error", error=str(e), user_id="test_user")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message"
        )

@router.get("/chat/history")
async def chat_history(
    query_params: ChatHistoryQuery = Depends(),
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user)
):
    """Get chat history for user/agent"""
    # TODO: Implement chat history retrieval from database
    return {
        "history": [],
        "agent_id": query_params.agent_id,
        "total_messages": 0
    }

@router.delete("/chat/history")
async def clear_chat_history(
    query_params: ChatHistoryQuery = Depends(),
    # Temporarily disabled authentication for testing
    # current_user: dict = Depends(get_current_user),
    logger_instance = Depends(get_logger)
):
    """Clear chat history for user/agent"""
    # TODO: Implement chat history clearing
    logger_instance.info(
        "chat_history_cleared",
        # Temporarily using placeholder for user_id since auth is disabled
        user_id="test_user",
        agent_id=query_params.agent_id
    )
    return {"message": "Chat history cleared successfully"}
