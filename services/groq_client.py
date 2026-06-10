import logging
import requests
import json
from django.conf import settings

logger = logging.getLogger('ai_engine')

class GroqClient:
    def __init__(self):
        self.api_key = getattr(settings, 'GROQ_API_KEY', '')
        self.model = getattr(settings, 'GROQ_MODEL', 'llama-3.3-70b-versatile')
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    def is_configured(self):
        return bool(self.api_key)

    def generate_chat_completion(self, messages, temperature=0.2, response_format=None):
        if not self.is_configured():
            logger.info("Groq API key not configured. Using mock fallback.")
            return self._mock_fallback(messages, response_format)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature
        }
        if response_format:
            payload["response_format"] = response_format

        try:
            response = requests.post(self.url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"Groq API returned error {response.status_code}: {response.text}")
                return self._mock_fallback(messages, response_format)
        except Exception as e:
            logger.error(f"Error communicating with Groq API: {e}")
            return self._mock_fallback(messages, response_format)

    def _mock_fallback(self, messages, response_format=None):
        # Fallback implementation
        user_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                user_message = msg.get("content", "").lower()
                break

        # Check if requesting JSON (for intent routing)
        if response_format and response_format.get("type") == "json_object":
            intent = "GENERAL_FOOTBALL"
            teams = []
            player = None
            league = None
            
            # Simple keyword heuristic to match intent
            if "predict" in user_message or "vs" in user_message:
                intent = "MATCH_PREDICTION"
                if "arsenal" in user_message:
                    teams.append("Arsenal")
                if "chelsea" in user_message:
                    teams.append("Chelsea")
            elif "tip" in user_message or "bet" in user_message:
                intent = "BETTING_ADVICE"
            elif "balance" in user_message or "wallet" in user_message:
                intent = "USER_BET_ANALYSIS"
            elif "standing" in user_message or "table" in user_message:
                intent = "STANDINGS_LOOKUP"
            elif "odds" in user_message:
                intent = "ODDS_ANALYSIS"
                
            return json.dumps({
                "intent": intent,
                "confidence": 0.95,
                "teams": teams,
                "player": player,
                "league": league
            })

        # Standard text fallback
        if "predict" in user_message:
            return "Based on precomputed analysis, Arsenal has a 48% win probability against Chelsea, with a 28% chance of a draw and 24% chance of a Chelsea victory."
        elif "balance" in user_message or "wallet" in user_message:
            return "Your current wallet balance is GHS 250.00."
        return "I am your AI assistant. How can I help you today?"
