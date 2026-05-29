from django.core.cache import cache
import logging

logger = logging.getLogger('analytics')

class CacheService:
    """Wrapper around Django Redis cache to standardize keys and operations."""
    
    @staticmethod
    def get_match_list(filter_type, league_id="all"):
        key = f"matches:list:{filter_type}:{league_id}"
        val = cache.get(key)
        if val is not None:
            logger.info(f"Cache HIT for key: {key}")
        else:
            logger.info(f"Cache MISS for key: {key}")
        return val

    @staticmethod
    def set_match_list(filter_type, league_id, html_content, timeout=60):
        key = f"matches:list:{filter_type}:{league_id}"
        cache.set(key, html_content, timeout)

    @staticmethod
    def get_match_detail(match_id):
        key = f"matches:detail:{match_id}"
        return cache.get(key)

    @staticmethod
    def set_match_detail(match_id, data, timeout=300):
        key = f"matches:detail:{match_id}"
        cache.set(key, data, timeout)

    @staticmethod
    def get_prediction(match_id):
        key = f"predictions:detail:{match_id}"
        return cache.get(key)

    @staticmethod
    def set_prediction(match_id, data, timeout=600):
        key = f"predictions:detail:{match_id}"
        cache.set(key, data, timeout)

    @staticmethod
    def get_odds(match_id):
        key = f"odds:detail:{match_id}"
        return cache.get(key)

    @staticmethod
    def set_odds(match_id, data, timeout=120):
        key = f"odds:detail:{match_id}"
        cache.set(key, data, timeout)

    @staticmethod
    def get_voice_history(user_id):
        key = f"assistant:history:{user_id}"
        return cache.get(key) or []

    @staticmethod
    def set_voice_history(user_id, history, timeout=1800):
        key = f"assistant:history:{user_id}"
        cache.set(key, history, timeout)

    @staticmethod
    def invalidate_match(match_id):
        """Invalidates all cache keys related to a specific match."""
        cache.delete(f"matches:detail:{match_id}")
        cache.delete(f"predictions:detail:{match_id}")
        cache.delete(f"odds:detail:{match_id}")
        cache.delete(f"prediction_partial_{match_id}")
        # Invalidate lists since match state changes
        for filter_type in ['live', 'upcoming', 'finished']:
            cache.delete(f"matches:list:{filter_type}:all")
            # Invalidate specific leagues if necessary, clearing all is safer
            cache.delete_pattern("matches:list:*")
            cache.delete_pattern("betting_tips_*")
            
    @staticmethod
    def invalidate_all():
        cache.clear()
