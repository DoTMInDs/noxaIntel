import random
import logging

logger = logging.getLogger('ai_engine')

class LLMExplanationLayer:
    """Simulates a premium, context-aware LLM reasoning and commentary generation layer."""

    @staticmethod
    def explain(query: str, intent: str, context: dict, user, history=None) -> str:
        """Generates analytical Markdown commentary based on the user query, intent, and retrieved context."""
        history = history or []
        
        # Try Groq-powered analytical commentary
        try:
            from services.groq_client import GroqClient
            client = GroqClient()
            if client.is_configured():
                import json
                history_str = ""
                for h_msg in history[-5:]:
                    role = "User" if h_msg.get('sender') == 'user' else "AI"
                    history_str += f"{role}: {h_msg.get('text', '')}\n"

                system_prompt = (
                    "You are the NoxaIntel AI Soccer Betting Assistant, a premium professional sports analyst.\n"
                    "Your task is to generate a professional, context-aware markdown analysis responding to the user's query.\n\n"
                    "CRITICAL RULES:\n"
                    "1. SOURCING PREDICTIONS: You must NEVER fabricate or hallucinate win/draw/away probabilities, predicted scores, over/under, or BTTS likelihoods. You must strictly source them from the provided RAG Context. If the context does not contain this data, explicitly state that predictions are currently unavailable for this fixture.\n"
                    "2. NO FABRICATION: Do not invent odds, wallet balances, active bets, or injuries. Only refer to what is provided in the RAG Context.\n"
                    "3. FORMATTING: Use clean, professional, and visually engaging markdown formatting (headers, lists, tables). Use DaisyUI-friendly styling rules where applicable. Keep descriptions concise and analytical.\n"
                    "4. TONALITY: Address the user in a helpful, expert tone.\n\n"
                    f"--- CURRENT QUERY ---\n{query}\n\n"
                    f"--- SEMANTIC INTENT ---\n{intent}\n\n"
                    f"--- RAG CONTEXT (JSON) ---\n{json.dumps(context, indent=2)}\n\n"
                    f"--- CHAT HISTORY ---\n{history_str}"
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query}
                ]
                
                res = client.generate_chat_completion(messages, temperature=0.3)
                if res:
                    return res
        except Exception as e:
            logger.warning(f"Groq explanation failed: {e}. Falling back to rule-based explainer.")
            
        # Base greetings / context alerts
        history_alert = ""
        if context.get("resolved_from_history"):
            teams_str = ", ".join(context.get("teams_searched", []))
            history_alert = f"*(Resolved context for **{teams_str.title()}** from our previous discussion)*\n\n"

        if intent == 'MATCH_PREDICTION':
            return LLMExplanationLayer._explain_match_prediction(context, history_alert)
            
        elif intent == 'WINNING_PROBABILITY':
            return LLMExplanationLayer._explain_winning_probability(context, history_alert)
            
        elif intent == 'SCORE_PREDICTION':
            return LLMExplanationLayer._explain_score_prediction(context, history_alert)
            
        elif intent == 'TEAM_ANALYSIS':
            return LLMExplanationLayer._explain_team_analysis(context, history_alert)
            
        elif intent == 'PLAYER_ANALYSIS':
            return LLMExplanationLayer._explain_player_analysis(context)
            
        elif intent == 'LIVE_MATCH_LOOKUP':
            return LLMExplanationLayer._explain_live_matches(context)
            
        elif intent == 'FIXTURES_LOOKUP':
            return LLMExplanationLayer._explain_fixtures(context)
            
        elif intent == 'STANDINGS_LOOKUP':
            return LLMExplanationLayer._explain_standings(context)
            
        elif intent == 'INJURY_LOOKUP':
            return LLMExplanationLayer._explain_injuries(context, history_alert)
            
        elif intent == 'ODDS_ANALYSIS':
            return LLMExplanationLayer._explain_odds(context, history_alert)
            
        elif intent == 'BETTING_ADVICE':
            return LLMExplanationLayer._explain_betting_advice(context)
            
        elif intent == 'OVER_UNDER_ANALYSIS':
            return LLMExplanationLayer._explain_over_under(context, history_alert)
            
        elif intent == 'BTTS_ANALYSIS':
            return LLMExplanationLayer._explain_btts(context, history_alert)
            
        elif intent == 'H2H_ANALYSIS':
            return LLMExplanationLayer._explain_h2h(context, history_alert)
            
        elif intent == 'USER_BET_ANALYSIS':
            return LLMExplanationLayer._explain_user_bets(context, user)
            
        else: # GENERAL_FOOTBALL
            return LLMExplanationLayer._explain_general(query)

    # --- Individual Explanations ---

    @staticmethod
    def _explain_match_prediction(context: dict, alert: str) -> str:
        match = context.get("match")
        if not match:
            return "⚽ I couldn't find any upcoming or active fixtures matching those teams. Try browsing the Predictions page."

        pred = context.get("prediction")
        odds = context.get("odds")
        analysis = context.get("ai_analysis")
        
        resp = f"{alert}### 🔮 AI Match Analysis: {match['home_team']} vs {match['away_team']}\n"
        resp += f"**League**: {match['league']} | **Kickoff**: {match['date']} | **Status**: {match['status']}\n\n"
        
        if pred:
            resp += "#### 📊 Win Probabilities:\n"
            resp += f"- **{match['home_team']} Win**: `{pred['home_win_prob']}%`  \n"
            resp += f"- **Draw**: `{pred['draw_prob']}%`  \n"
            resp += f"- **{match['away_team']} Win**: `{pred['away_win_prob']}%`  \n\n"
            
            resp += f"🤖 **AI Recommended Pick**: `{pred['recommended_pick']}` (Confidence: `{pred['confidence_score']}%`)\n\n"
            
        if odds:
            resp += "#### 💰 Live Market Odds:\n"
            resp += f"- **{match['home_team']} Win**: `@{odds['home_odds']}` | **Draw**: `@{odds['draw_odds']}` | **{match['away_team']} Win**: `@{odds['away_odds']}`  \n"
            resp += f"- **Over 2.5 Goals**: `@{odds['over_2_5_odds']}` | **Both Teams to Score (BTTS)**: `@{odds['btts_yes_odds']}`\n\n"
            
        if analysis:
            resp += "#### 📝 Tactical Breakdown:\n"
            resp += f"- **Tactical Setup**: {analysis['tactical_breakdown']}\n"
            resp += f"- **Key Duels**: {analysis['key_player_matchups']}\n"
            resp += f"- **Final Verdict**: {analysis['final_verdict']}\n\n"

        resp += LLMExplanationLayer._get_injuries_bullet(context)
        return resp

    @staticmethod
    def _explain_winning_probability(context: dict, alert: str) -> str:
        match = context.get("match")
        pred = context.get("prediction")
        if not match or not pred:
            return "📊 I don't have probability ratings for this matchup in my data files right now. Check back shortly."

        resp = f"{alert}### 📈 Win Probability: {match['home_team']} vs {match['away_team']}\n\n"
        resp += f"Our ML model indicates the following likelihood distribution:\n\n"
        
        # Text based gauges
        resp += f"🟢 **{match['home_team']} Win probability**: `{pred['home_win_prob']}%`  \n"
        resp += f"🟡 **Draw probability**: `{pred['draw_prob']}%`  \n"
        resp += f"🔴 **{match['away_team']} Win probability**: `{pred['away_win_prob']}%`  \n\n"
        
        better_team = match['home_team'] if pred['home_win_prob'] > pred['away_win_prob'] else match['away_team']
        higher_prob = max(pred['home_win_prob'], pred['away_win_prob'])
        
        resp += f"**Analytical Insight**: {better_team} enters this clash as the model's favorite with a `{higher_prob}%` probability rating. "
        
        if context.get("h2h_history") and context["h2h_history"]["matches_count"] > 0:
            h2h = context["h2h_history"]
            resp += f"Historically, out of {h2h['matches_count']} meetings, {match['home_team']} won {h2h['home_wins']} and {match['away_team']} won {h2h['away_wins']}. "
            
        return resp

    @staticmethod
    def _explain_score_prediction(context: dict, alert: str) -> str:
        match = context.get("match")
        pred = context.get("prediction")
        if not match or not pred:
            return "⚽ I don't have sufficient score precomputations for this matchup. Check the Predictions board."

        home_prob = float(pred['home_win_prob'])
        away_prob = float(pred['away_win_prob'])
        over_prob = float(pred['over_2_5_prob'])

        # Deterministic but simulated scoreline based on probability
        if abs(home_prob - away_prob) < 10:
            score = "1-1" if over_prob < 60 else "2-2"
        elif home_prob > away_prob:
            score = "2-0" if over_prob < 55 else ("2-1" if over_prob < 72 else "3-1")
        else:
            score = "0-1" if over_prob < 55 else ("1-2" if over_prob < 72 else "1-3")

        resp = f"{alert}### 🎯 Correct Score Prediction: {match['home_team']} vs {match['away_team']}\n\n"
        resp += f"Our AI model predicts the most probable correct score is **{score}**.\n\n"
        resp += "#### 📈 Goals Distribution Model:\n"
        resp += f"- **Over 2.5 Goals probability**: `{pred['over_2_5_prob']}%`  \n"
        resp += f"- **Under 2.5 Goals probability**: `{pred['under_2_5_prob']}%`  \n"
        resp += f"- **Both Teams To Score probability**: `{pred['btts_yes_prob']}%`  \n\n"
        
        resp += f"**Reasoning**: With a BTTS probability of `{pred['btts_yes_prob']}%` and a `{pred['confidence_score']}%` model confidence rating, a close-run match is expected. "
        resp += f"The attacking metrics suggest backing goals is highly viable."
        return resp

    @staticmethod
    def _explain_team_analysis(context: dict, alert: str) -> str:
        match = context.get("match")
        analysis = context.get("ai_analysis")
        if not match or not analysis:
            return "📋 No tactical breakdowns are loaded for this squad at the moment."

        resp = f"{alert}### 🛡️ Tactical Team Analysis: {match['home_team']} vs {match['away_team']}\n\n"
        resp += f"**{match['home_team']} Tactics & Form**:\n"
        resp += f"{analysis['tactical_breakdown']}\n\n"
        resp += f"**Key Matchup Zone**:\n"
        resp += f"{analysis['key_player_matchups']}\n\n"
        
        resp += LLMExplanationLayer._get_injuries_bullet(context)
        return resp

    @staticmethod
    def _explain_player_analysis(context: dict) -> str:
        player = context.get("player_stats")
        if player:
            resp = f"### 🏃 Player Profile: {player['name']} ({player['position']})\n"
            resp += f"**Current Team**: {player['team']}  \n"
            resp += f"**Season Stats**:  \n"
            resp += f"- **Apps**: {player['matches']} | **Goals**: {player['goals']} | **Assists**: {player['assists']}  \n"
            resp += f"- **Avg Match Rating**: `{player['rating']}/10`  \n"
            resp += f"- **Shots per Game**: {player['shots_per_game']} | **Pass Accuracy**: {player['pass_accuracy']}  \n\n"
            resp += f"**Commentary**: {player['name']} is performing at a top-tier rating of `{player['rating']}` this season. "
            resp += f"His offensive contribution of {player['goals']} goals is key to {player['team']}'s tactical setup."
            return resp
        
        team_players = context.get("team_players")
        if team_players:
            resp = f"### 👥 Key Players: {context['teams_searched'][0].title()}\n\n"
            resp += "The leading performers in the squad database:\n\n"
            for pl in team_players[:3]:
                resp += f"- **{pl['name']}** ({pl['position']}): {pl['goals']} G, {pl['assists']} A, rating `{pl['rating']}`\n"
            return resp

        # Show general top scorers
        top = PlayerService.get_top_scorers()
        resp = "### 🏆 Leading Scorer Leaderboard:\n\n"
        resp += "| Rank | Player | Team | Goals | Rating |\n"
        resp += "|---|---|---|---|---|\n"
        for idx, pl in enumerate(top, 1):
            resp += f"| {idx} | {pl['name']} | {pl['team']} | {pl['goals']} | `{pl['rating']}` |\n"
        return resp

    @staticmethod
    def _explain_live_matches(context: dict) -> str:
        live = context.get("live_matches")
        if not live:
            return "⚽ No matches are live right now. Head to the Matches page to see the upcoming schedule."

        resp = "### 🔴 Current Live Matches\n\n"
        for m in live:
            resp += f"- **{m['home_team']} {m['score']} {m['away_team']}** ({m['minute']}) - *{m['league']}*  \n"
        
        resp += f"\n*Tip: Tap the live match listings in the main interface to see live odds updates!*"
        return resp

    @staticmethod
    def _explain_fixtures(context: dict) -> str:
        league_name = context.get("league_name")
        
        if league_name and context.get("league_fixtures"):
            resp = f"### 📅 Upcoming Fixtures: {league_name}\n\n"
            for f in context["league_fixtures"]:
                resp += f"- **{f['home']} vs {f['away']}** — `{f['date']}` ({f['status']})  \n"
            return resp
            
        fixtures = context.get("upcoming_fixtures")
        if not fixtures:
            return "📅 No scheduled matches found in the upcoming calendar."

        resp = "### 📅 Upcoming Scheduled Matches\n\n"
        for f in fixtures[:6]:
            resp += f"- **{f['home_team']} vs {f['away_team']}** — `{f['date']}` (*{f['league']}*)  \n"
        
        resp += f"\n*Tip: Predictions and AI Analysis are precomputed for all these matches. Tap them in the Home screen!*"
        return resp

    @staticmethod
    def _explain_standings(context: dict) -> str:
        standings = context.get("league_standings")
        if not standings:
            return "📋 Standing data is currently unavailable."

        league_title = context.get("league_name", "Premier League")
        resp = f"### 🏆 League Table: {league_title}\n\n"
        resp += "| Pos | Team | P | W | D | L | GD | Pts |\n"
        resp += "|---|---|---|---|---|---|---|---|\n"
        for entry in standings[:10]:
            marker = "🔥 " if entry['rank'] <= 4 else ("" if entry['rank'] < 8 else "⚠️ ")
            resp += f"| {entry['rank']} | {marker}{entry['team_name']} | {entry['played']} | {entry['wins']} | {entry['draws']} | {entry['losses']} | {entry['goal_difference']} | **{entry['points']}** |\n"
        
        resp += "\n*🔥 = Champions League spots | ⚠️ = Relegation risk*"
        return resp

    @staticmethod
    def _explain_injuries(context: dict, alert: str) -> str:
        teams = context.get("teams_searched", [])
        if not teams:
            return "🏥 Please specify a team to see their injury report."

        resp = f"{alert}### 🏥 Medical Room & Injury Report\n\n"
        
        h_inj = context.get("home_injuries", [])
        a_inj = context.get("away_injuries", [])

        if not h_inj and not a_inj:
            return f"{alert}🏥 No significant injuries reported for the queried teams."

        if h_inj:
            resp += f"**{teams[0].title()} Injuries**:\n"
            for inj in h_inj:
                resp += f"- **{inj['player']}** ({inj['injury']}): `{inj['duration']}` | Fitness: `{inj['fitness']}` (*{inj['status']}*)\n"
            resp += "\n"

        if len(teams) > 1 and a_inj:
            resp += f"**{teams[1].title()} Injuries**:\n"
            for inj in a_inj:
                resp += f"- **{inj['player']}** ({inj['injury']}): `{inj['duration']}` | Fitness: `{inj['fitness']}` (*{inj['status']}*)\n"
                
        return resp

    @staticmethod
    def _explain_odds(context: dict, alert: str) -> str:
        match = context.get("match")
        odds = context.get("odds")
        if not match or not odds:
            return "💰 Odds are currently suspended or unavailable for this fixture."

        resp = f"{alert}### 💰 Market Odds Analysis: {match['home_team']} vs {match['away_team']}\n\n"
        resp += "Our bookmaker feeds show the following active odds:\n\n"
        
        resp += "| Market Selection | Decimal Odds |\n"
        resp += "|---|---|\n"
        resp += f"| **{match['home_team']} Win** | `@{odds['home_odds']}` |\n"
        resp += f"| **Draw** | `@{odds['draw_odds']}` |\n"
        resp += f"| **{match['away_team']} Win** | `@{odds['away_odds']}` |\n"
        resp += f"| **Over 2.5 Goals** | `@{odds['over_2_5_odds']}` |\n"
        resp += f"| **Under 2.5 Goals** | `@{odds['under_2_5_odds']}` |\n"
        resp += f"| **Both Teams to Score (Yes)** | `@{odds['btts_yes_odds']}` |\n"
        resp += f"| **Both Teams to Score (No)** | `@{odds['btts_no_odds']}` |\n\n"
        
        # Smart odds analysis
        fav = match['home_team'] if odds['home_odds'] < odds['away_odds'] else match['away_team']
        resp += f"**Odds Outlook**: Bookmakers list **{fav}** as the betting favorite. "
        if abs(float(odds['home_odds']) - float(odds['away_odds'])) < 0.6:
            resp += "The close pricing reflects a tight, high-stakes matchup. Backing Double Chance might be a smart choice."
            
        return resp

    @staticmethod
    def _explain_betting_advice(context: dict) -> str:
        resp = "### 🎯 AI Betting Recommendations\n\n"
        
        safe = context.get("safe_tips", [])
        value = context.get("value_tips", [])
        acca = context.get("acca_tips", [])

        if not safe and not value and not acca:
            return "🟢 No betting recommendations are ready right now. Check the Tips board!"

        if safe:
            resp += "#### 🟢 Safe Picks (High Confidence):\n"
            for t in safe:
                lock = "🔒 [VIP only]" if t["is_vip"] else t["description"]
                resp += f"- **{t['match']}**: {lock} | Odds: `@{t['odds']}` (Conf: `{t['confidence']}%`)\n"
            resp += "\n"
            
        if value:
            resp += "#### 🟡 Value Picks (High Yield):\n"
            for t in value:
                lock = "🔒 [VIP only]" if t["is_vip"] else t["description"]
                resp += f"- **{t['match']}**: {lock} | Odds: `@{t['odds']}` (Conf: `{t['confidence']}%`)\n"
            resp += "\n"

        if acca:
            resp += "#### 👑 VIP Accumulator Legs:\n"
            for t in acca:
                resp += f"- **{t['match']}**: {t['description']} | Odds: `@{t['odds']}` (Conf: `{t['confidence']}%`)\n"

        return resp

    @staticmethod
    def _explain_over_under(context: dict, alert: str) -> str:
        match = context.get("match")
        pred = context.get("prediction")
        odds = context.get("odds")
        
        if not match or not pred:
            return "⚽ Goals line predictions are not available for this game."

        resp = f"{alert}### ⚽ Over/Under Goals Analysis: {match['home_team']} vs {match['away_team']}\n\n"
        resp += f"- **Over 2.5 Goals Probability**: `{pred['over_2_5_prob']}%`  \n"
        resp += f"- **Under 2.5 Goals Probability**: `{pred['under_2_5_prob']}%`  \n"
        
        if odds:
            resp += f"- **Over 2.5 Goals Odds**: `@{odds['over_2_5_odds']}`  \n"
            resp += f"- **Under 2.5 Goals Odds**: `@{odds['under_2_5_odds']}`  \n"
            
        resp += "\n**Model Verdict**: "
        if float(pred['over_2_5_prob']) > 60:
            resp += f"High attacking output expected. We project an open match with over 2.5 goals."
        else:
            resp += f"Both teams show heavy defensive ratings. Backing under 2.5 goals is suggested."
            
        return resp

    @staticmethod
    def _explain_btts(context: dict, alert: str) -> str:
        match = context.get("match")
        pred = context.get("prediction")
        odds = context.get("odds")
        
        if not match or not pred:
            return "⚽ Both Teams to Score data is unavailable for this match."

        resp = f"{alert}### 🥅 Both Teams to Score (BTTS) Analysis: {match['home_team']} vs {match['away_team']}\n\n"
        resp += f"- **Both Teams To Score (Yes) Probability**: `{pred['btts_yes_prob']}%`  \n"
        resp += f"- **Both Teams To Score (No) Probability**: `{pred['btts_no_prob']}%`  \n"
        
        if odds:
            resp += f"- **BTTS (Yes) Odds**: `@{odds['btts_yes_odds']}`  \n"
            resp += f"- **BTTS (No) Odds**: `@{odds['btts_no_odds']}`  \n"
            
        resp += "\n**Model Verdict**: "
        if float(pred['btts_yes_prob']) > 55:
            resp += "Both teams show high conversion rates in open play. BTTS (Yes) is highly probable."
        else:
            resp += "Strong defensive systems suggest at least one clean sheet is likely. BTTS (No) is recommended."
            
        return resp

    @staticmethod
    def _explain_h2h(context: dict, alert: str) -> str:
        match = context.get("match")
        h2h = context.get("h2h_history")
        
        if not match or not h2h or h2h["matches_count"] == 0:
            return f"{alert}📊 No historical head-to-head records found in the database for {match['home_team']} vs {match['away_team']}."

        resp = f"{alert}### ⚔️ Head-to-Head Records: {match['home_team']} vs {match['away_team']}\n\n"
        resp += f"Database records contain **{h2h['matches_count']}** historical clashes:\n\n"
        resp += f"- **{match['home_team']} Wins**: {h2h['home_wins']}  \n"
        resp += f"- **{match['away_team']} Wins**: {h2h['away_wins']}  \n"
        resp += f"- **Draws**: {h2h['draws']}  \n\n"
        
        # Analysis
        if h2h['home_wins'] > h2h['away_wins']:
            resp += f"**Historical Trend**: {match['home_team']} has traditionally dominated this fixture."
        elif h2h['home_wins'] < h2h['away_wins']:
            resp += f"**Historical Trend**: {match['away_team']} has held the upper hand in recent clashes."
        else:
            resp += "**Historical Trend**: Historically, meetings between these sides have been highly balanced."
            
        return resp

    @staticmethod
    def _explain_user_bets(context: dict, user) -> str:
        summary = context.get("user_wallet")
        active = context.get("user_active_bets", [])
        settled = context.get("user_settled_stats")

        if not summary:
            return "💰 I can't read your wallet files at the moment."

        resp = f"### 💰 Wallet & Betting Portfolio: {user.username}\n\n"
        resp += f"- **Balance**: `GHS {summary['balance']:,.2f}`  \n"
        resp += f"- **Active Bets count**: `{summary['active_bets_count']}` (Staked: `GHS {summary['total_active_staked']:,.2f}`)\n\n"

        if settled and settled['total_bets'] > 0:
            resp += "#### 📊 Betting Performance (Settled Slips):\n"
            resp += f"- **Total Settled Slips**: {settled['total_bets']} (Wins: {settled['won_bets']} | Losses: {settled['lost_bets']})  \n"
            resp += f"- **Win Rate**: `{settled['win_rate']}%` | **Net Yield (ROI)**: `{settled['roi']}%`  \n"
            resp += f"- **Total Staked**: `GHS {settled['total_staked']:,.2f}` | **Total Payout**: `GHS {settled['total_payout']:,.2f}`  \n\n"

        if active:
            resp += "#### 🎟️ Active Bet Slips:\n"
            for slip in active:
                resp += f"**Slip #{slip['id']}** ({slip['type']})  \n"
                resp += f"- Stake: `GHS {slip['stake']:,.2f}` | Potential Payout: `GHS {slip['potential_payout']:,.2f}` | Odds: `@{slip['odds']}`  \n"
                for leg in slip['legs']:
                    resp += f"  - Leg: *{leg['match']}* — Pick: **{leg['market']}** (`@{leg['odds']}`) [{leg['result']}]\n"
                resp += "\n"
        else:
            resp += "🎟️ You have no active pending bets. Head to the Predictions tab to select fixtures and place a bet!"
            
        return resp

    @staticmethod
    def _explain_general(query: str) -> str:
        return (
            "🤖 **NoxaIntel Soccer Intelligence Assistant**\n\n"
            "Ask me anything about matches, predictions, and betting analytics! Try these prompts:\n"
            "- 'Can Arsenal beat Liverpool?'\n"
            "- 'Show live EPL scores'\n"
            "- 'Show the league table for Premier League'\n"
            "- 'What are the safest bets tonight?'\n"
            "- 'Show my active bets'"
        )

    # --- Helpers ---
    @staticmethod
    def _get_injuries_bullet(context: dict) -> str:
        teams = context.get("teams_searched", [])
        if not teams:
            return ""
        
        h_inj = context.get("home_injuries", [])
        a_inj = context.get("away_injuries", [])
        
        if not h_inj and not a_inj:
            return ""
            
        resp = "#### 🏥 Medical / Injury Updates:\n"
        if h_inj:
            resp += f"- **{teams[0].title()}**: " + ", ".join([f"{inj['player']} ({inj['injury']}, {inj['duration']})" for inj in h_inj]) + "  \n"
        if len(teams) > 1 and a_inj:
            resp += f"- **{teams[1].title()}**: " + ", ".join([f"{inj['player']} ({inj['injury']}, {inj['duration']})" for inj in a_inj]) + "  \n"
        return resp + "\n"
