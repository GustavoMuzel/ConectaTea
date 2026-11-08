from collections import Counter

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.messages.views import SuccessMessageMixin
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef, Q
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import DeleteView, DetailView, FormView, ListView, TemplateView, UpdateView

from apps.atividades.models import Atividade
from apps.usuarios.mixins import AlunoRequiredMixin, ProfissionalRequiredMixin
from apps.usuarios.models import Aluno

from .forms import AnotacaoForm, ConclusaoForm, DistribuicaoAtividadeForm
from .models import Anotacao, Atribuicao, RegistroEvolucao


def atividades_do_aluno(aluno):
    # Profissional revogado ou desativado deixa de entregar atividades aos alunos dele.
    # Da sala, só chegam as atividades exclusivas deste aluno já publicadas (as dos membros passam pelo dono).
    return Atividade.objects.filter(
        Q(aluno__isnull=True) | Q(aluno=aluno),
        profissional_id=aluno.profissional_id, publicacao=Atividade.Publicacao.PUBLICADA,
        profissional__is_approved=True, profissional__user__is_active=True,
    )


class AtividadesAlunoView(AlunoRequiredMixin, ListView):
    """Atividades do profissional do aluno que ele ainda não concluiu."""

    template_name = 'acompanhamento/atividades_aluno.html'
    context_object_name = 'atividades'

    def get_queryset(self):
        aluno = self.request.user.aluno
        concluidas = RegistroEvolucao.objects.filter(
            aluno=aluno, status=RegistroEvolucao.Status.CONCLUIDA,
        ).values('atividade')
        return atividades_do_aluno(aluno).exclude(pk__in=concluidas).order_by('created_at')


def material_aberto(request, atividade):
    """Atividade sem material (antiga) não exige abrir nada."""
    from apps.atividades.views import SESSAO_MATERIAIS_ABERTOS

    if not atividade.tipo_material:
        return True
    return atividade.pk in request.session.get(SESSAO_MATERIAIS_ABERTOS, [])


class ConfirmarConclusaoView(AlunoRequiredMixin, DetailView):
    """Tela da atividade: material, campo de resposta e o botão de concluir (nada se conclui na lista)."""

    http_method_names = ['get']
    template_name = 'acompanhamento/confirmar_conclusao.html'
    context_object_name = 'atividade'

    def get_queryset(self):
        return atividades_do_aluno(self.request.user.aluno)

    def get_context_data(self, **kwargs):
        kwargs.setdefault('form', ConclusaoForm())
        kwargs['aberto'] = material_aberto(self.request, self.object)
        return super().get_context_data(**kwargs)


