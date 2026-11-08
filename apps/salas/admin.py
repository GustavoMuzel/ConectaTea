from django.contrib import admin

from .models import MembroSala, ParticipacaoVideochamada, Sala, SolicitacaoVinculo


class MembroInline(admin.TabularInline):
    model = MembroSala
    extra = 0
    fields = ['profissional', 'status', 'solicitado_em', 'respondido_em']
    readonly_fields = ['solicitado_em', 'respondido_em']


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'dono', 'criada_em']
    list_select_related = ['aluno__user', 'dono__user']
    search_fields = ['aluno__user__name', 'dono__user__name']
    readonly_fields = ['id_videochamada', 'criada_em']
    inlines = [MembroInline]


@admin.register(SolicitacaoVinculo)
class SolicitacaoVinculoAdmin(admin.ModelAdmin):
    list_display = ['profissional', 'aluno', 'status', 'criada_em', 'respondida_em']
    list_filter = ['status']
    list_select_related = ['profissional__user', 'aluno__user']


@admin.register(ParticipacaoVideochamada)
class ParticipacaoVideochamadaAdmin(admin.ModelAdmin):
    """Só consulta: registro de quem entrou na chamada (RF13)."""

    list_display = ['sala', 'user', 'entrou_em']
    list_select_related = ['sala__aluno__user', 'user']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
