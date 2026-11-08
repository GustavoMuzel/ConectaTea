from django.urls import path

from . import views

urlpatterns = [
    path('', views.SalasView.as_view(), name='salas'),
    path('entrar/', views.EntrarSalaView.as_view(), name='entrar_sala'),
    path('<int:pk>/', views.SalaView.as_view(), name='sala'),
    path('<int:pk>/senha/', views.TrocarSenhaSalaView.as_view(), name='trocar_senha_sala'),
    path('<int:pk>/atividades/', views.ProporAtividadeView.as_view(), name='propor_atividade'),
    path('<int:pk>/atividades/<int:atividade_pk>/<str:decisao>/', views.AnalisarAtividadeView.as_view(),
         name='analisar_atividade'),
    path('<int:pk>/membros/<int:membro_pk>/<str:decisao>/', views.DecidirMembroView.as_view(), name='decidir_membro'),
    path('<int:pk>/videochamada/', views.VideochamadaView.as_view(), name='videochamada'),
    path('vinculo/aluno/<int:pk>/pedir/', views.EnviarPedidoVinculoView.as_view(), name='pedir_vinculo'),
    path('vinculo/<int:pk>/<str:resposta>/', views.ResponderPedidoVinculoView.as_view(), name='responder_vinculo'),
    path('minha-equipe/', views.MinhaEquipeView.as_view(), name='minha_equipe'),
]
