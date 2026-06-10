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
    def load_context(user, request=None):
        """Loads active query context from Redis cache, session, and ConversationContext database model."""
        from django.core.cache import cache
        cache_key = f"copilot_context_{user.id}"
        
        # 1. Try Redis cache
        context = cache.get(cache_key)
        if context:
            logger.info(f"[AIChatService] Loaded context from Redis: {context}")
            return context
            
        # 2. Try Django session state
        if request and hasattr(request, 'session'):
            context = request.session.get('copilot_context')
            if context:
                logger.info(f"[AIChatService] Loaded context from Django Session: {context}")
                cache.set(cache_key, context, timeout=1800)
                return context

        # 3. Try ConversationContext database model
        try:
            from ai_engine.models import ConversationContext
            conv_ctx, created = ConversationContext.objects.get_or_create(user=user)
            if conv_ctx.context_data:
                context = conv_ctx.context_data
                logger.info(f"[AIChatService] Loaded context from DB Model: {context}")
                cache.set(cache_key, context, timeout=1800)
                if request and hasattr(request, 'session'):
                    request.session['copilot_context'] = context
                return context
        except Exception as e:
            logger.error(f"[AIChatService] Error loading context from DB: {e}")

        return {}

    @staticmethod
    def save_context(user, context, request=None):
        """Saves active query context to Redis cache, session, and ConversationContext database model."""
        from django.core.cache import cache
        cache_key = f"copilot_context_{user.id}"
        
        # 1. Save to Redis cache
        cache.set(cache_key, context, timeout=1800)
        
        # 2. Save to Django session state
        if request and hasattr(request, 'session'):
            request.session['copilot_context'] = context
            request.session.modified = True
            
        # 3. Save to ConversationContext database model
        try:
            from ai_engine.models import ConversationContext
            ConversationContext.objects.update_or_create(
                user=user,
                defaults={'context_data': context}
            )
            logger.info(f"[AIChatService] Saved context successfully: {context}")
        except Exception as e:
            logger.error(f"[AIChatService] Error saving context to DB: {e}")

    @staticmethod
    def generate_response(query, user, request=None):
        """Processes query via the RAG Pipeline: Intent Router -> RAG Retrieval -> LLM Explanation."""
        # 1. Fetch current conversation history *before* adding the new message
        history = AIChatService.get_conversation_history(user.id)

        # 2. Add user message to history
        AIChatService.add_message(user.id, "user", query)

        # 3. Load active context
        active_context = AIChatService.load_context(user, request)

        # 4. Intent Detection (Context-Aware)
        intent, params = IntentRouter.route(query, history)

        # 5. Entity resolution using active context (if query didn't specify them)
        resolved_teams = params.get('teams', [])
        resolved_player = params.get('player')
        resolved_league = params.get('league')

        if not resolved_teams and active_context.get('teams'):
            resolved_teams = active_context['teams']
            params['teams'] = resolved_teams
            params['resolved_from_history'] = True
            logger.info(f"[AIChatService] Resolved teams from saved context: {resolved_teams}")

        if not resolved_player and active_context.get('player'):
            resolved_player = active_context['player']
            params['player'] = resolved_player
            params['resolved_from_history'] = True
            logger.info(f"[AIChatService] Resolved player from saved context: {resolved_player}")

        if not resolved_league and active_context.get('league'):
            resolved_league = active_context['league']
            params['league'] = resolved_league
            params['resolved_from_history'] = True
            logger.info(f"[AIChatService] Resolved league from saved context: {resolved_league}")

        # 6. Save updated active context if entities are present
        new_context = {}
        if resolved_teams:
            new_context['teams'] = resolved_teams
        if resolved_player:
            new_context['player'] = resolved_player
        if resolved_league:
            new_context['league'] = resolved_league

        if new_context:
            AIChatService.save_context(user, new_context, request)

        # 7. Information Retrieval (RAG)
        context = RetrievalService.retrieve_context(intent, params, user)

        # 8. LLM Explanation Layer
        response_text = LLMExplanationLayer.explain(query, intent, context, user, history)

        # 9. Add AI response to history
        AIChatService.add_message(user.id, "ai", response_text)

        return response_text

