from collections import Counter

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Exists, Max, OuterRef
from django.db.models.functions import TruncWeek
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import DetailView, FormView, ListView, TemplateView

from apps.atividades.models import Atividade
from apps.usuarios.mixins import AlunoRequiredMixin, ProfissionalRequiredMixin
from apps.usuarios.models import Aluno

from .forms import DistribuicaoAtividadeForm
from .models import Atribuicao, RegistroEvolucao


def atividades_do_aluno(aluno):
    # Profissional revogado ou desativado deixa de entregar atividades aos alunos dele.
    return Atividade.objects.filter(
        profissional_id=aluno.profissional_id,
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


class ConfirmarConclusaoView(AlunoRequiredMixin, DetailView):
    """Tela intermediária: evita que um toque acidental na lista conclua a atividade direto."""

    http_method_names = ['get']
    template_name = 'acompanhamento/confirmar_conclusao.html'
    context_object_name = 'atividade'

    def get_queryset(self):
        return atividades_do_aluno(self.request.user.aluno)


class ConcluirAtividadeView(AlunoRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, pk):
        aluno = request.user.aluno
        # Só atividades do próprio profissional: id de outra atividade dá 404.
        atividade = get_object_or_404(atividades_do_aluno(aluno), pk=pk)
        with transaction.atomic():
            # Trava o aluno: dois cliques seguidos não geram duas conclusões.
            Aluno.objects.select_for_update().get(pk=aluno.pk)
            registros = RegistroEvolucao.objects.filter(aluno=aluno, atividade=atividade)
            refazendo = registros.filter(status=RegistroEvolucao.Status.EM_ANDAMENTO).first()
            criado = True
            if refazendo:  # tentativa aberta por "Fazer de novo": é ela que termina agora
                refazendo.status = RegistroEvolucao.Status.CONCLUIDA
                refazendo.data_realizacao = timezone.now()
                refazendo.save(update_fields=['status', 'data_realizacao'])
            elif registros.filter(status=RegistroEvolucao.Status.CONCLUIDA).exists():
                criado = False
            else:
                RegistroEvolucao.objects.create(
                    aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.CONCLUIDA,
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
        atividade = get_object_or_404(profissional.atividades.filter(arquivada=False), pk=self.kwargs['pk'])
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
