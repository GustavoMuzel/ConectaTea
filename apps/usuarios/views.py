import hashlib
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect, resolve_url
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import CreateView, FormView, TemplateView, UpdateView
from rest_framework.generics import RetrieveAPIView

from apps.acompanhamento.models import RegistroEvolucao
from apps.atividades.models import Atividade

from .forms import CadastroForm, CodigoNovaSenhaForm, LoginForm, PreferenciasForm, RecuperarSenhaForm
from .mixins import GestorRequiredMixin
from .models import Aluno, PreferenciaAcessibilidade, Profissional, User
from .serializers import UserMeSerializer
from .services import recuperacao
from .services.email import enviar_boas_vindas, enviar_notificacao_aluno_criado


class UserMeView(RetrieveAPIView):
    serializer_class = UserMeSerializer

    def get_object(self):
        return User.objects.select_related('aluno', 'profissional').get(pk=self.request.user.pk)


MSG_PROFISSIONAL_PENDENTE = (
    'Sua conta de profissional está aguardando a aprovação de um administrador. '
    'Assim que for aprovada, você poderá cadastrar atividades e acompanhar seus alunos.'
)


@method_decorator(sensitive_post_parameters(), name='dispatch')
class EntrarView(LoginView):
    form_class = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.get_user()
        messages.success(self.request, f'Olá, {user.name}. Você entrou no ConectaTEA.')
        # Pendente que ia para outra página também é avisado; na home, o próprio cartão já explica.
        if user.is_profissional_pendente and self.get_success_url() != resolve_url('home'):
            messages.warning(self.request, MSG_PROFISSIONAL_PENDENTE)
        return response


class SairView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.info(request, 'Você saiu da sua conta. Até logo!')
        return response


SESSAO_EMAIL_RECUPERACAO = 'recuperacao_senha_email'
LIMITE_RECUPERACAO_SEGUNDOS = 300


class RecuperarSenhaView(FormView):
    """Passo 1 do RF03: pede o e-mail e envia o código. A resposta é a mesma exista ou não a conta."""

    form_class = RecuperarSenhaForm
    template_name = 'registration/recuperar_senha.html'
    success_url = reverse_lazy('recuperar_senha_codigo')

    def form_valid(self, form):
        email = form.cleaned_data['email'].lower()
        self.request.session[SESSAO_EMAIL_RECUPERACAO] = email
        # Limite por e-mail digitado, exista ou não a conta (não vira oráculo). cache.add é atômico.
        # ponytail: LocMemCache é por processo; com vários workers, configurar CACHES compartilhado.
        chave = 'reset_limit_' + hashlib.sha256(email.encode()).hexdigest()
        if cache.add(chave, 1, timeout=LIMITE_RECUPERACAO_SEGUNDOS):
            recuperacao.solicitar_codigo(email)
            messages.info(self.request,
                          'Se existir uma conta com esse e-mail, enviamos um código de 6 números para ele.')
        else:
            messages.warning(self.request, 'Aguarde 5 minutos para pedir outro código. '
                                           'Se você já recebeu um, digite-o abaixo.')
        return super().form_valid(form)


@method_decorator(sensitive_post_parameters(), name='dispatch')
class RecuperarSenhaCodigoView(FormView):
    """Passo 2 do RF03: confere o código (até 5 tentativas) e grava a senha nova."""

    form_class = CodigoNovaSenhaForm
    template_name = 'registration/recuperar_senha_codigo.html'
    success_url = reverse_lazy('login')
    MSG_CODIGO = 'Código incorreto, vencido ou já usado. Confira o e-mail ou peça um código novo.'

    def dispatch(self, request, *args, **kwargs):
        self.email = request.session.get(SESSAO_EMAIL_RECUPERACAO)
        if not self.email:
            return redirect('recuperar_senha')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        kwargs['email'] = self.email
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        with transaction.atomic():
            registro = recuperacao.conferir_codigo(self.email, form.cleaned_data['codigo'])
            if registro is None:
                form.add_error('codigo', self.MSG_CODIGO)
                return self.form_invalid(form)
            if not form.validar_senha_para(registro.user):  # senha fraca não gasta tentativa
                return self.form_invalid(form)
            recuperacao.usar_codigo(registro, form.cleaned_data['nova_senha1'])
        del self.request.session[SESSAO_EMAIL_RECUPERACAO]
        messages.success(self.request, 'Senha alterada. Agora é só entrar com a senha nova.')
        return super().form_valid(form)


