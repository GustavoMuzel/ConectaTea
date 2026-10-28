from django.urls import path

from . import views

urlpatterns = [
    path('atividades/', views.AtividadesAlunoView.as_view(), name='aluno_atividades'),
    path('atividades/<int:pk>/confirmar/', views.ConfirmarConclusaoView.as_view(), name='confirmar_conclusao'),
    path('atividades/<int:pk>/concluir/', views.ConcluirAtividadeView.as_view(), name='concluir_atividade'),
    path('historico/', views.HistoricoAlunoView.as_view(), name='historico_aluno'),
    path('atividades/<int:pk>/refazer/', views.RefazerAtividadeView.as_view(), name='refazer_atividade'),
    path('dashboard-profissional/', views.DashboardProfissionalView.as_view(), name='dashboard_profissional'),
    path('distribuir-atividade/<int:pk>/', views.DistribuirAtividadeView.as_view(), name='distribuir_atividade'),
]
