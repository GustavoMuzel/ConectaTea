from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.usuarios.views import UserMeView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/me/', UserMeView.as_view(), name='auth_me'),
    path('painel/', include('apps.atividades.urls')),
    path('aluno/', include('apps.acompanhamento.urls')),
    path('', include('apps.usuarios.urls')),
]