@method_decorator(sensitive_post_parameters(), name='dispatch')
class CadastroView(CreateView):
    form_class = CadastroForm
    template_name = 'usuarios/cadastro.html'
    success_url = reverse_lazy('home')

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        user = self.object
        transaction.on_commit(lambda: enviar_boas_vindas(user), robust=True)
        if user.is_aluno:
            transaction.on_commit(lambda: enviar_notificacao_aluno_criado(user), robust=True)
        login(self.request, user)
        messages.success(self.request, 'Conta criada com sucesso. Bem-vindo(a) ao ConectaTEA!')
        return response


class HomeView(TemplateView):
    """`/`: página pública para visitantes; painel/atividades para quem já tem conta."""

    template_name = 'usuarios/home.html'

    def get(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            self.template_name = 'usuarios/landing.html'
            return super().get(request, *args, **kwargs)
        if request.user.is_profissional:
            return redirect('painel')
        if request.user.is_aluno and not request.user.is_aluno_sem_vinculo:
            return redirect('aluno_atividades')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.salas.models import SolicitacaoVinculo  # import local: salas depende de usuarios

        if self.request.user.is_authenticated and self.request.user.is_aluno_sem_vinculo:
            kwargs['pedidos_vinculo'] = SolicitacaoVinculo.objects.filter(
                aluno=self.request.user.aluno, status=SolicitacaoVinculo.Status.PENDENTE,
                profissional__is_approved=True, profissional__user__is_active=True,
            ).select_related('profissional__user')
        return super().get_context_data(**kwargs)


class TermosView(TemplateView):
    template_name = 'usuarios/termos.html'


class PrivacidadeView(TemplateView):
    template_name = 'usuarios/privacidade.html'


class AdminDashboardView(GestorRequiredMixin, TemplateView):
    """`/painel-gestao/`: visão gerencial simplificada, alternativa ao admin técnico do Django."""

    template_name = 'usuarios/painel_gestao.html'

    def get_context_data(self, **kwargs):
        pendentes = list(
            Profissional.objects.filter(is_approved=False).select_related('user').order_by('user__name'),
        )
        kwargs['total_alunos_ativos'] = Aluno.objects.filter(user__is_active=True).count()
        kwargs['total_profissionais_aprovados'] = Profissional.objects.filter(is_approved=True).count()
        kwargs['total_profissionais_pendentes'] = len(pendentes)
        kwargs['profissionais_pendentes'] = pendentes
        kwargs['total_atividades'] = Atividade.objects.count()
        # Conclusões do sistema todo por semana, últimos 3 meses (mesmo padrão do dashboard do profissional).
        desde = timezone.now() - timedelta(days=90)
        por_semana = RegistroEvolucao.objects.filter(
            status=RegistroEvolucao.Status.CONCLUIDA, data_realizacao__gte=desde,
        ).annotate(semana=TruncWeek('data_realizacao')).values('semana').annotate(total=Count('pk')).order_by('semana')
        kwargs['semanas'] = [(linha['semana'].strftime('%d/%m/%Y'), linha['total']) for linha in por_semana]
        kwargs['dados'] = {
            'rotulos': [rotulo for rotulo, _ in kwargs['semanas']],
            'valores': [total for _, total in kwargs['semanas']],
        }
        return super().get_context_data(**kwargs)


class AprovarProfissionalGestaoView(GestorRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        profissional = get_object_or_404(Profissional, pk=pk)
        profissional.is_approved = True
        profissional.save(update_fields=['is_approved'])
        messages.success(request, f'Profissional "{profissional.user.name}" aprovado.')
        return redirect('painel_gestao')


class PreferenciasView(LoginRequiredMixin, UpdateView):
    """Cada usuário ajusta só as próprias preferências; o registro nasce no primeiro acesso."""

    form_class = PreferenciasForm
    template_name = 'usuarios/preferencias.html'
    success_url = reverse_lazy('preferencias')

    def get_object(self, queryset=None):
        return PreferenciaAcessibilidade.objects.get_or_create(user=self.request.user)[0]

    def form_valid(self, form):
        messages.success(self.request, 'Preferências salvas.')
        return super().form_valid(form)
