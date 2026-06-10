# __future__ import absolute_import, unicode_literals

import json
import logging
from datetime import datetime

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import PushSubscription
from .push_service import send_push_notification, notify_user

logger = logging.getLogger(__name__)

@shared_task(name='notifications.tasks.send_daily_notifications')
def send_daily_notifications():
    """Send a daily reminder push to all subscribed users.

    The task is scheduled by ``CELERY_BEAT_SCHEDULE`` at 06:00 and 12:00
    (local server time). It iterates over every ``PushSubscription`` and
    sends a simple JSON payload. Real‑world implementations would customise
    the message per user, include a deep‑link URL and honour user
    preferences.
    """
    now = timezone.localtime()
    # Simple message – you can replace this with a richer template.
    payload = json.dumps({
        "title": "NoxaIntel Daily Tip",
        "body": f"Your AI‑powered soccer tip for {now:%A %b %d, %H:%M}" ,
        "url": "/"  # landing page when the user clicks the notification
    })

    subscriptions = PushSubscription.objects.select_related('user').all()
    notified_users = set()
    sent = 0
    failed = 0
    for sub in subscriptions:
        user = sub.user
        if user.id in notified_users:
            continue
        try:
            send_push_notification(
                user=user,
                title="NoxaIntel Daily Tip",
                body=f"Your AI‑powered soccer tip for {now:%A %b %d, %H:%M}",
                url="/"
            )
            notified_users.add(user.id)
            sent += 1
        except Exception as exc:  # pragma: no cover – production will log
            logger.error(
                "Failed to push to %s: %s",
                user.username,
                exc,
            )
            failed += 1

    logger.info(
        "Daily push sent – %d succeeded, %d failed (time=%s)",
        sent,
        failed,
        now.isoformat(),
    )
    return {"sent": sent, "failed": failed, "time": now.isoformat()}


def get_subscribed_users(match=None, category=None):
    """
    Filters and returns users subscribed to a notification category and match details.
    """
    from users.models import Profile
    profiles = Profile.objects.select_related('user')
    
    if category == 'live_matches':
        profiles = profiles.filter(notify_live_matches=True)
    elif category == 'predictions':
        profiles = profiles.filter(notify_ai_predictions=True)
    elif category == 'betting':
        profiles = profiles.filter(notify_betting_tips=True)
    elif category == 'personal_bets':
        profiles = profiles.filter(notify_personal_bets=True)
        
    users = []
    for p in profiles:
        user = p.user
        if match:
            # Check team preference (comma-separated team names)
            if p.notify_teams:
                subscribed_teams = [t.strip().lower() for t in p.notify_teams.split(',') if t.strip()]
                match_home = match.home_team.name.lower()
                match_away = match.away_team.name.lower()
                if not any(t in match_home or t in match_away for t in subscribed_teams):
                    continue
            # Check league preference (comma-separated league codes/names)
            if p.notify_leagues:
                subscribed_leagues = [l.strip().lower() for l in p.notify_leagues.split(',') if l.strip()]
                match_league = match.league.name.lower()
                match_league_code = match.league.code.lower() if hasattr(match.league, 'code') else ""
                if not any(l in match_league or (match_league_code and l in match_league_code) for l in subscribed_leagues):
                    continue
        users.append(user)
    return users


@shared_task(name='notifications.tasks.send_live_match_alert')
def send_live_match_alert(match_id, event_type, event_details=None):
    from matches.models import Match
    from services.prediction_engine import PredictionEngine
    try:
        match = Match.objects.get(id=match_id)
        res = PredictionEngine.predict(match)
        
        title = f"⚽ Live Match Alert: {match.home_team.name} vs {match.away_team.name}"
        score_str = f"{match.home_score} - {match.away_score}" if match.home_score is not None else "0 - 0"
        
        if event_type == 'GOAL':
            scoring_team = (event_details or {}).get('team_name', 'A team')
            body = f"⚽ GOAL! {scoring_team} scored! Score: {match.home_team.name} {score_str} {match.away_team.name} ({match.minute}'). AI updated win probability: {match.home_team.name} {res['home_win_prob']}%, Draw {res['draw_prob']}%, {match.away_team.name} {res['away_win_prob']}%."
        elif event_type == 'RED_CARD':
            player = (event_details or {}).get('player_name', 'A player')
            team = (event_details or {}).get('team_name', 'team')
            body = f"🟥 RED CARD! {player} ({team}) has been sent off! AI updated win probability: {match.home_team.name} {res['home_win_prob']}%, Draw {res['draw_prob']}%, {match.away_team.name} {res['away_win_prob']}%."
        elif event_type == 'START':
            body = f"🏁 Kickoff! {match.home_team.name} vs {match.away_team.name} has started. AI Win probability: {match.home_team.name} {res['home_win_prob']}%, Draw {res['draw_prob']}%, {match.away_team.name} {res['away_win_prob']}%."
        elif event_type == 'HT':
            body = f"Halftime: {match.home_team.name} {score_str} {match.away_team.name}. AI Win probability: {match.home_team.name} {res['home_win_prob']}%, Draw {res['draw_prob']}%, {match.away_team.name} {res['away_win_prob']}%."
        elif event_type == 'FT':
            body = f"Fulltime: {match.home_team.name} {score_str} {match.away_team.name}. Final outcome matches AI prediction."
        else:
            body = f"Event alert: {event_type} during {match.home_team.name} vs {match.away_team.name}. Score: {score_str} ({match.minute}')."

        users = get_subscribed_users(match, category='live_matches')
        for user in users:
            notify_user(user, title, body, notification_type='GOAL' if event_type == 'GOAL' else 'MATCH_START', url=f"/matches/{match.id}/")
            
        logger.info(f"Sent live match alert to {len(users)} users for match {match.id}.")
        return {"notified_count": len(users)}
    except Exception as e:
        logger.error(f"Error in send_live_match_alert: {e}")
        return {"error": str(e)}


