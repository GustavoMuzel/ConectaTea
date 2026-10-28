from django.urls import path

from . import views

urlpatterns = [
    path('atividades/', views.AtividadesAlunoView.as_view(), name='aluno_atividades'),
    path('atividades/<int:pk>/confirmar/', views.ConfirmarConclusaoView.as_view(), name='confirmar_conclusao'),
    path('atividades/<int:pk>/concluir/', views.ConcluirAtividadeView.as_view(), name='concluir_atividade'),
    path('historico/', views.HistoricoAlunoView.as_view(), name='historico_aluno'),
    path('atividades/<int:pk>/refazer/', views.RefazerAtividadeView.as_view(), name='refazer_atividade'),
    path('anotacoes/', views.AnotacoesAlunoView.as_view(), name='anotacoes_aluno'),
    path('anotacoes/<int:pk>/editar/', views.AnotacaoEditarView.as_view(), name='editar_anotacao'),
    path('anotacoes/<int:pk>/excluir/', views.AnotacaoExcluirView.as_view(), name='excluir_anotacao'),
    path('dashboard-profissional/', views.DashboardProfissionalView.as_view(), name='dashboard_profissional'),
    path('distribuir-atividade/<int:pk>/', views.DistribuirAtividadeView.as_view(), name='distribuir_atividade'),
]
