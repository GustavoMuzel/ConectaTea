from django.urls import path

from .views import (
    AlunosDoProfissionalView, ArquivarAtividadeView, AtividadeUpdateView, EvolucaoAlunoView, PainelView,
    SalvarObservacaoView,
)

urlpatterns = [
    path('', PainelView.as_view(), name='painel'),
    path('atividades/<int:pk>/editar/', AtividadeUpdateView.as_view(), name='editar_atividade'),
    path('atividades/<int:pk>/arquivar/', ArquivarAtividadeView.as_view(), name='arquivar_atividade'),
    path('alunos/', AlunosDoProfissionalView.as_view(), name='alunos_profissional'),
    path('alunos/<int:pk>/', EvolucaoAlunoView.as_view(), name='evolucao_aluno'),
    path('alunos/<int:aluno_pk>/registros/<int:pk>/observacoes/', SalvarObservacaoView.as_view(),
         name='salvar_observacao'),
]
