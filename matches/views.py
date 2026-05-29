from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_page
from django.utils import timezone
from .models import Match, League


def match_dashboard(request):
    """Renders the main match dashboard structure."""
    leagues = League.objects.all()
    return render(request, 'matches/dashboard.html', {'leagues': leagues})


def match_list_partial(request):
    """HTMX endpoint returning filtered match cards."""
    filter_type = request.GET.get('filter', 'upcoming')
    league_id = request.GET.get('league')

    matches = Match.objects.select_related('home_team', 'away_team', 'league').prefetch_related('odds_snapshots')

    if league_id:
        matches = matches.filter(league_id=league_id)

    if filter_type == 'live':
        matches = matches.filter(status='LIVE')
    elif filter_type == 'finished':
        matches = matches.filter(status='FINISHED').order_by('-match_date')[:20]
    else:  # upcoming
        matches = matches.filter(status='SCHEDULED').order_by('match_date')[:30]

    return render(request, 'matches/partials/match_list.html', {'matches': matches, 'filter_type': filter_type})


def match_detail(request, match_id):
    """Renders match detail view with latest odds and stats."""
    match = get_object_or_404(
        Match.objects.select_related('home_team', 'away_team', 'league'),
        id=match_id
    )
    latest_odds = match.odds_snapshots.first()
    return render(request, 'matches/detail.html', {'match': match, 'latest_odds': latest_odds})