class ConcluirAtividadeView(AlunoRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        aluno = request.user.aluno
        # Só atividades do próprio profissional: id de outra atividade dá 404.
        atividade = get_object_or_404(atividades_do_aluno(aluno), pk=pk)
        form = ConclusaoForm(request.POST)
        aberto = material_aberto(request, atividade)
        if not aberto:
            form.is_valid()
            form.add_error(None, 'Abra o material da atividade antes de concluir.')
        if not aberto or not form.is_valid():
            return render(request, 'acompanhamento/confirmar_conclusao.html',
                          {'atividade': atividade, 'form': form, 'aberto': aberto})
        resposta = form.cleaned_data['resposta']
        with transaction.atomic():
            # Trava o aluno: dois cliques seguidos não geram duas conclusões.
            Aluno.objects.select_for_update().get(pk=aluno.pk)
            registros = RegistroEvolucao.objects.filter(aluno=aluno, atividade=atividade)
            refazendo = registros.filter(status=RegistroEvolucao.Status.EM_ANDAMENTO).first()
            criado = True
            if refazendo:  # tentativa aberta por "Fazer de novo": é ela que termina agora
                refazendo.status = RegistroEvolucao.Status.CONCLUIDA
                refazendo.data_realizacao = timezone.now()
                refazendo.resposta = resposta
                refazendo.save(update_fields=['status', 'data_realizacao', 'resposta'])
            elif registros.filter(status=RegistroEvolucao.Status.CONCLUIDA).exists():
                criado = False
            else:
                RegistroEvolucao.objects.create(
                    aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.CONCLUIDA, resposta=resposta,
                )
            # Distribuída: vira CONCLUIDA. Sem distribuição prévia, nasce já concluída (a unicidade evita duplicata).
            Atribuicao.objects.update_or_create(
                aluno=aluno, atividade=atividade, defaults={'status': Atribuicao.Status.CONCLUIDA},
                create_defaults={'profissional': atividade.profissional, 'status': Atribuicao.Status.CONCLUIDA},
            )
        if criado:
            messages.success(request, f'Atividade concluída: {atividade.title}.')
        else:
            messages.info(request, f'Esta atividade já estava concluída: {atividade.title}.')
        return redirect('aluno_atividades')


class HistoricoAlunoView(AlunoRequiredMixin, ListView):
    """Atividades que o aluno já concluiu, com o total de tentativas e a data da última."""

    template_name = 'acompanhamento/historico_aluno.html'
    context_object_name = 'atividades'

    def get_queryset(self):
        aluno = self.request.user.aluno
        # Mesma regra da lista: atividade de profissional revogado/desativado não é entregue (nem refeita).
        return RegistroEvolucao.objects.filter(
            aluno=aluno, status=RegistroEvolucao.Status.CONCLUIDA, atividade__in=atividades_do_aluno(aluno),
        ).values('atividade', 'atividade__title', 'atividade__category').annotate(
            tentativas=Count('pk'), ultima=Max('data_realizacao'),
        ).order_by('-ultima', 'atividade__title')


class RefazerAtividadeView(AlunoRequiredMixin, View):
    """Abre uma nova tentativa (em andamento) e leva o aluno à tela de confirmação."""

    http_method_names = ['post']

    def post(self, request, pk):
        aluno = request.user.aluno
        concluidas = RegistroEvolucao.objects.filter(
            aluno=aluno, status=RegistroEvolucao.Status.CONCLUIDA,
        ).values('atividade')
        # Só refaz o que já concluiu, de um profissional ativo; o resto dá 404.
        atividade = get_object_or_404(atividades_do_aluno(aluno).filter(pk__in=concluidas), pk=pk)
        # Já havendo uma tentativa aberta, ela é retomada (a constraint garante uma só).
        RegistroEvolucao.objects.get_or_create(
            aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.EM_ANDAMENTO,
        )
        return redirect('confirmar_conclusao', pk=atividade.pk)


class DistribuirAtividadeView(ProfissionalRequiredMixin, FormView):
    """Distribui uma atividade da biblioteca do profissional a um ou mais alunos vinculados."""

    form_class = DistribuicaoAtividadeForm
    template_name = 'acompanhamento/distribuir_atividade.html'
    success_url = reverse_lazy('painel')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        profissional = self.request.user.profissional
        # Só atividades ativas do próprio profissional: id de outra atividade ou arquivada dá 404.
        atividade = get_object_or_404(profissional.atividades.filter(arquivada=False, aluno__isnull=True),
                                      pk=self.kwargs['pk'])
        return kwargs | {'profissional': profissional, 'initial': {'atividade': atividade}}

    def form_valid(self, form):
        dados = form.cleaned_data
        profissional = self.request.user.profissional
        criadas = 0
        with transaction.atomic():
            for aluno in dados['alunos']:
                # A unicidade (atividade, aluno) evita duplicata em reenvio ou duas abas.
                _, criada = Atribuicao.objects.get_or_create(
                    atividade=dados['atividade'], aluno=aluno,
                    defaults={'profissional': profissional, 'prazo': dados['prazo']},
                )
                criadas += criada
        total = len(dados['alunos'])
        if criadas:
            messages.success(self.request, f'Atividade distribuída: {criadas} de {total} aluno(s).')
        if criadas < total:
            messages.warning(self.request, 'Alguns alunos já tinham esta atividade e foram mantidos como estavam.')
        return super().form_valid(form)


class DashboardProfissionalView(ProfissionalRequiredMixin, TemplateView):
    """Números e gráficos de conclusões, só dos alunos vinculados ao profissional logado."""

    template_name = 'acompanhamento/dashboard_profissional.html'

    def get_context_data(self, **kwargs):
        profissional = self.request.user.profissional
        # Alunos inativos entram, como na tela "Meus alunos": o histórico não some com o soft delete.
        concluidas = RegistroEvolucao.objects.filter(
            aluno__profissional=profissional, status=RegistroEvolucao.Status.CONCLUIDA,
        )
        por_semana = concluidas.annotate(semana=TruncWeek('data_realizacao')).values('semana').annotate(
            total=Count('pk')).order_by('semana')
        por_aluno = list(concluidas.values('aluno', 'aluno__user__name').annotate(total=Count('pk')).order_by(
            '-total', 'aluno__user__name'))
        homonimos = Counter(linha['aluno__user__name'] for linha in por_aluno)
        kwargs['semanas'] = [(linha['semana'].strftime('%d/%m/%Y'), linha['total']) for linha in por_semana]
        kwargs['alunos'] = [
            (linha['aluno__user__name'] if homonimos[linha['aluno__user__name']] == 1
             else f"{linha['aluno__user__name']} (#{linha['aluno']})", linha['total'])
            for linha in por_aluno
        ]
        kwargs['total_alunos'] = profissional.alunos.count()
        # ConcluirAtividadeView já marca a Atribuicao como CONCLUIDA; o Exists() cobre só atribuições antigas.
        kwargs['total_pendentes'] = Atribuicao.objects.filter(
            profissional=profissional, status=Atribuicao.Status.PENDENTE,
        ).exclude(Exists(concluidas.filter(aluno=OuterRef('aluno'), atividade=OuterRef('atividade')))).count()
        kwargs['total_concluidas'] = sum(total for _, total in kwargs['alunos'])
        # json_script serializa; aqui vão só listas e dicts simples.
        kwargs['dados'] = {
            grupo: {'rotulos': [rotulo for rotulo, _ in pares], 'valores': [total for _, total in pares]}
            for grupo, pares in (('semanas', kwargs['semanas']), ('alunos', kwargs['alunos']))
        }
        return super().get_context_data(**kwargs)


class AnotacoesView(FormView):
    """Lista as anotações que o usuário pode ler sobre um aluno e cria novas. As subclasses dizem qual aluno."""

    form_class = AnotacaoForm
    template_name = 'acompanhamento/anotacoes.html'

    def get_context_data(self, **kwargs):
        kwargs['aluno'] = self.aluno
        kwargs['anotacoes'] = Anotacao.objects.visiveis_para(self.request.user, self.aluno).select_related('autor')
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        # Autor e aluno vêm da sessão e da URL validada, nunca do POST.
        form.instance.autor = self.request.user
        form.instance.aluno = self.aluno
        form.save()
        messages.success(self.request, 'Anotação salva.')
        return super().form_valid(form)

    def get_success_url(self):
        return self.request.path


class AnotacoesProfissionalView(ProfissionalRequiredMixin, AnotacoesView):
    @cached_property
    def aluno(self):
        # Só alunos do próprio profissional: id de outro dá 404.
        alunos = self.request.user.profissional.alunos.select_related('user')
        return get_object_or_404(alunos, pk=self.kwargs['aluno_pk'])


class AnotacoesAlunoView(AlunoRequiredMixin, AnotacoesView):
    @cached_property
    def aluno(self):
        return self.request.user.aluno


class AutorDeAnotacaoMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Só o autor mexe na anotação: a de outro, mesmo compartilhada comigo, dá 404."""

    def test_func(self):
        user = self.request.user
        return user.is_profissional or (user.is_aluno and not user.is_aluno_sem_vinculo)

    def get_queryset(self):
        return Anotacao.objects.filter(autor=self.request.user)

    def get_success_url(self):
        aluno = self.object.aluno
        if self.request.user.pk == aluno.user_id:
            return reverse('anotacoes_aluno')
        if aluno.profissional is None or aluno.profissional.user_id != self.request.user.pk:  # trocou de profissional
            return reverse('alunos_profissional')
        return reverse('anotacoes_profissional', args=[aluno.pk])


class AnotacaoEditarView(AutorDeAnotacaoMixin, SuccessMessageMixin, UpdateView):
    form_class = AnotacaoForm
    template_name = 'acompanhamento/anotacao_form.html'
    success_message = 'Anotação atualizada.'


class AnotacaoExcluirView(AutorDeAnotacaoMixin, SuccessMessageMixin, DeleteView):
    template_name = 'acompanhamento/anotacao_confirmar_exclusao.html'
    success_message = 'Anotação excluída.'
