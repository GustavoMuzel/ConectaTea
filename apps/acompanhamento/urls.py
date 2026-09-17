from django.urls import path

from . import views

urlpatterns = [
    path('atividades/', views.AtividadesAlunoView.as_view(), name='aluno_atividades'),
    path('atividades/<int:pk>/confirmar/', views.ConfirmarConclusaoView.as_view(), name='confirmar_conclusao'),
    path('atividades/<int:pk>/concluir/', views.ConcluirAtividadeView.as_view(), name='concluir_atividade'),
]
