import csv
import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.http import HttpResponse
from django.db.models import Count
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.debug import sensitive_post_parameters
from django.views.generic import CreateView, FormView, ListView, TemplateView, UpdateView
from rest_framework.generics import RetrieveAPIView

from apps.acompanhamento.auditoria import Categoria, registrar
from apps.acompanhamento.models import RegistroEvolucao
from apps.atividades.models import Atividade

from .forms import CadastroForm, CodigoNovaSenhaForm, LoginForm, PreferenciasForm, RecuperarSenhaForm
from .mixins import GestorRequiredMixin
from .models import Aluno, PreferenciaAcessibilidade, Profissional, User
from .serializers import UserMeSerializer
from .services import limites, recuperacao
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
        # Limite por e-mail digitado, exista ou não a conta (não vira oráculo). Cache compartilhado (settings).
        if limites.pode_pedir_codigo(email, LIMITE_RECUPERACAO_SEGUNDOS):
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
        registrar(self.request, 'Trocou a senha com o código de recuperação', Categoria.AUTENTICACAO,
                  user=registro.user)
        messages.success(self.request, 'Senha alterada. Agora é só entrar com a senha nova.')
        return super().form_valid(form)


@method_decorator(sensitive_post_parameters(), name='dispatch')
class CadastroView(CreateView):
    form_class = CadastroForm
    template_name = 'usuarios/cadastro.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        kwargs['profissoes_com_conselho'] = json.dumps([str(p) for p in Profissional.CONSELHOS])
        return super().get_context_data(**kwargs)

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
        registrar(self.request, f'Criou a conta ({user.get_role_display()})', Categoria.AUTENTICACAO, user=user)
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
            return redirect('aluno_painel')
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


class SobreTeaView(TemplateView):
    """Página pública e informativa sobre o TEA, com as fontes citadas."""

    template_name = 'usuarios/sobre_tea.html'


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
        kwargs['brevo'] = {'chave': bool(settings.BREVO_API_KEY), 'remetente': settings.BREVO_SENDER_EMAIL}
        kwargs['profissionais_aprovados'] = (Profissional.objects.filter(is_approved=True, user__is_active=True)
                                             .select_related('user', 'aprovado_por').order_by('user__name'))
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
    """Aprovar vale como conferência do registro no conselho: grava quem aprovou e quando."""

    http_method_names = ['post']

    def post(self, request, pk):
        profissional = get_object_or_404(Profissional.objects.select_related('user'), pk=pk)
        profissional.is_approved = True
        profissional.aprovado_em, profissional.aprovado_por = timezone.now(), request.user
        profissional.save(update_fields=['is_approved', 'aprovado_em', 'aprovado_por'])
        registro = profissional.registro_formatado or profissional.especialidade
        registrar(request, f'Aprovou o profissional {profissional.user.name} ({registro})', Categoria.GESTAO)
        messages.success(request, f'Profissional "{profissional.user.name}" aprovado.')
        return redirect('painel_gestao')


class RevogarProfissionalGestaoView(GestorRequiredMixin, View):
    """Tira a aprovação: o profissional perde o painel, os alunos, as salas e a videochamada na hora."""

    http_method_names = ['post']

    def post(self, request, pk):
        profissional = get_object_or_404(Profissional.objects.select_related('user'), pk=pk, is_approved=True)
        profissional.is_approved = False
        profissional.save(update_fields=['is_approved'])
        registrar(request, f'Revogou a aprovação de {profissional.user.name}', Categoria.GESTAO)
        messages.warning(request, f'Aprovação de "{profissional.user.name}" revogada.')
        return redirect('painel_gestao')


class TesteEmailView(GestorRequiredMixin, View):
    """Botão do Painel de Gestão: manda um e-mail de teste pelo Brevo e mostra o motivo, se falhar."""

    http_method_names = ['post']

    def post(self, request):
        from .services.email import diagnosticar_brevo

        destino = (request.POST.get('destino') or request.user.email).strip()
        ok, mensagem = diagnosticar_brevo(destino)
        (messages.success if ok else messages.error)(request, mensagem)
        return redirect(reverse('painel_gestao') + '#titulo-email')


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


