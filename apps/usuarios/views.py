from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import CreateView, TemplateView, UpdateView
from rest_framework.generics import RetrieveAPIView

from apps.acompanhamento.models import RegistroEvolucao
from apps.atividades.models import Atividade

from .forms import CadastroForm, LoginForm, PreferenciasForm
from .mixins import GestorRequiredMixin
from .models import Aluno, PreferenciaAcessibilidade, Profissional, User
from .serializers import UserMeSerializer
from .services.email import enviar_boas_vindas, enviar_notificacao_aluno_criado


class UserMeView(RetrieveAPIView):
    serializer_class = UserMeSerializer

    def get_object(self):
        return User.objects.select_related('aluno', 'profissional').get(pk=self.request.user.pk)


class EntrarView(LoginView):
    form_class = LoginForm
    redirect_authenticated_user = True


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
        if request.user.is_aluno:
            return redirect('aluno_atividades')
        return super().get(request, *args, **kwargs)


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
