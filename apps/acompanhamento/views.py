from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import DetailView, FormView, ListView

from apps.atividades.models import Atividade
from apps.usuarios.mixins import AlunoRequiredMixin, ProfissionalRequiredMixin

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
        _, criado = RegistroEvolucao.objects.get_or_create(
            aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.CONCLUIDA,
        )
        if criado:
            messages.success(request, f'Atividade concluída: {atividade.title}.')
        else:
            messages.info(request, f'Esta atividade já estava concluída: {atividade.title}.')
        return redirect('aluno_atividades')


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
