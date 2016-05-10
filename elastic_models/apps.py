from django.apps import AppConfig
from .utils import autoload_submodules


class ElasticModelsConfig(AppConfig):
    name = 'elastic_models'
    verbose_name = "Elastic Models"
    
    def ready(self):
        autoload_submodules(['indexes'])
        from .receivers import register_receivers
        register_receivers()
