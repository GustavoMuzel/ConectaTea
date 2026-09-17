from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin


class ProfissionalRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Sem login: vai para a tela de login. Logado sem perfil profissional: 403."""

    def test_func(self):
        return self.request.user.is_profissional


class AlunoRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Sem login: vai para a tela de login. Logado sem perfil aluno: 403."""

    def test_func(self):
        return self.request.user.is_aluno


class GestorRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Sem login: vai para a tela de login. is_staff sozinho não basta: exige a permissão de model
    (mesmo padrão de SoftDeleteAdminMixin), senão um staff só de leitura no admin nativo aprovaria
    profissionais aqui."""

    def test_func(self):
        user = self.request.user
        return user.is_superuser or (user.is_staff and user.has_perm('usuarios.change_profissional'))
