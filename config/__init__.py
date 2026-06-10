from django.template.context import BaseContext


def _patched_basecontext_copy(self):
    duplicate = self.__class__.__new__(self.__class__)
    duplicate.__dict__.update(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate

BaseContext.__copy__ = _patched_basecontext_copy

from .celery import app as celery_app

__all__ = ('celery_app',)
