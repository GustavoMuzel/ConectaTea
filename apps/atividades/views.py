from django.contrib import messages
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.acompanhamento.models import RegistroEvolucao
from apps.usuarios.mixins import ProfissionalRequiredMixin

from .forms import AtividadeForm, ObservacaoForm


class PainelView(ProfissionalRequiredMixin, CreateView):
    """Lista as atividades do profissional logado e cadastra novas na mesma tela."""

    form_class = AtividadeForm
    template_name = 'atividades/painel.html'
    success_url = reverse_lazy('painel')

    def get_context_data(self, **kwargs):
        kwargs['atividades'] = self.request.user.profissional.atividades.order_by('-created_at')
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        # Dono vem da sessão, nunca do POST.
        form.instance.profissional = self.request.user.profissional
        messages.success(self.request, f'Atividade "{form.instance.title}" cadastrada.')
        return super().form_valid(form)


class AtividadeUpdateView(ProfissionalRequiredMixin, UpdateView):
    form_class = AtividadeForm
    template_name = 'atividades/editar.html'
    success_url = reverse_lazy('painel')

    def get_queryset(self):
        # Só atividades do próprio profissional: id de outra atividade dá 404.
        return self.request.user.profissional.atividades.all()

    def form_valid(self, form):
        messages.success(self.request, f'Atividade "{form.instance.title}" atualizada.')
        return super().form_valid(form)


class ArquivarAtividadeView(ProfissionalRequiredMixin, View):
    """Arquivada some da distribuição (RF07), mas continua no painel e no histórico dos alunos."""

    http_method_names = ['post']

    def post(self, request, pk):
        atividade = get_object_or_404(request.user.profissional.atividades, pk=pk)
        atividade.arquivada = True
        atividade.save(update_fields=['arquivada'])
        messages.success(request, f'Atividade "{atividade.title}" arquivada.')
        return redirect('painel')


class AlunosDoProfissionalView(ProfissionalRequiredMixin, ListView):
    """Alunos vinculados ao profissional logado."""

    template_name = 'atividades/alunos.html'
    context_object_name = 'alunos'

    def get_queryset(self):
        return self.request.user.profissional.alunos.select_related('user').order_by('user__name')


class EvolucaoAlunoView(ProfissionalRequiredMixin, DetailView):
    """Histórico de atividades concluídas do aluno, com anotações do profissional."""

    http_method_names = ['get']
    template_name = 'atividades/evolucao_aluno.html'
    context_object_name = 'aluno'

    def get_queryset(self):
        # Só alunos do próprio profissional: id de aluno de outro profissional dá 404.
        return self.request.user.profissional.alunos.select_related('user')

    def get_context_data(self, **kwargs):
        # "tentativa" numera as conclusões de cada atividade, da primeira para a última.
        registros = RegistroEvolucao.objects.filter(
            aluno=self.object, status=RegistroEvolucao.Status.CONCLUIDA,
        ).annotate(
            tentativa=Window(RowNumber(), partition_by=F('atividade'), order_by=['data_realizacao', 'pk']),
        ).select_related('atividade').order_by('-data_realizacao', '-pk')
        kwargs['registros'] = [(registro, ObservacaoForm(instance=registro)) for registro in registros]
        return super().get_context_data(**kwargs)


class SalvarObservacaoView(ProfissionalRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, aluno_pk, pk):
        aluno = get_object_or_404(request.user.profissional.alunos, pk=aluno_pk)
        registro = get_object_or_404(
            RegistroEvolucao.objects.filter(status=RegistroEvolucao.Status.CONCLUIDA), pk=pk, aluno=aluno,
        )
        form = ObservacaoForm(request.POST, instance=registro)
        if form.is_valid():
            form.save()
            messages.success(request, 'Anotação salva.')
        else:
            messages.error(request, 'Não foi possível salvar a anotação.')
        return redirect('evolucao_aluno', pk=aluno_pk)
