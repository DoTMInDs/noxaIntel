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


@cache_control(max_age=86400, public=True)
def service_worker(request):
    """Renders the serviceworker.js template with application/javascript content type."""
    response = render(
        request,
        'pwa/serviceworker.js',
        content_type='application/javascript'
    )
    response['Service-Worker-Allowed'] = '/'
    return response



def offline(request):
    """Renders the offline fallback HTML page."""
    return render(request, 'pwa/offline.html')
