from django.apps import AppConfig


class AcompanhamentoConfig(AppConfig):
    name = "apps.acompanhamento"

    def ready(self):
        from . import sinais  # noqa: F401  (registra os sinais de login/logout na auditoria)
