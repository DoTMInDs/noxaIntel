import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from matches.models import Match
from .tasks import settle_match_bets

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Match)
def match_settlement_trigger(sender, instance, **kwargs):
    """
    Listens for Match post_save events.
    If match status is set to FINISHED, triggers Celery bet settlement asynchronously.
    """
    if instance.status == 'FINISHED':
        logger.info(f"Match #{instance.id} saved as FINISHED. Triggering asynchronous bet settlement...")
        try:
            settle_match_bets.delay(instance.id)
        except Exception as e:
            logger.error(f"Failed to queue Celery settlement task for Match #{instance.id}: {e}")
            # Fallback to synchronous run if celery broker is offline in local dev
            logger.info("Executing settlement synchronously as fallback...")
            try:
                settle_match_bets(instance.id)
            except Exception as se:
                logger.error(f"Failed to execute settlement synchronously: {se}")
