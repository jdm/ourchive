from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import caches, cache
from django.utils.cache import get_cache_key
from django.urls import reverse
from django.http import HttpRequest
from django.db import connections
from django.core.cache.backends.db import DatabaseCache
from api import models as api

def make_key(key, key_prefix, version):
    return f"ourchive:{version}:{key}"

def spoil_work_cache(instance):
    connection = connections['default']
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM ourchive_database_cache where cache_key like 'ourchive:%:work_{instance.id}_%'")

def spoil_subscription_cache(instance):
    connection = connections['default']
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM ourchive_database_cache where cache_key like %s", [f'ourchive:%:subscription_{instance.user.username}_%'])

def spoil_bookmark_cache(instance):
    connection = connections['default']
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM ourchive_database_cache where cache_key like 'ourchive:%:bookmark_{instance.id}_%'")
        cursor.execute(f"DELETE FROM ourchive_database_cache where cache_key like 'ourchive:%:collection_{instance.id}_%'")

def spoil_collection_cache(instance):
    connection = connections['default']
    with connection.cursor() as cursor:
        cursor.execute(f"DELETE FROM ourchive_database_cache where cache_key like 'ourchive:%:collection_{instance.id}_%'")

@receiver(post_save, sender=api.Work)
def spoil_cache_create(sender, instance, created, **kwargs):
    if created:
        print('created')

@receiver(post_save, sender=api.Work)
def spoil_work_cache_update(sender, instance, **kwargs):
    spoil_work_cache(instance)

@receiver(post_delete, sender=api.Work)
def spoil_work_cache_delete(sender, instance, **kwargs):
    spoil_work_cache(instance)

@receiver(post_save, sender=api.Chapter)
def spoil_chapter_cache_update(sender, instance, **kwargs):
    spoil_work_cache(instance.work)

@receiver(post_delete, sender=api.Chapter)
def spoil_chapter_cache_delete(sender, instance, **kwargs):
    spoil_work_cache(instance.work)

@receiver(post_save, sender=api.UserSubscription)
def spoil_subscription_cache_update(sender, instance, **kwargs):
    spoil_subscription_cache(instance)

@receiver(post_delete, sender=api.UserSubscription)
def spoil_subscription_cache_delete(sender, instance, **kwargs):
    spoil_subscription_cache(instance)

@receiver(post_save, sender=api.Bookmark)
def spoil_bookmark_cache_update(sender, instance, **kwargs):
    spoil_bookmark_cache(instance)

@receiver(post_delete, sender=api.Bookmark)
def spoil_bookmark_cache_delete(sender, instance, **kwargs):
    spoil_bookmark_cache(instance)

@receiver(post_save, sender=api.BookmarkCollection)
def spoil_collection_cache_update(sender, instance, **kwargs):
    spoil_collection_cache(instance)

@receiver(post_delete, sender=api.BookmarkCollection)
def spoil_collection_cache_delete(sender, instance, **kwargs):
    spoil_collection_cache(instance)