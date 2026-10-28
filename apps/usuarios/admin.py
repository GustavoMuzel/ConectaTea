from django.contrib import admin, messages
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import Model, QuerySet
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from .models import Aluno, Profissional, User


class SoftDeleteAdminMixin:
    """Excluir pelo admin só inativa o User (is_active=False); nenhuma linha é apagada."""

    user_id_field = 'user_id'  # caminho do model até o id do User

    def _desativar(self, request: HttpRequest, queryset: QuerySet) -> int:
        users = User.objects.filter(pk__in=queryset.values(self.user_id_field), is_active=True)
        users = users.exclude(pk=request.user.pk)  # ninguém se tranca fora do admin
        if not request.user.is_superuser:
            users = users.exclude(is_superuser=True)
        return users.update(is_active=False)

    def has_delete_permission(self, request: HttpRequest, obj: Model | None = None) -> bool:
        if obj is not None and getattr(obj, self.user_id_field) == request.user.pk:
            return False
        # Desativar altera o User, então exige também change_user.
        return super().has_delete_permission(request, obj) and request.user.has_perm('usuarios.change_user')

    def get_deleted_objects(self, objs, request: HttpRequest):
        # A tela de confirmação não deve listar cascata nem travar no PROTECT: nada será apagado.
        return [str(obj) for obj in objs], {}, set(), []

    def log_deletions(self, request: HttpRequest, queryset: QuerySet):
        return LogEntry.objects.log_actions(
            user_id=request.user.pk, queryset=queryset, action_flag=CHANGE,
            change_message='Desativado (soft delete)',
        )

    def delete_model(self, request: HttpRequest, obj: Model) -> None:
        self._desativar(request, type(obj).objects.filter(pk=obj.pk))

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet) -> None:
        self._desativar(request, queryset)

    def response_delete(self, request: HttpRequest, obj_display: str, obj_id) -> HttpResponse:
        if IS_POPUP_VAR in request.POST:
            return super().response_delete(request, obj_display, obj_id)
        self.message_user(request, f'{self.opts.verbose_name.capitalize()} “{obj_display}” foi desativado.')
        url = reverse(f'admin:{self.opts.app_label}_{self.opts.model_name}_changelist',
                      current_app=self.admin_site.name)
        preserved = {'preserved_filters': self.get_preserved_filters(request), 'opts': self.opts}
        return HttpResponseRedirect(add_preserved_filters(preserved, url))

    def get_actions(self, request: HttpRequest, action_location=admin.ActionLocation.CHANGE_LIST) -> dict:
        actions = super().get_actions(request, action_location)
        actions.pop('delete_selected', None)
        return actions

    @admin.action(description='Desativar usuários selecionados', permissions=['delete'])
    def desativar_usuarios(self, request: HttpRequest, queryset: QuerySet) -> None:
        self.log_deletions(request, queryset)
        total = self._desativar(request, queryset)
        self.message_user(request, f'{total} usuário(s) desativado(s).')


@admin.register(User)
class UserAdmin(SoftDeleteAdminMixin, BaseUserAdmin):
    user_id_field = 'pk'
    actions = ['desativar_usuarios']
    ordering = ['email']
    list_display = ['email', 'name', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['email', 'name']
    fieldsets = [
        (None, {'fields': ['email', 'password']}),
        ('Dados', {'fields': ['name', 'role']}),
        ('Permissões', {'fields': ['is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions']}),
        ('Datas', {'fields': ['last_login']}),
    ]
    add_fieldsets = [
        (None, {'fields': ['email', 'name', 'role', 'password1', 'password2']}),
    ]


@admin.register(Profissional)
class ProfissionalAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    actions = ['desativar_usuarios', 'aprovar_profissionais']
    list_display = ['__str__', 'registro_profissional', 'is_approved']
    list_editable = ['is_approved']
    list_filter = ['is_approved']
    list_select_related = ['user']

    @admin.action(description='Aprovar profissionais selecionados')
    def aprovar_profissionais(self, request: HttpRequest, queryset: QuerySet) -> None:
        if not self.has_change_permission(request):  # staff só de leitura não aprova (RF05/RN01)
            self.message_user(request, 'Você não tem permissão para aprovar profissionais.', messages.ERROR)
            return
        total = queryset.update(is_approved=True)
        self.message_user(request, f'{total} profissional(is) aprovado(s).')


@admin.register(Aluno)
class AlunoAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
    actions = ['desativar_usuarios']
    list_display = ['__str__', 'profissional', 'consentimento_data']
    list_filter = ['profissional']
    list_select_related = ['user', 'profissional__user']
    search_fields = ['user__name', 'guardian_name']
