from django.shortcuts import render
from django.views.decorators.cache import cache_control


@cache_control(max_age=86400, public=True)
def manifest(request):
    """Renders the manifest.json template with application/json content type."""
    return render(
        request,
        'pwa/manifest.json',
        content_type='application/json'
    )


@cache_control(no_cache=True, must_revalidate=True)
def service_worker(request):
    """Renders the serviceworker.js template with application/javascript content type.
    
    IMPORTANT: Service workers must never be cached long-term.
    The browser uses its own update algorithm (checks every 24h or on navigation).
    Setting no-cache here ensures the browser can always check for updates.
    """
    response = render(
        request,
        'pwa/serviceworker.js',
        content_type='application/javascript'
    )
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response



def offline(request):
    """Renders the offline fallback HTML page."""
    return render(request, 'pwa/offline.html')
