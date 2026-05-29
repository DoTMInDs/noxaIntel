import logging
from django.utils import timezone
from services.cache_service import CacheService
from services.voice_service import VoiceService

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
        """Processes query via VoiceService, updates session history, and returns response."""
        # 1. Add user message to history
        AIChatService.add_message(user.id, "user", query)

        # 2. Query VoiceService to get backend structured response
        response_text = VoiceService.parse_voice_command(query, user)

        # 3. Add AI message to history
        AIChatService.add_message(user.id, "ai", response_text)

        return response_text