@shared_task(name='notifications.tasks.send_prediction_alert')
def send_prediction_alert(match_id):
    from matches.models import Match
    try:
        match = Match.objects.get(id=match_id)
        pred = getattr(match, 'prediction', None)
        if not pred:
            logger.warning(f"No prediction found for match {match_id}")
            return {"status": "no_prediction"}

        title = f"🔮 New Prediction: {match.home_team.name} vs {match.away_team.name}"
        body = f"New AI Prediction: {match.home_team.name} vs {match.away_team.name}. Pick: {pred.recommended_pick} ({pred.confidence_score}% confidence)."

        users = get_subscribed_users(match, category='predictions')
        for user in users:
            notify_user(user, title, body, notification_type='PREDICTION', url=f"/predictions/{match.id}/")

        logger.info(f"Sent prediction alert to {len(users)} users for match {match.id}.")
        return {"notified_count": len(users)}
    except Exception as e:
        logger.error(f"Error in send_prediction_alert: {e}")
        return {"error": str(e)}


@shared_task(name='notifications.tasks.send_betting_alert')
def send_betting_alert(match_id, tip_id):
    from matches.models import Match
    from betting.models import BettingTip
    try:
        match = Match.objects.get(id=match_id)
        tip = BettingTip.objects.get(id=tip_id)
        
        title = f"🟢 High Confidence Tip: {match.home_team.name} vs {match.away_team.name}"
        body = f"New Value Pick ({tip.get_tip_type_display()}): {tip.description} @ {tip.odds} (AI Confidence: {tip.confidence_score}%)."

        users = get_subscribed_users(match, category='betting')
        for user in users:
            notify_user(user, title, body, notification_type='TIP_ALERT', url="/betting/")

        logger.info(f"Sent betting tip alert to {len(users)} users for tip {tip_id}.")
        return {"notified_count": len(users)}
    except Exception as e:
        logger.error(f"Error in send_betting_alert: {e}")
        return {"error": str(e)}


@shared_task(name='notifications.tasks.send_user_bet_alert')
def send_user_bet_alert(user_id, bet_slip_id, event_type):
    from django.contrib.auth import get_user_model
    from betting.models import BetSlip
    User = get_user_model()
    try:
        user = User.objects.get(id=user_id)
        slip = BetSlip.objects.get(id=bet_slip_id)
        
        profile = getattr(user, 'profile', None)
        if profile and not profile.notify_personal_bets:
            logger.info(f"User {user.username} has disabled personal bet notifications.")
            return {"status": "disabled_by_user"}

        if event_type == 'WON':
            title = "🎉 Bet Slip Won!"
            body = f"Congratulations! Your single/accumulator bet slip #{slip.id} has WON! GHS {slip.actual_payout} has been credited to your wallet."
        elif event_type == 'LOST':
            title = "❌ Bet Slip Settled"
            body = f"Your bet slip #{slip.id} has been settled as LOST. Better luck next time!"
        elif event_type == 'CASHOUT':
            title = "💰 Cash Out Successful"
            body = f"Your bet slip #{slip.id} was successfully cashed out for GHS {slip.cash_out_amount}."
        elif event_type == 'CASHOUT_OPPORTUNITY':
            cashout_val = slip.calculate_cash_out_value()
            title = "⚡ Cash Out Opportunity"
            body = f"Cash out your bet slip #{slip.id} now for GHS {cashout_val:.2f} before odds change!"
        else:
            title = "🎟️ Bet Slip Update"
            body = f"Your bet slip #{slip.id} status is now: {slip.get_status_display()}."

        notify_user(user, title, body, notification_type='TIP_ALERT', url="/betting/my-bets/")
        logger.info(f"Sent user bet alert to {user.username} for slip {bet_slip_id}.")
        return {"status": "sent"}
    except Exception as e:
        logger.error(f"Error in send_user_bet_alert: {e}")
        return {"error": str(e)}
