import logging
from django.utils import timezone
from services.cache_service import CacheService
from services.intent_router import IntentRouter
from services.retrieval_service import RetrievalService
from services.llm_explanation_layer import LLMExplanationLayer

logger = logging.getLogger('ai_engine')

class AIChatService:
    """Manages chat message history and handles conversation context."""

    @staticmethod
    def get_conversation_history(user_id):
        """Retrieves conversational logs from cache."""
        return CacheService.get_voice_history(user_id)

    @staticmethod
    def add_message(user_id, sender, text):
        """Appends a message to the cached history list."""
        history = AIChatService.get_conversation_history(user_id)
        history.append({
            "sender": sender,
            "text": text,
            "timestamp": timezone.now().strftime("%H:%M")
        })
        # Keep last 15 messages to prevent cache bloat
        if len(history) > 15:
            history = history[-15:]
        CacheService.set_voice_history(user_id, history)

    @staticmethod
    def generate_response(query, user):
        """Processes query via the RAG Pipeline: Intent Router -> RAG Retrieval -> LLM Explanation."""
        # 1. Fetch current conversation history *before* adding the new message
        history = AIChatService.get_conversation_history(user.id)

        # 2. Add user message to history
        AIChatService.add_message(user.id, "user", query)

        # 3. Intent Detection (Context-Aware)
        intent, params = IntentRouter.route(query, history)

        # 4. Information Retrieval (RAG)
        context = RetrievalService.retrieve_context(intent, params, user)

        # 5. LLM Explanation Layer
        response_text = LLMExplanationLayer.explain(query, intent, context, user)

        # 6. Add AI response to history
        AIChatService.add_message(user.id, "ai", response_text)

        return response_text

