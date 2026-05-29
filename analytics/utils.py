from django.core.cache import cache

def track_cache(endpoint_name, is_hit):
    """
    Increments hits/misses in Redis to avoid hitting the database on every HTTP request.
    These are aggregated and saved to the database periodically by a background task.
    """
    key = f"metrics:{endpoint_name}:hits" if is_hit else f"metrics:{endpoint_name}:misses"
    try:
        # Attempt to increment the key in Redis
        cache.incr(key)
    except ValueError:
        # If the key doesn't exist in the cache, initialize it
        cache.set(key, 1, timeout=None)