class AuditoriaView(GestorRequiredMixin, ListView):
    """Aba Auditoria do Painel de Gestão (RNF05, Marco Civil art. 15): todas as ações registradas e as videochamadas.

    Só leitura. Filtros por tipo, pessoa, aluno e período; exporta o resultado filtrado em CSV.
    """

    template_name = 'usuarios/auditoria.html'
    paginate_by = 30
    ABAS = {'acoes': 'Todas as ações', 'acessos': 'Acessos a dados de alunos', 'videochamadas': 'Videochamadas'}

    def get_aba(self):
        aba = self.request.GET.get('aba', 'acoes')
        return aba if aba in self.ABAS else 'acoes'

    def get_queryset(self):
        from apps.acompanhamento.models import LogAcesso
        from apps.salas.models import ParticipacaoVideochamada

        g, aba = self.request.GET, self.get_aba()
        if aba == 'videochamadas':
            qs = ParticipacaoVideochamada.objects.select_related('user', 'sala__aluno__user')
            campo_data, campo_aluno = 'acionada_em', 'sala__aluno__user__name'
        else:
            qs = LogAcesso.objects.select_related('user', 'aluno__user')
            campo_data, campo_aluno = 'ocorrido_em', 'aluno__user__name'
            if aba == 'acessos':
                qs = qs.filter(categoria=LogAcesso.Categoria.DADOS_ALUNO)
            elif g.get('tipo') in LogAcesso.Categoria.values:
                qs = qs.filter(categoria=g['tipo'])
        if g.get('pessoa'):
            qs = qs.filter(user__name__icontains=g['pessoa'].strip())
        if g.get('aluno'):
            qs = qs.filter(**{f'{campo_aluno}__icontains': g['aluno'].strip()})
        for chave, operador in (('de', 'gte'), ('ate', 'lte')):
            data = parse_date(g.get(chave, '') or '')
            if data:
                qs = qs.filter(**{f'{campo_data}__date__{operador}': data})
        return qs

    def get(self, request, *args, **kwargs):
        if request.GET.get('formato') == 'csv':
            return self.exportar_csv()
        return super().get(request, *args, **kwargs)

    def exportar_csv(self):
        resposta = HttpResponse(content_type='text/csv; charset=utf-8')
        resposta['Content-Disposition'] = f'attachment; filename="auditoria-{self.get_aba()}.csv"'
        resposta.write('\ufeff')  # BOM: o Excel abre os acentos certos
        escritor = csv.writer(resposta, delimiter=';')

        def quando(data):
            return timezone.localtime(data).strftime('%d/%m/%Y %H:%M') if data else ''

        if self.get_aba() == 'videochamadas':
            escritor.writerow(['Pessoa', 'Aluno da sala', 'Forma', 'Abriu', 'Entrada confirmada', 'Saída confirmada'])
            for p in self.get_queryset():
                escritor.writerow([p.user.name, p.sala.aluno.user.name, p.get_forma_display(),
                                   quando(p.acionada_em), quando(p.entrou_em), quando(p.saiu_em)])
        else:
            escritor.writerow(['Quando', 'Tipo', 'Pessoa', 'Aluno', 'Ação', 'IP'])
            for log in self.get_queryset():
                escritor.writerow([quando(log.ocorrido_em), log.get_categoria_display(),
                                   log.user.name if log.user else '', log.aluno.user.name if log.aluno else '',
                                   log.acao, log.ip or ''])
        return resposta

    def get_context_data(self, **kwargs):
        from apps.acompanhamento.models import LogAcesso

        filtros = self.request.GET.copy()
        filtros.pop('page', None)
        kwargs.update(aba=self.get_aba(), abas=self.ABAS, filtros=filtros.urlencode(), g=self.request.GET,
                      tipos=LogAcesso.Categoria.choices)
        return super().get_context_data(**kwargs)
