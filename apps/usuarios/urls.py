from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('entrar/', views.EntrarView.as_view(), name='login'),
    path('sair/', LogoutView.as_view(), name='logout'),
    path('cadastro/', views.CadastroView.as_view(), name='cadastro'),
    path('termos/', views.TermosView.as_view(), name='termos'),
    path('privacidade/', views.PrivacidadeView.as_view(), name='privacidade'),
    path('preferencias/', views.PreferenciasView.as_view(), name='preferencias'),
    path('painel-gestao/', views.AdminDashboardView.as_view(), name='painel_gestao'),
    path('painel-gestao/profissional/<int:pk>/aprovar/', views.AprovarProfissionalGestaoView.as_view(),
         name='aprovar_profissional_gestao'),
]
