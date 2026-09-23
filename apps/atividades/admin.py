from django.contrib import admin

from .models import Atividade


@admin.register(Atividade)
class AtividadeAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'profissional', 'created_at']
    list_filter = ['category', 'profissional']
    list_select_related = ['profissional__user']
    search_fields = ['title', 'description']
