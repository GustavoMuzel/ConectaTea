from django.urls import path

from .views import AlunosDoProfissionalView, EvolucaoAlunoView, PainelView, SalvarObservacaoView

urlpatterns = [
    path('', PainelView.as_view(), name='painel'),
    path('alunos/', AlunosDoProfissionalView.as_view(), name='alunos_profissional'),
    path('alunos/<int:pk>/', EvolucaoAlunoView.as_view(), name='evolucao_aluno'),
    path('alunos/<int:aluno_pk>/registros/<int:pk>/observacoes/', SalvarObservacaoView.as_view(),
         name='salvar_observacao'),
]
