import uuid
from urllib.parse import quote

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import TemplateView

from apps.acompanhamento.auditoria import Categoria, registrar
from apps.atividades.models import Atividade
from apps.usuarios.mixins import AlunoRequiredMixin, ProfissionalRequiredMixin
from apps.usuarios.models import Aluno
from apps.usuarios.services.email import enviar_aviso_chamada_marcada

from .forms import AgendaChamadaForm, EntrarSalaForm, PropostaAtividadeForm, RecusaAtividadeForm
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
            registrar(request, 'Enviou pedido de vínculo', Categoria.SALAS, aluno=aluno)
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
                registrar(request, f'Recusou o vínculo com {pedido.profissional.user.name}', Categoria.SALAS,
                          aluno=aluno)
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
            registrar(request, f'Aceitou o vínculo com {profissional.user.name}', Categoria.SALAS, aluno=aluno)
        messages.success(request, f'Pronto! Agora {profissional.user.name} acompanha você.')
        return redirect('aluno_painel')


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
        registrar(request, 'Pediu para entrar na sala do aluno', Categoria.SALAS, aluno=sala.aluno)
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
        kwargs['na_chamada'] = sala.na_chamada_agora()
        kwargs['chamadas'] = sala.participacoes_video.select_related('user')[:15]
        if dono:
            kwargs.setdefault('form_agenda', AgendaChamadaForm(instance=sala))
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
        acao = 'Publicou' if self.eh_dono() else 'Propôs'
        registrar(request, f'{acao} a atividade "{atividade.title}" na sala', Categoria.ATIVIDADES,
                  aluno=self.sala.aluno)
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
        verbo = 'Aprovou' if decisao == 'aprovar' else 'Recusou'
        registrar(request, f'{verbo} a atividade proposta "{atividade.title}"', Categoria.ATIVIDADES,
                  aluno=self.sala.aluno)
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
        if para == MembroSala.Status.REMOVIDO:
            # Quem saiu ainda conhece o endereço da chamada: a sala ganha um endereço novo.
            self.sala.id_videochamada = uuid.uuid4()
            self.sala.save(update_fields=['id_videochamada'])
        # Auditoria (RNF05): quem passa a ver, deixa de ver ou teve negado o acesso aos dados do aluno.
        verbo = {MembroSala.Status.APROVADO: 'Aprovou', MembroSala.Status.RECUSADO: 'Recusou',
                 MembroSala.Status.REMOVIDO: 'Removeu'}[para]
        registrar(request, f'{verbo} {membro.profissional.user.name} na sala', Categoria.SALAS, aluno=self.sala.aluno)
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
        registrar(request, 'Trocou a senha da sala', Categoria.SALAS, aluno=sala.aluno)
        messages.success(request, 'Senha trocada. A senha antiga não funciona mais; quem já está na sala continua.')
        return redirect('sala', pk=sala.pk)


# Videochamada e equipe (aluno) -------------------------------------------------------------------------------

def sala_da_chamada(request, pk):
    """A sala, se quem pede participa dela agora (aprovação e conta conferidas de novo a cada acesso)."""
    sala = get_object_or_404(Sala.objects.select_related('aluno__user', 'dono__user'), pk=pk)
    if not sala.participa(request.user):
        raise Http404
    return sala


def aluno_fora_do_horario(request, sala):
    """O aluno só entra no horário que o profissional marcou. Devolve o redirecionamento com o aviso, ou None."""
    if request.user.pk != sala.aluno.user_id or sala.chamada_aberta_para_aluno():
        return None
    if sala.chamada_vigente():
        quando = timezone.localtime(sala.chamada_abre_em).strftime('%d/%m às %Hh%M')
        messages.info(request, f'A videochamada ainda não começou. Ela abre no dia {quando}.')
    else:
        messages.info(request, 'Ainda não há videochamada marcada. O seu profissional vai marcar o dia e a hora.')
    return redirect('minha_equipe')


def nome_da_sala_jitsi(sala):
    return f'ConectaTEA-{sala.id_videochamada}'


class VideochamadaView(LoginRequiredMixin, TemplateView):
    """Chamada embutida no ConectaTEA (RF13). Só aluno, dono e membros aprovados, com a sala ativa."""

    template_name = 'salas/videochamada.html'

    def get(self, request, pk):
        self.sala = sala_da_chamada(request, pk)
        fora = aluno_fora_do_horario(request, self.sala)
        if fora:
            return fora
        self.participacao = ParticipacaoVideochamada.objects.create(
            sala=self.sala, user=request.user, forma=ParticipacaoVideochamada.Forma.EMBUTIDA,
        )
        return super().get(request, pk)

    def get_context_data(self, **kwargs):
        sala, user = self.sala, self.request.user
        kwargs.update(
            sala=sala, participacao=self.participacao, dominio=settings.JITSI_DOMINIO,
            nome_sala=nome_da_sala_jitsi(sala), eh_aluno=user.pk == sala.aluno.user_id,
            voltar=reverse('minha_equipe') if user.pk == sala.aluno.user_id else reverse('sala', args=[sala.pk]),
            equipe=sala.membros_aprovados(),
        )
        return super().get_context_data(**kwargs)


