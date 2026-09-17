from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.atividades.models import Atividade
from apps.usuarios.mixins import AlunoRequiredMixin

from .models import RegistroEvolucao


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
