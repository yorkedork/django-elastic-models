from __future__ import unicode_literals
from __future__ import absolute_import

from elastic_models.management.commands import IndexCommand


class Command(IndexCommand):
    def handle_operation(self, index, queryset):
        print("Creating mapping for %s.%s" % (index.model.__name__, index.name))
        index.put_mapping()
        print("Indexing %d %s objects" % (
            queryset.count(), index.model.__name__))
        index.index_queryset(queryset)
