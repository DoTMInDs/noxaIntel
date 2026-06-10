import re
import logging

logger = logging.getLogger('ai_engine')

class IntentRouter:
    """Classifies user queries into semantic football intents and extracts parameters, resolving context."""

    INTENTS = {
        'MATCH_PREDICTION': 'Match Prediction',
        'WINNING_PROBABILITY': 'Winning Probability',
        'SCORE_PREDICTION': 'Score Prediction',
        'TEAM_ANALYSIS': 'Team Analysis',
        'PLAYER_ANALYSIS': 'Player Analysis',
        'LIVE_MATCH_LOOKUP': 'Live Match Lookup',
        'FIXTURES_LOOKUP': 'Fixtures Lookup',
        'STANDINGS_LOOKUP': 'Standings Lookup',
        'INJURY_LOOKUP': 'Injury Lookup',
        'ODDS_ANALYSIS': 'Odds Analysis',
        'BETTING_ADVICE': 'Betting Advice',
        'OVER_UNDER_ANALYSIS': 'Over/Under Analysis',
        'BTTS_ANALYSIS': 'Both Teams To Score Analysis',
        'H2H_ANALYSIS': 'Head-to-Head Analysis',
        'USER_BET_ANALYSIS': 'User Bet Analysis',
        'GENERAL_FOOTBALL': 'General Football Questions'
    }

    _TEAM_ALIASES = {
        "city": "manchester city",
        "man city": "manchester city",
        "mancity": "manchester city",
        "united": "manchester united",
        "man united": "manchester united",
        "manunited": "manchester united",
        "madrid": "real madrid",
        "real": "real madrid",
        "barca": "barcelona",
        "bvb": "dortmund",
        "juve": "juventus",
        "atletico": "atletico madrid",
        "spurs": "tottenham",
        "villa": "aston villa",
        "blues": "chelsea",
        "reds": "liverpool",
        "gunners": "arsenal",
        "gooners": "arsenal",
        "bayern": "bayern munich",
        "dortmund": "borussia dortmund",
        "leipzig": "rb leipzig",
        "leverkusen": "leverkusen",
        "inter": "inter milan",
        "milan": "ac milan",
    }

    _TEAM_LIST = [
        "arsenal", "manchester city", "manchester united", "liverpool", "chelsea",
        "tottenham", "aston villa", "newcastle", "west ham", "brighton", "everton",
        "barcelona", "real madrid", "atletico madrid", "sevilla", "valencia",
        "bayern munich", "borussia dortmund", "rb leipzig", "leverkusen", "wolfsburg",
        "inter milan", "ac milan", "juventus", "napoli", "roma", "lazio",
        "psg", "marseille", "lyon", "monaco", "lens",
        "ajax", "psv", "feyenoord", "porto", "benfica", "sporting",
        "celtic", "rangers"
    ]

    _PLAYERS = [
        "haaland", "saka", "salah", "mbappe", "palmer", "kane", "foden", "messi", 
        "ronaldo", "de bruyne", "odegaard", "rice", "bellingham", "vinicius", "rodri"
    ]

    _LEAGUES = {
        "epl": "Premier League",
        "premier league": "Premier League",
        "la liga": "La Liga",
        "laliga": "La Liga",
        "bundesliga": "Bundesliga",
        "serie a": "Serie A",
        "ligue 1": "Ligue 1",
    }

    @classmethod
    def extract_teams(cls, text: str):
        """Extracts up to 2 team names from text."""
        q = text.lower()
        # Clean common words that might clash
        q = re.sub(r'\b(the|a|an|versus|vs|against|v|and|or)\b', ' ', q)

        # First substitute aliases
        for alias, canon in cls._TEAM_ALIASES.items():
            # Match word boundary
            q = re.sub(rf'\b{alias}\b', canon, q)

        found = []
        # Look for exact canonical team matches
        for team in cls._TEAM_LIST:
            if team in q:
                # Avoid matching subparts incorrectly (e.g. 'manchester' in 'manchester city')
                if team == "manchester united" or team == "manchester city":
                    found.append(team)
                elif "manchester" not in team and team in q:
                    # check for milan and inter milan overlap
                    if team == "ac milan" or team == "inter milan":
                        found.append(team)
                    elif team == "milan" and ("ac milan" in found or "inter milan" in found):
                        continue
                    else:
                        found.append(team)
        
        # Deduplicate
        seen = set()
        dedup = []
        for f in found:
            if f not in seen:
                seen.add(f)
                dedup.append(f)
        return dedup[:2]

    @classmethod
    def extract_player(cls, text: str):
        q = text.lower()
        for p in cls._PLAYERS:
            if p in q:
                return p.capitalize()
        return None

    @classmethod
    def extract_league(cls, text: str):
        q = text.lower()
        for alias, name in cls._LEAGUES.items():
            if alias in q:
                return name
        return None

    @classmethod
    def _matches_pattern(cls, text: str, keywords: list) -> bool:
        """Helper to match keywords as complete tokens or exact multi-word phrases to avoid substring clashing."""
        tokens = set(re.split(r'\W+', text))
        for kw in keywords:
            if ' ' in kw:
                if kw in text:
                    return True
            else:
                if kw in tokens:
                    return True
        return False

    @classmethod
    def route(cls, query: str, history=None):
        """
        Determines the intent and extracts parameters.
        history: List of past messages e.g. [{'sender': 'user', 'text': '...'}]
        """
        q = query.strip().lower()
        history = history or []

        # Try Groq-powered semantic routing
        try:
            from services.groq_client import GroqClient
            client = GroqClient()
            system_prompt = (
                "You are an expert intent router for a football analytics and betting assistant. "
                "Your task is to classify the user's query into one of these INTENT codes:\n"
                "- MATCH_PREDICTION\n- WINNING_PROBABILITY\n- SCORE_PREDICTION\n- TEAM_ANALYSIS\n"
                "- PLAYER_ANALYSIS\n- LIVE_MATCH_LOOKUP\n- FIXTURES_LOOKUP\n- STANDINGS_LOOKUP\n"
                "- INJURY_LOOKUP\n- ODDS_ANALYSIS\n- BETTING_ADVICE\n- OVER_UNDER_ANALYSIS\n"
                "- BTTS_ANALYSIS\n- H2H_ANALYSIS\n- USER_BET_ANALYSIS\n- GENERAL_FOOTBALL\n\n"
                "Extract entities:\n"
                "- teams: list of canonical team names in query/history (e.g. ['Arsenal', 'Chelsea'])\n"
                "- player: string or null\n"
                "- league: string or null\n\n"
                "Use the chat history to resolve follow-up queries or pronouns.\n"
                "You must respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                "  \"intent\": \"INTENT_CODE\",\n"
                "  \"confidence\": 0.95,\n"
                "  \"teams\": [\"Team A\", \"Team B\"],\n"
                "  \"player\": \"Player Name\",\n"
                "  \"league\": \"League Name\"\n"
                "}"
            )
            messages = [{"role": "system", "content": system_prompt}]
            for h_msg in history[-5:]:
                role = "user" if h_msg.get('sender') == 'user' else "assistant"
                messages.append({"role": role, "content": h_msg.get('text', '')})
            
            messages.append({"role": "user", "content": query})
            
            res = client.generate_chat_completion(messages, temperature=0.0, response_format={"type": "json_object"})
            if res:
                import json
                parsed = json.loads(res)
                intent = parsed.get("intent", "GENERAL_FOOTBALL")
                if intent not in cls.INTENTS:
                    intent = "GENERAL_FOOTBALL"
                
                teams = parsed.get("teams", [])
                player = parsed.get("player")
                league = parsed.get("league")
                
                params = {
                    'teams': teams,
                    'player': player,
                    'league': league,
                    'resolved_from_history': True
                }
                logger.info(f"[IntentRouter Groq] Routed '{query}' -> Intent: {intent}, Params: {params}")
                return intent, params
        except Exception as e:
            logger.warning(f"Groq intent routing failed: {e}. Falling back to rule-based router.")

        # 1. Parameter extraction
        teams = cls.extract_teams(q)
        player = cls.extract_player(q)
        league = cls.extract_league(q)
        resolved_from_history = False

        # If no teams found in query, check history (context-awareness)
        if not teams and history:
            for msg in reversed(history):
                hist_text = msg.get('text', '')
                hist_teams = cls.extract_teams(hist_text)
                if hist_teams:
                    teams = hist_teams
                    resolved_from_history = True
                    logger.info(f"[IntentRouter] Context inheritance: resolved teams {teams} from history.")
                    break
        
        # Resolve league from history if missing
        if not league and history:
            for msg in reversed(history):
                hist_text = msg.get('text', '')
                hist_league = cls.extract_league(hist_text)
                if hist_league:
                    league = hist_league
                    break

        # 2. Intent Classification based on semantic patterns
        intent = 'GENERAL_FOOTBALL'

        # User bets, wallet, balance check
        if cls._matches_pattern(q, ['balance', 'wallet', 'funds', 'deposit', 'withdraw', 'my money', 'cash out', 'payout', 'my bet', 'active bet', 'open bet', 'bet history', 'past bet', 'settled bet']):
            intent = 'USER_BET_ANALYSIS'
        
        # Live matches
        elif cls._matches_pattern(q, ['live', 'in play', 'in-play', 'ongoing', 'current score', 'score right now', 'playing now']):
            intent = 'LIVE_MATCH_LOOKUP'

        # Standings
        elif cls._matches_pattern(q, ['standings', 'standing', 'table', 'rank', 'ranking', 'leaderboard', 'top of the']):
            intent = 'STANDINGS_LOOKUP'

        # Injuries
        elif cls._matches_pattern(q, ['injury', 'injuries', 'injured', 'fitness', 'unavailable', 'out list', 'suspended', 'suspension', 'medical']):
            intent = 'INJURY_LOOKUP'

        # Player Analysis
        elif player or cls._matches_pattern(q, ['player stats', 'top scorer', 'assists list', 'goals by', 'how many goals did']):
            intent = 'PLAYER_ANALYSIS'

        # Head to Head
        elif cls._matches_pattern(q, ['h2h', 'head to head', 'head-to-head', 'previous meetings', 'history between', 'past matches']):
            intent = 'H2H_ANALYSIS'

        # Odds analysis
        elif cls._matches_pattern(q, ['odds', 'bookmaker', 'value line', 'odds snapshot', 'pricing', 'underdog', 'favorite']):
            # If also prediction related
            if cls._matches_pattern(q, ['predict', 'winner', 'winning']):
                intent = 'WINNING_PROBABILITY'
            else:
                intent = 'ODDS_ANALYSIS'

        # Over / Under
        elif cls._matches_pattern(q, ['over/under', 'over under', 'o2.5', 'u2.5', 'over 2.5', 'under 2.5', 'total goals', 'goals line']):
            intent = 'OVER_UNDER_ANALYSIS'

        # BTTS
        elif cls._matches_pattern(q, ['btts', 'both teams to score', 'btts yes', 'btts no', 'goal goal', 'clean sheet']):
            intent = 'BTTS_ANALYSIS'

        # Score prediction
        elif cls._matches_pattern(q, ['score', 'correct score', 'exact score', 'predict score', 'final score']):
            intent = 'SCORE_PREDICTION'

        # Winning Probability
        elif cls._matches_pattern(q, ['probability', 'chances', 'win chance', 'winning probability', 'likelihood', 'win percent', 'percentage']):
            intent = 'WINNING_PROBABILITY'

        # Match Prediction
        elif cls._matches_pattern(q, ['predict', 'prediction', 'tips', 'forecast', 'winner', 'who will win', 'who wins', 'who is winning']):
            intent = 'MATCH_PREDICTION'

        # Team analysis
        elif cls._matches_pattern(q, ['analyse', 'analysis', 'tactics', 'tactical', 'lineup', 'line-up', 'playstyle', 'form of', 'form guide']):
            intent = 'TEAM_ANALYSIS'

        # Betting advice
        elif cls._matches_pattern(q, ['advice', 'banker', 'safe bet', 'acca', 'accumulator', 'sure bet', 'recommend a bet', 'suggest a bet']):
            intent = 'BETTING_ADVICE'

        # Fixtures Lookup
        elif cls._matches_pattern(q, ['fixture', 'fixtures', 'schedule', 'upcoming', 'next matches', 'calendar', 'when is', 'matches today', 'tomorrow match']):
            intent = 'FIXTURES_LOOKUP'

        # Pronoun resolution check: if query has pronouns and teams are resolved, map to match/odds intents
        if intent == 'GENERAL_FOOTBALL' and teams:
            # If teams were resolved, it's likely asking for prediction/analysis of those teams
            if cls._matches_pattern(q, ['should', 'can they', 'chances', 'chances of', 'win', 'beat', 'defeat']):
                intent = 'MATCH_PREDICTION'
            else:
                intent = 'TEAM_ANALYSIS'

        params = {
            'teams': teams,
            'player': player,
            'league': league,
            'resolved_from_history': resolved_from_history
        }

        logger.info(f"[IntentRouter] Routed '{query}' -> Intent: {intent}, Params: {params}")
        return intent, params

