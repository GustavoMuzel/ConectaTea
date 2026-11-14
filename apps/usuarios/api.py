"""API REST (DRF + JWT). Documentação OpenAPI em /api/docs/ (RNF12).

As regras são as mesmas das telas: o aluno só vê o que foi distribuído a ele, o profissional só vê os alunos
que acompanha, e o login tem o mesmo limite de tentativas (RNF04).
"""

from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import permissions, serializers
from rest_framework.exceptions import AuthenticationFailed, Throttled
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.acompanhamento.models import Atribuicao, RegistroEvolucao
from apps.atividades.models import Atividade

from .services import limites


# Login com limite de tentativas ------------------------------------------------------------------------------

class LoginComLimiteSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get(self.username_field, '')
        if limites.login_bloqueado(email):
            raise Throttled(detail='Muitas tentativas erradas com este e-mail. Espere 15 minutos.')
        try:
            dados = super().validate(attrs)
        except AuthenticationFailed:
            limites.registrar_falha_login(email)
            raise
        limites.limpar_falhas_login(email)
        return dados


@extend_schema(tags=['Autenticação'], summary='Entrar e receber os tokens JWT (acesso e renovação)')
class LoginApiView(TokenObtainPairView):
    serializer_class = LoginComLimiteSerializer


# Permissões ------------------------------------------------------------------------------------------------

class EhAlunoVinculado(permissions.BasePermission):
    message = 'Disponível só para aluno com profissional vinculado.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_aluno and not user.is_aluno_sem_vinculo)


class EhProfissionalAprovado(permissions.BasePermission):
    message = 'Disponível só para profissional aprovado.'

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_profissional)


# Atividades do aluno ---------------------------------------------------------------------------------------

class AtividadeDoAlunoSerializer(serializers.ModelSerializer):
    prazo = serializers.DateField(allow_null=True, read_only=True)
    concluida = serializers.BooleanField(read_only=True)
    tipo_material = serializers.CharField(read_only=True)

    class Meta:
        model = Atividade
        fields = ['id', 'title', 'description', 'category', 'tipo_material', 'prazo', 'concluida']


@extend_schema(tags=['Aluno'], summary='Atividades distribuídas ao aluno logado, com prazo e situação')
class AtividadesDoAlunoApiView(ListAPIView):
    serializer_class = AtividadeDoAlunoSerializer
    permission_classes = [EhAlunoVinculado]

    def get_queryset(self):
        from django.db.models import Exists, OuterRef, Subquery

        from apps.acompanhamento.views import atividades_do_aluno

        aluno = self.request.user.aluno
        prazo = Atribuicao.objects.filter(aluno=aluno, atividade=OuterRef('pk')).values('prazo')[:1]
        concluida = RegistroEvolucao.objects.filter(aluno=aluno, atividade=OuterRef('pk'),
                                                    status=RegistroEvolucao.Status.CONCLUIDA)
        return (atividades_do_aluno(aluno).filter(arquivada=False)
                .annotate(prazo=Subquery(prazo), concluida=Exists(concluida)).order_by('created_at'))


# Alunos do profissional ------------------------------------------------------------------------------------

class AlunoAcompanhadoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField(source='user.name')
    papel = serializers.SerializerMethodField(help_text='"responsavel" (dono da sala) ou "equipe"')
    atividades_concluidas = serializers.IntegerField()
    ultima_conclusao = serializers.DateTimeField(allow_null=True)

    def get_papel(self, aluno) -> str:
        return 'responsavel' if aluno.profissional_id == self.context['profissional'].pk else 'equipe'


@extend_schema(tags=['Profissional'], summary='Alunos que o profissional acompanha (como responsável ou na equipe)')
class AlunosDoProfissionalApiView(ListAPIView):
    serializer_class = AlunoAcompanhadoSerializer
    permission_classes = [EhProfissionalAprovado]

    def get_serializer_context(self):
        return super().get_serializer_context() | {'profissional': self.request.user.profissional}

    def get_queryset(self):
        from django.db.models import Count, Max, Q

        from apps.salas.models import alunos_do_profissional

        concluida = Q(registros_evolucao__status=RegistroEvolucao.Status.CONCLUIDA)
        return (alunos_do_profissional(self.request.user.profissional).select_related('user')
                .annotate(atividades_concluidas=Count('registros_evolucao', filter=concluida, distinct=True),
                          ultima_conclusao=Max('registros_evolucao__data_realizacao', filter=concluida))
                .order_by('user__name'))


@extend_schema(
    tags=['Sistema'], summary='Situação da API (para monitoramento)', auth=[],
    responses=inline_serializer('Saude', {'status': serializers.CharField(), 'horario': serializers.DateTimeField()}),
)
class SaudeApiView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'status': 'ok', 'horario': timezone.now()})
