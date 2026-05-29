from django.shortcuts import render, get_object_or_404
from django.core.cache import cache
from matches.models import Match
from .models import Prediction, AIAnalysis
from ai_engine.tasks import refresh_match_prediction
from analytics.utils import track_cache


def prediction_detail(request, match_id):
    """Renders the full prediction detail page."""
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team', 'league'),
        id=match_id
    )
    prediction = getattr(match, 'prediction', None)
    ai_analysis = getattr(match, 'ai_analysis', None)

    return render(request, 'predictions/detail.html', {
        'match': match,
        'prediction': prediction,
        'ai_analysis': ai_analysis,
    })


def prediction_partial(request, match_id):
    """
    HTMX endpoint implementing low-latency Redis cache check + stale-while-revalidate.
    User Request -> Redis Cache Check ->
      If cache hit -> return HTML fragment instantly
      If cache miss -> serve stale data + trigger async refresh via Celery
    """
    cache_key = f"prediction_partial_{match_id}"
    cached_html = cache.get(cache_key)

    if cached_html:
        track_cache('prediction_partial', is_hit=True)
        return cached_html

    track_cache('prediction_partial', is_hit=False)

    # Cache miss: fetch stale/current data from DB
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team', 'league'),
        id=match_id
    )
    prediction = getattr(match, 'prediction', None)
    ai_analysis = getattr(match, 'ai_analysis', None)

    # Trigger async Celery task to precompute/refresh in background
    refresh_match_prediction.delay(match_id)

    response = render(request, 'predictions/partials/prediction_card.html', {
        'match': match,
        'prediction': prediction,
        'ai_analysis': ai_analysis,
    })

    # Cache the rendered fragment for 5 minutes
    cache.set(cache_key, response, 60 * 5)
    return response

