from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import FileResponse, Http404
from django.db.models import F, Window
from django.db.models.functions import RowNumber
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from apps.acompanhamento.models import LogAcesso, RegistroEvolucao
from apps.usuarios.mixins import ProfissionalRequiredMixin
from apps.salas.models import SolicitacaoVinculo, alunos_do_profissional
from apps.usuarios.models import Aluno

from .forms import AtividadeForm, ObservacaoForm
from .models import Atividade


class PainelView(ProfissionalRequiredMixin, CreateView):
    """Lista as atividades do profissional logado e cadastra novas na mesma tela."""

    form_class = AtividadeForm
    template_name = 'atividades/painel.html'
    success_url = reverse_lazy('painel')

    def get_context_data(self, **kwargs):
        # Só a biblioteca: atividades exclusivas de um aluno ficam na sala dele.
        kwargs['atividades'] = self.request.user.profissional.atividades.filter(aluno__isnull=True).order_by(
            '-created_at')
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
        return self.request.user.profissional.alunos.select_related('user', 'sala').order_by('user__name')

    def get_context_data(self, **kwargs):
        profissional = self.request.user.profissional
        kwargs['da_equipe'] = (alunos_do_profissional(profissional).exclude(profissional=profissional)
                               .select_related('user', 'sala__dono__user').order_by('user__name'))
        return super().get_context_data(**kwargs)


class AlunosSemVinculoView(ProfissionalRequiredMixin, ListView):
    """Alunos ativos que ainda não têm profissional: o profissional aprovado escolhe quais são seus."""

    template_name = 'atividades/vincular_alunos.html'
    context_object_name = 'alunos'

    def get_queryset(self):
        return (Aluno.objects.filter(profissional__isnull=True, user__is_active=True)
                .select_related('user').order_by('user__name', 'pk'))

    def get_context_data(self, **kwargs):
        kwargs['ja_pedidos'] = set(SolicitacaoVinculo.objects.filter(
            profissional=self.request.user.profissional, status=SolicitacaoVinculo.Status.PENDENTE,
        ).values_list('aluno_id', flat=True))
        return super().get_context_data(**kwargs)


class EvolucaoAlunoView(ProfissionalRequiredMixin, DetailView):
    """Histórico de atividades concluídas do aluno, com anotações do profissional."""

    http_method_names = ['get']
    template_name = 'atividades/evolucao_aluno.html'
    context_object_name = 'aluno'

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        # Auditoria (RF10/RNF05): só chega aqui se o aluno é do profissional; 403/404 não geram log.
        LogAcesso.objects.create(user=request.user, aluno=self.object, acao='Visualizou evolução')
        return response

    def get_queryset(self):
        # Alunos do próprio profissional ou de sala em que ele foi aprovado; os outros dão 404.
        return alunos_do_profissional(self.request.user.profissional).select_related('user')

    def get_context_data(self, **kwargs):
        # "tentativa" numera as conclusões de cada atividade, da primeira para a última.
        registros = RegistroEvolucao.objects.filter(
            aluno=self.object, status=RegistroEvolucao.Status.CONCLUIDA,
        ).annotate(
            tentativa=Window(RowNumber(), partition_by=F('atividade'), order_by=['data_realizacao', 'pk']),
        ).select_related('atividade').order_by('-data_realizacao', '-pk')
        kwargs['registros'] = [(registro, ObservacaoForm(instance=registro)) for registro in registros]
        kwargs['eh_dono'] = self.object.profissional_id == self.request.user.profissional.pk
        return super().get_context_data(**kwargs)


class SalvarObservacaoView(ProfissionalRequiredMixin, View):
    http_method_names = ['post']

    def post(self, request, aluno_pk, pk):
        # Dono e membros aprovados da sala corrigem (escrevem observações nas tentativas do aluno).
        aluno = get_object_or_404(alunos_do_profissional(request.user.profissional), pk=aluno_pk)
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


SESSAO_MATERIAIS_ABERTOS = 'atividades_abertas'


class MaterialAtividadeView(LoginRequiredMixin, View):
    """Entrega o PDF ou leva ao Google Forms, só para quem pode ver a atividade. O PDF nunca fica público.

    Quando é o aluno que abre, a sessão guarda isso: a conclusão só é aceita depois de abrir o material.
    """

    http_method_names = ['get']

    def get(self, request, pk):
        from apps.acompanhamento.views import atividades_do_aluno  # import local: evita ciclo entre apps

        user = request.user
        if user.is_aluno and not user.is_aluno_sem_vinculo:
            atividade = get_object_or_404(atividades_do_aluno(user.aluno), pk=pk)
            abertas = set(request.session.get(SESSAO_MATERIAIS_ABERTOS, []))
            abertas.add(atividade.pk)
            request.session[SESSAO_MATERIAIS_ABERTOS] = sorted(abertas)
        elif user.is_profissional:
            atividade = get_object_or_404(Atividade, pk=pk)
            profissional = user.profissional
            pode = (atividade.profissional_id == profissional.pk or atividade.autor_id == profissional.pk
                    or (atividade.aluno_id and alunos_do_profissional(profissional).filter(
                        pk=atividade.aluno_id).exists()))
            if not pode:
                raise Http404
        else:
            raise Http404
        if atividade.tipo_material == Atividade.TipoMaterial.FORMULARIO and atividade.link_formulario:
            return redirect(atividade.link_formulario)
        if atividade.tipo_material == Atividade.TipoMaterial.PDF and atividade.arquivo_pdf:
            nome = f'{atividade.title[:60]}.pdf'
            return FileResponse(atividade.arquivo_pdf.open('rb'), content_type='application/pdf', filename=nome)
        raise Http404
