from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import redirect


class ProfissionalRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Sem login: vai para a tela de login. Profissional ainda não aprovado: volta ao início com aviso.
    Logado sem perfil profissional: 403."""

    def test_func(self):
        return self.request.user.is_profissional

    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated and user.is_profissional_pendente:
            messages.warning(self.request, 'Sua conta ainda aguarda a aprovação de um administrador.')
            return redirect('home')
        return super().handle_no_permission()


class AlunoRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Sem login: vai para a tela de login. Aluno ainda sem profissional: volta ao início com aviso.
    Logado sem perfil aluno: 403."""

    def test_func(self):
        user = self.request.user
        return user.is_aluno and not user.is_aluno_sem_vinculo

    def handle_no_permission(self):
        user = self.request.user
        if user.is_authenticated and user.is_aluno_sem_vinculo:
            messages.info(self.request, 'Sua conta ainda não está ligada a um profissional.')
            return redirect('home')
        return super().handle_no_permission()


class GestorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Sem login: vai para a tela de login. is_staff sozinho não basta: exige a permissão de model
    (mesmo padrão de SoftDeleteAdminMixin), senão um staff só de leitura no admin nativo aprovaria
    profissionais aqui."""

    def test_func(self):
        user = self.request.user
        return user.is_superuser or (user.is_staff and user.has_perm('usuarios.change_profissional'))
