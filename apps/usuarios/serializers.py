from rest_framework import serializers

from .models import Aluno, Profissional, User


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'password', 'role', 'is_active', 'created_at', 'last_login']
        read_only_fields = ['is_active', 'created_at', 'last_login']

    def create(self, validated_data):
        # create_user grava a senha com hash; ModelSerializer.create a salvaria em texto puro.
        return User.objects.create_user(**validated_data)


class ProfissionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profissional
        fields = ['id', 'user', 'especialidade', 'registro_profissional']


class AlunoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aluno
        fields = ['id', 'user', 'profissional', 'birth_date', 'guardian_name', 'guardian_phone', 'guardian_email']


class UserMeSerializer(UserSerializer):
    """Usuário logado com o perfil aninhado; o perfil que ele não tem vem como null."""

    aluno = AlunoSerializer(read_only=True)
    profissional = ProfissionalSerializer(read_only=True)

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ['aluno', 'profissional']
