from __future__ import unicode_literals
from __future__ import absolute_import
from contextlib import contextmanager
from datetime import timedelta
import logging

from django.utils.lru_cache import lru_cache
from django.utils.timezone import now
from django.utils import six
from django.dispatch import receiver
from django.db.models import signals
from django.core.cache import caches
from django.conf import settings
from django.apps import apps

from .indexes import index_registry
from .utils import merge

SUSPENSION_BUFFER_TIME = timedelta(seconds=10)
USE_CACHE = getattr(settings, 'ELASTIC_MODELS_USE_CACHE', False)

logger = logging.getLogger(__name__)

if not USE_CACHE:
    suspended_models = []


@lru_cache()
def get_search_models():
    return set(m for (m, a) in index_registry.keys()
               if m in apps.get_models())

def get_indexes_for_model(model):
    return [i for (m, n), i in index_registry.items()
            if issubclass(model, m)]

def _is_suspended(model):
    if USE_CACHE:
        suspended_models = cache.get('suspended_models', [])
    else:
        global suspended_models

    for models in suspended_models:
        if model in models:
            return True
    return False

def get_dependents(instance):
    dependents = {}

    for index in index_registry.values():
        if index.model not in apps.get_models():
            continue
        dependencies = index.get_dependencies()
        if type(instance) in dependencies:
            filter_kwargs = {dependencies[type(instance)]: instance}
            qs = index.model.objects.filter(**filter_kwargs)
            dependents[index] = list(qs.values_list("pk", flat=True))

    return dependents

@receiver(signals.pre_save)
@receiver(signals.pre_delete)
def collect_dependents(sender, **kwargs):
    instance = kwargs['instance']
    instance._search_dependents = get_dependents(instance)

@receiver(signals.post_delete)
@receiver(signals.post_save)
def update_search_index(sender, **kwargs):
    instance = kwargs['instance']
    search_models = get_search_models()

    if not isinstance(instance, sender):
        logger.warning("Resetting 'sender' to '{}'".format(type(instance)))
        sender = type(instance)
    if sender not in search_models or _is_suspended(sender):
        logger.debug("Skipping indexing for '%s'" % (sender))
        return

    indexes = get_indexes_for_model(sender)
    for index in indexes:
        index.index_instance(instance)

    dependents = merge([instance._search_dependents, get_dependents(instance)])
    for index, pks in six.iteritems(dependents):
        for record in index.model.objects.filter(pk__in=pks).iterator():
            index.index_instance(record)

@receiver(signals.m2m_changed)
def handle_m2m(sender, **kwargs):
    if kwargs['action'].startswith("pre_"):
        collect_dependents(kwargs['model'], **kwargs)
    else:
        update_search_index(kwargs['model'], **kwargs)

@contextmanager
def suspended_updates(models=None, permanent=False):
    if USE_CACHE:
        suspended_models = cache.get('suspended_models', [])
    else:
        global suspended_models

    try:
        search_models = get_search_models()
        if not models:
            models = search_models
        models = set(models)

        start = now() - SUSPENSION_BUFFER_TIME
        suspended_models.append(models)
        if USE_CACHE:
            cache.set('suspended_models', suspended_models)

        yield

    finally:
        suspended_models.remove(models)
        if USE_CACHE:
            cache.set('suspended_models', suspended_models)

        if permanent is True:
            return

        for index in index_registry.values():
            if index.model in models or models.intersection(index.get_dependencies()):
                qs = index.get_filtered_queryset(since=start)
                index.index_queryset(qs)
