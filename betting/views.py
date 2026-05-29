from django.shortcuts import render
from django.core.cache import cache
from .models import BettingTip
from analytics.utils import track_cache


def tips_dashboard(request):
    """Renders the betting recommendations dashboard."""
    return render(request, 'betting/dashboard.html')


def tips_filter_partial(request):
    """HTMX endpoint returning filtered betting tips with Redis caching."""
    tip_type = request.GET.get('type', 'all')
    is_vip = getattr(request.user, 'profile', None) and request.user.profile.subscription_tier.access_vip_tips

    cache_key = f"betting_tips_{tip_type}_vip_{is_vip}"
    cached_html = cache.get(cache_key)

    if cached_html:
        track_cache('tips_filter_partial', is_hit=True)
        return cached_html

    track_cache('tips_filter_partial', is_hit=False)

    tips = BettingTip.objects.select_related('match__home_team', 'match__away_team', 'match__league')

    if tip_type != 'all':
        tips = tips.filter(tip_type=tip_type.upper())

    # Keep VIP tips in the list so that we can render locked cards in the frontend, encouraging upgrades
    tips = tips[:30]

    response = render(request, 'betting/partials/tip_list.html', {'tips': tips, 'tip_type': tip_type})
    cache.set(cache_key, response, 60 * 5)
    return response