class VideochamadaNovaAbaView(LoginRequiredMixin, View):
    """Plano B: abre a chamada no site do Jitsi. Aqui só dá para registrar o acionamento, não a entrada."""

    http_method_names = ['get']

    def get(self, request, pk):
        sala = sala_da_chamada(request, pk)
        fora = aluno_fora_do_horario(request, sala)
        if fora:
            return fora
        ParticipacaoVideochamada.objects.create(sala=sala, user=request.user,
                                                forma=ParticipacaoVideochamada.Forma.NOVA_ABA)
        nome = quote(f'"{request.user.name}"')
        return redirect(f'https://{settings.JITSI_DOMINIO}/{nome_da_sala_jitsi(sala)}#userInfo.displayName={nome}')


class EventoVideochamadaView(LoginRequiredMixin, View):
    """Recebe da página da chamada os eventos do Jitsi: entrada confirmada e saída."""

    http_method_names = ['post']

    def post(self, request, pk, participacao_pk):
        tipo = request.POST.get('tipo')
        if tipo not in ('entrou', 'saiu'):
            return JsonResponse({'erro': 'tipo inválido'}, status=400)
        participacao = get_object_or_404(ParticipacaoVideochamada, pk=participacao_pk, sala_id=pk, user=request.user,
                                         forma=ParticipacaoVideochamada.Forma.EMBUTIDA)
        agora = timezone.now()
        if tipo == 'entrou':
            # Quem perdeu o acesso no meio do caminho não tem a entrada registrada.
            if not participacao.sala.participa(request.user):
                return JsonResponse({'erro': 'sem acesso'}, status=403)
            if participacao.entrou_em is None:
                participacao.entrou_em = agora
                participacao.save(update_fields=['entrou_em'])
        elif participacao.entrou_em and participacao.saiu_em is None:
            participacao.saiu_em = agora
            participacao.save(update_fields=['saiu_em'])
        return JsonResponse({'ok': True})


class AgendarChamadaView(SoDonoMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        if request.POST.get('limpar'):
            self.sala.proxima_chamada, self.sala.pauta_chamada = None, ''
            self.sala.resposta_aluno, self.sala.respondida_em = '', None
            self.sala.save(update_fields=['proxima_chamada', 'pauta_chamada', 'resposta_aluno', 'respondida_em'])
            registrar(request, 'Desmarcou a videochamada', Categoria.SALAS, aluno=self.sala.aluno)
            messages.info(request, 'Próxima chamada desmarcada.')
            return redirect('sala', pk=self.sala.pk)
        form = AgendaChamadaForm(request.POST, instance=self.sala)
        if form.is_valid():
            sala = form.save(commit=False)
            sala.resposta_aluno, sala.respondida_em = '', None  # horário novo: o aluno responde de novo
            sala.save()
            aluno, quando = sala.aluno, sala.proxima_chamada
            transaction.on_commit(lambda: enviar_aviso_chamada_marcada(aluno, quando), robust=True)
            registrar(request, f'Marcou videochamada para {timezone.localtime(quando):%d/%m/%Y %H:%M}',
                      Categoria.SALAS, aluno=aluno)
            messages.success(request, 'Videochamada marcada. O aluno vê o dia e a hora e só consegue entrar nesse '
                                      'horário (de 15 minutos antes até 2 horas depois).')
        else:
            messages.error(request, ' '.join(e for erros in form.errors.values() for e in erros))
        return redirect('sala', pk=self.sala.pk)


class ResponderChamadaView(AlunoRequiredMixin, View):
    """O aluno avisa se vai participar da videochamada marcada ("Vou participar" ou "Não vou conseguir")."""

    http_method_names = ['post']

    def post(self, request, resposta):
        if resposta not in ('sim', 'nao'):
            raise Http404
        sala = get_object_or_404(Sala, aluno=request.user.aluno)
        if not (sala.ativa() and sala.chamada_vigente()):
            messages.info(request, 'Não há videochamada marcada agora.')
            return redirect('minha_equipe')
        sala.resposta_aluno, sala.respondida_em = resposta, timezone.now()
        sala.save(update_fields=['resposta_aluno', 'respondida_em'])
        texto = 'vai participar' if resposta == 'sim' else 'não vai conseguir'
        registrar(request, f'Respondeu à videochamada: {texto}', Categoria.SALAS, aluno=sala.aluno)
        messages.success(request, 'Obrigado! O seu profissional vai ver a sua resposta.' if resposta == 'sim' else
                         'Tudo bem. O seu profissional vai ver que você não vai conseguir e pode marcar outro horário.')
        return redirect('aluno_painel' if request.POST.get('voltar') == 'inicio' else 'minha_equipe')


class MinhaEquipeView(AlunoRequiredMixin, TemplateView):
    """O aluno vê quem participa da sala dele (transparência, LGPD) e entra na videochamada."""

    template_name = 'salas/minha_equipe.html'

    def get_context_data(self, **kwargs):
        sala = Sala.objects.filter(aluno=self.request.user.aluno).select_related('dono__user').first()
        kwargs['sala'] = sala
        kwargs['ativa'] = bool(sala and sala.ativa())
        kwargs['membros'] = sala.membros_aprovados() if kwargs['ativa'] else []
        kwargs['na_chamada'] = sala.na_chamada_agora() if kwargs['ativa'] else []
        return super().get_context_data(**kwargs)
