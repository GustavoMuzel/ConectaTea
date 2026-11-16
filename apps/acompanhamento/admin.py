from django.contrib import admin

from .models import LogAcesso, RegistroEvolucao


@admin.register(RegistroEvolucao)
class RegistroEvolucaoAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'atividade', 'status', 'data_realizacao']
    list_select_related = ['aluno__user', 'atividade']

    def has_delete_permission(self, request, obj=None):
        return False  # histórico de evolução nunca é apagado


@admin.register(LogAcesso)
class LogAcessoAdmin(admin.ModelAdmin):
    """Auditoria (RNF05): só consulta. Ninguém cria, edita ou apaga registros pelo admin."""

    list_display = ['ocorrido_em', 'user', 'aluno', 'acao']
    list_select_related = ['user', 'aluno__user']
    search_fields = ['user__name', 'aluno__user__name', 'acao']
    date_hierarchy = 'ocorrido_em'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
