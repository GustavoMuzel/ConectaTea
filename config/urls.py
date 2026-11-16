from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.usuarios.api import AlunosDoProfissionalApiView, AtividadesDoAlunoApiView, LoginApiView, SaudeApiView

from apps.usuarios.views import UserMeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', LoginApiView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/me/', UserMeView.as_view(), name='auth_me'),
    path('api/aluno/atividades/', AtividadesDoAlunoApiView.as_view(), name='api_atividades_aluno'),
    path('api/profissional/alunos/', AlunosDoProfissionalApiView.as_view(), name='api_alunos_profissional'),
    path('api/saude/', SaudeApiView.as_view(), name='api_saude'),
    path('api/schema/', SpectacularAPIView.as_view(), name='api_schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='api_schema'), name='api_docs'),
    path('painel/', include('apps.atividades.urls')),
    path('aluno/', include('apps.acompanhamento.urls')),
    path('salas/', include('apps.salas.urls')),
    path('', include('apps.usuarios.urls')),
]
