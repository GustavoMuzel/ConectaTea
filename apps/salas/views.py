import uuid
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import TemplateView

from apps.acompanhamento.models import LogAcesso
from apps.atividades.models import Atividade
from apps.usuarios.mixins import AlunoRequiredMixin, ProfissionalRequiredMixin
from apps.usuarios.models import Aluno

from .forms import EntrarSalaForm, PropostaAtividadeForm, RecusaAtividadeForm
from .models import MembroSala, ParticipacaoVideochamada, Sala, SolicitacaoVinculo, gerar_senha_sala


class QualquerAlunoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Aluno com ou sem vínculo: quem ainda não tem profissional precisa poder responder aos pedidos."""

    def test_func(self):
        return self.request.user.is_aluno


# Vínculo com aceite do aluno ---------------------------------------------------------------------------------

class EnviarPedidoVinculoView(ProfissionalRequiredMixin, View):
    """O profissional aprovado pede para acompanhar um aluno sem vínculo; o vínculo só vale se o aluno aceitar."""

    http_method_names = ['post']

    def post(self, request, pk):
        aluno = get_object_or_404(Aluno, pk=pk, profissional__isnull=True, user__is_active=True)
        _, criado = SolicitacaoVinculo.objects.get_or_create(
            profissional=request.user.profissional, aluno=aluno, status=SolicitacaoVinculo.Status.PENDENTE,
        )
        if criado:
            messages.success(request, f'Pedido enviado. Agora {aluno.user.name} precisa aceitar.')
        else:
            messages.info(request, f'Você já enviou um pedido para {aluno.user.name}. Aguarde a resposta.')
        return redirect('vincular_alunos')


class ResponderPedidoVinculoView(QualquerAlunoMixin, View):
    http_method_names = ['post']

    def post(self, request, pk, resposta):
        if resposta not in ('aceitar', 'recusar'):
            raise Http404
        aluno = request.user.aluno
        with transaction.atomic():
            aluno = Aluno.objects.select_for_update().get(pk=aluno.pk)  # dois cliques não criam duas salas
            pedido = get_object_or_404(
                SolicitacaoVinculo.objects.select_related('profissional__user'),
                pk=pk, aluno=aluno, status=SolicitacaoVinculo.Status.PENDENTE,
            )
            agora = timezone.now()
            if resposta == 'recusar':
                pedido.status, pedido.respondida_em = SolicitacaoVinculo.Status.RECUSADA, agora
                pedido.save(update_fields=['status', 'respondida_em'])
                messages.info(request, f'Você recusou o pedido de {pedido.profissional.user.name}.')
                return redirect('home')
            profissional = pedido.profissional
            if aluno.profissional_id is not None or not profissional.is_approved or not profissional.user.is_active:
                messages.warning(request, 'Este pedido não vale mais.')
                return redirect('home')
            aluno.profissional = profissional
            aluno.save(update_fields=['profissional'])
            pedido.status, pedido.respondida_em = SolicitacaoVinculo.Status.ACEITA, agora
            pedido.save(update_fields=['status', 'respondida_em'])
            # Os outros pedidos perdem o sentido: o aluno já tem profissional.
            aluno.solicitacoes_vinculo.filter(status=SolicitacaoVinculo.Status.PENDENTE).update(
                status=SolicitacaoVinculo.Status.CANCELADA, respondida_em=agora,
            )
            sala, criada = Sala.objects.get_or_create(aluno=aluno, defaults={'dono': profissional})
            if not criada and sala.dono_id != profissional.pk:
                # Vínculo novo sobre sala antiga: o novo profissional assume e a equipe antiga sai.
                # Senha e nome da sala no Jitsi mudam: a equipe antiga ainda conhece a URL da chamada.
                sala.dono, sala.senha, sala.id_videochamada = profissional, gerar_senha_sala(), uuid.uuid4()
                sala.save(update_fields=['dono', 'senha', 'id_videochamada'])
                sala.membros.exclude(status=MembroSala.Status.REMOVIDO).update(
                    status=MembroSala.Status.REMOVIDO, respondido_em=agora)
            LogAcesso.objects.create(user=request.user, aluno=aluno,
                                     acao=f'Aceitou o vínculo com {profissional.user.name}')
        messages.success(request, f'Pronto! Agora {profissional.user.name} acompanha você.')
        return redirect('aluno_atividades')


# Salas (lado do profissional) --------------------------------------------------------------------------------

class SalasView(ProfissionalRequiredMixin, TemplateView):
    """Salas em que o profissional é dono ou membro, e o formulário para pedir entrada com a senha."""

    template_name = 'salas/salas.html'

    def get_context_data(self, **kwargs):
        profissional = self.request.user.profissional
        kwargs['minhas'] = profissional.salas_criadas.select_related('aluno__user').order_by('aluno__user__name')
        kwargs['participacoes'] = (profissional.participacoes.select_related('sala__aluno__user', 'sala__dono__user')
                                   .exclude(status=MembroSala.Status.REMOVIDO).order_by('-solicitado_em'))
        kwargs.setdefault('form', EntrarSalaForm())
        return super().get_context_data(**kwargs)


class EntrarSalaView(SalasView):
    http_method_names = ['post']

    def post(self, request):
        form = EntrarSalaForm(request.POST)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form=form))
        profissional = request.user.profissional
        sala = Sala.objects.filter(senha=form.cleaned_data['senha']).select_related('dono__user').first()
        if sala is None:
            form.add_error('senha', 'Não existe sala com esta senha. Confira com o dono da sala.')
            return self.render_to_response(self.get_context_data(form=form))
        if sala.dono_id == profissional.pk:
            messages.info(request, 'Você é o dono desta sala.')
            return redirect('sala', pk=sala.pk)
        membro, criado = MembroSala.objects.get_or_create(sala=sala, profissional=profissional)
        if not criado and membro.status == MembroSala.Status.APROVADO:
            return redirect('sala', pk=sala.pk)
        if not criado and membro.status != MembroSala.Status.PENDENTE:
            # Recusado ou removido pode pedir de novo; o dono decide outra vez.
            membro.status, membro.respondido_em = MembroSala.Status.PENDENTE, None
            membro.save(update_fields=['status', 'respondido_em'])
        messages.success(request, f'Pedido enviado. {sala.dono.user.name}, dono da sala, precisa aprovar sua entrada.')
        return redirect('salas')


class SalaDoProfissionalMixin(ProfissionalRequiredMixin):
    """Só o dono e os membros aprovados abrem a sala; para os outros ela não existe (404)."""

    @cached_property
    def sala(self):
        sala = get_object_or_404(Sala.objects.select_related('aluno__user', 'dono__user'), pk=self.kwargs['pk'])
        if not sala.participa(self.request.user):  # inclui o dono, e só enquanto o vínculo dele vale
            raise Http404
        return sala

    def eh_dono(self, sala=None):
        return (sala or self.sala).dono_id == self.request.user.profissional.pk


class SoDonoMixin(SalaDoProfissionalMixin):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.is_profissional and not self.eh_dono():
            raise Http404
        return super().dispatch(request, *args, **kwargs)


class SalaView(SalaDoProfissionalMixin, TemplateView):
    template_name = 'salas/sala.html'

    def get_context_data(self, **kwargs):
        sala, dono = self.sala, self.eh_dono()
        kwargs.update(sala=sala, eh_dono=dono, membros=sala.membros_aprovados())
        kwargs.setdefault('form_proposta', PropostaAtividadeForm())
        exclusivas = Atividade.objects.filter(aluno=sala.aluno).select_related('autor__user').order_by('-created_at')
        if dono:
            kwargs['pendentes'] = sala.membros.filter(status=MembroSala.Status.PENDENTE).select_related(
                'profissional__user')
            kwargs['em_analise'] = exclusivas.filter(publicacao=Atividade.Publicacao.EM_ANALISE)
            kwargs['form_recusa'] = RecusaAtividadeForm()
            kwargs['historico'] = exclusivas.exclude(publicacao=Atividade.Publicacao.EM_ANALISE)
        else:  # o membro acompanha as próprias propostas
            kwargs['historico'] = exclusivas.filter(autor=self.request.user.profissional)
        return super().get_context_data(**kwargs)


class ProporAtividadeView(SalaView):
    """Dono publica direto para o aluno; membro propõe e a atividade espera a análise do dono."""

    http_method_names = ['post']

    def post(self, request, pk):
        form = PropostaAtividadeForm(request.POST, request.FILES)
        if not form.is_valid():
            return self.render_to_response(self.get_context_data(form_proposta=form))
        atividade = form.save(commit=False)
        atividade.profissional = self.sala.dono
        atividade.aluno = self.sala.aluno
        atividade.autor = request.user.profissional
        if self.eh_dono():
            atividade.publicacao = Atividade.Publicacao.PUBLICADA
            messages.success(request, f'Atividade "{atividade.title}" publicada para {self.sala.aluno.user.name}.')
        else:
            atividade.publicacao = Atividade.Publicacao.EM_ANALISE
            messages.success(request, f'Atividade "{atividade.title}" enviada. Ela aparece para o aluno depois que '
                                      f'{self.sala.dono.user.name} aprovar.')
        atividade.save()
        return redirect('sala', pk=self.sala.pk)


class AnalisarAtividadeView(SoDonoMixin, View):
    http_method_names = ['post']

    def post(self, request, pk, atividade_pk, decisao):
        if decisao not in ('aprovar', 'recusar'):
            raise Http404
        atividade = get_object_or_404(Atividade, pk=atividade_pk, aluno=self.sala.aluno,
                                      publicacao=Atividade.Publicacao.EM_ANALISE)
        if decisao == 'aprovar':
            atividade.publicacao = Atividade.Publicacao.PUBLICADA
            messages.success(request, f'Atividade "{atividade.title}" publicada para o aluno.')
        else:
            form = RecusaAtividadeForm(request.POST)
            atividade.motivo_recusa = form.cleaned_data['motivo'] if form.is_valid() else ''
            atividade.publicacao = Atividade.Publicacao.RECUSADA
            messages.info(request, f'Atividade "{atividade.title}" recusada.')
        atividade.save(update_fields=['publicacao', 'motivo_recusa'])
        return redirect('sala', pk=self.sala.pk)


class DecidirMembroView(SoDonoMixin, View):
    http_method_names = ['post']
    DECISOES = {
        'aprovar': (MembroSala.Status.PENDENTE, MembroSala.Status.APROVADO, 'agora faz parte da sala'),
        'recusar': (MembroSala.Status.PENDENTE, MembroSala.Status.RECUSADO, 'teve o pedido recusado'),
        'remover': (MembroSala.Status.APROVADO, MembroSala.Status.REMOVIDO, 'foi removido da sala'),
    }

    def post(self, request, pk, membro_pk, decisao):
        if decisao not in self.DECISOES:
            raise Http404
        de, para, texto = self.DECISOES[decisao]
        membro = get_object_or_404(MembroSala.objects.select_related('profissional__user'),
                                   pk=membro_pk, sala=self.sala, status=de)
        membro.status, membro.respondido_em = para, timezone.now()
        membro.save(update_fields=['status', 'respondido_em'])
        if para == MembroSala.Status.APROVADO:
            # Auditoria: mais uma pessoa passa a ver os dados do aluno (RNF05).
            LogAcesso.objects.create(user=request.user, aluno=self.sala.aluno,
                                     acao=f'Aprovou {membro.profissional.user.name} na sala')
        messages.success(request, f'{membro.profissional.user.name} {texto}.')
        return redirect('sala', pk=self.sala.pk)


class TrocarSenhaSalaView(SoDonoMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        sala = self.sala
        sala.senha = gerar_senha_sala()
        while Sala.objects.filter(senha=sala.senha).exclude(pk=sala.pk).exists():
            sala.senha = gerar_senha_sala()
        sala.save(update_fields=['senha'])
        messages.success(request, 'Senha trocada. A senha antiga não funciona mais; quem já está na sala continua.')
        return redirect('sala', pk=sala.pk)


# Videochamada e equipe (aluno) -------------------------------------------------------------------------------

class VideochamadaView(LoginRequiredMixin, View):
    """Registra a entrada e leva ao Jitsi. Só dono, membros aprovados e o próprio aluno entram (RF13)."""

    http_method_names = ['get']

    def get(self, request, pk):
        sala = get_object_or_404(Sala.objects.select_related('aluno', 'dono'), pk=pk)
        if not sala.participa(request.user):
            raise Http404
        ParticipacaoVideochamada.objects.create(sala=sala, user=request.user)
        nome = quote(f'"{request.user.name}"')
        return redirect(f'https://{settings.JITSI_DOMINIO}/ConectaTEA-{sala.id_videochamada}'
                        f'#userInfo.displayName={nome}')


class MinhaEquipeView(AlunoRequiredMixin, TemplateView):
    """O aluno vê quem participa da sala dele (transparência, LGPD) e entra na videochamada."""

    template_name = 'salas/minha_equipe.html'

    def get_context_data(self, **kwargs):
        sala = Sala.objects.filter(aluno=self.request.user.aluno).select_related('dono__user').first()
        kwargs['sala'] = sala
        kwargs['membros'] = sala.membros_aprovados() if sala else []
        return super().get_context_data(**kwargs)
