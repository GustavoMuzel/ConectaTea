from django.contrib import admin

from .models import RegistroEvolucao


@admin.register(RegistroEvolucao)
class RegistroEvolucaoAdmin(admin.ModelAdmin):
    list_display = ['aluno', 'atividade', 'status', 'data_realizacao']
    list_select_related = ['aluno__user', 'atividade']

    def has_delete_permission(self, request, obj=None):
        return False  # histórico de evolução nunca é apagado
