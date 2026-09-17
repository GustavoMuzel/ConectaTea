import datetime

import pytest
from rest_framework.test import APIClient

from .models import Aluno, Profissional, User
from .serializers import UserSerializer

SENHA = 'senha-forte-123'


@pytest.fixture
def client():
    User.objects.create_user('prof@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    return APIClient()


@pytest.mark.django_db
def test_login_retorna_tokens_e_refresh_funciona(client):
    resp = client.post('/api/auth/login/', {'email': 'prof@ex.com', 'password': SENHA}, format='json')
    assert resp.status_code == 200
    assert {'access', 'refresh'} <= resp.data.keys()

    resp = client.post('/api/auth/refresh/', {'refresh': resp.data['refresh']}, format='json')
    assert resp.status_code == 200
    assert 'access' in resp.data


@pytest.mark.django_db
def test_login_com_senha_errada_retorna_401(client):
    resp = client.post('/api/auth/login/', {'email': 'prof@ex.com', 'password': 'errada'}, format='json')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_de_usuario_inativo_retorna_401(client):
    User.objects.filter(email='prof@ex.com').update(is_active=False)
    resp = client.post('/api/auth/login/', {'email': 'prof@ex.com', 'password': SENHA}, format='json')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_user_serializer_grava_senha_com_hash_e_nao_expoe():
    s = UserSerializer(data={'name': 'Aluno', 'email': 'a@ex.com', 'password': SENHA, 'role': 'aluno'})
    assert s.is_valid(), s.errors
    user = s.save()
    assert user.password != SENHA and user.check_password(SENHA)
    assert 'password' not in UserSerializer(user).data


def _get_me(client, email):
    login = client.post('/api/auth/login/', {'email': email, 'password': SENHA}, format='json')
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    return client.get('/api/auth/me/')


@pytest.mark.django_db
def test_me_sem_token_retorna_401():
    assert APIClient().get('/api/auth/me/').status_code == 401


@pytest.mark.django_db
def test_me_de_profissional(client):
    prof = Profissional.objects.create(
        user=User.objects.get(email='prof@ex.com'), especialidade='Psicologia', registro_profissional='CRP 06/1',
    )
    resp = _get_me(client, 'prof@ex.com')

    assert resp.status_code == 200
    assert resp.data['email'] == 'prof@ex.com'
    assert resp.data['role'] == 'profissional'
    assert 'password' not in resp.data
    assert resp.data['aluno'] is None
    assert resp.data['profissional'] == {
        'id': prof.id, 'user': prof.user_id, 'especialidade': 'Psicologia', 'registro_profissional': 'CRP 06/1',
    }


@pytest.mark.django_db
def test_me_de_aluno(client):
    prof = Profissional.objects.create(user=User.objects.get(email='prof@ex.com'), especialidade='Psicologia')
    aluno_user = User.objects.create_user('aluno@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    aluno = Aluno.objects.create(
        user=aluno_user, profissional=prof, birth_date=datetime.date(2011, 5, 1),
        guardian_name='Resp', guardian_phone='11999999999', guardian_email='resp@ex.com',
    )
    resp = _get_me(client, 'aluno@ex.com')

    assert resp.status_code == 200
    assert resp.data['role'] == 'aluno'
    assert resp.data['profissional'] is None
    assert resp.data['aluno']['id'] == aluno.id
    assert resp.data['aluno']['profissional'] == prof.id
    assert resp.data['aluno']['birth_date'] == '2011-05-01'


@pytest.mark.django_db
def test_me_de_usuario_sem_perfil(client):
    User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    resp = _get_me(client, 'admin@ex.com')

    assert resp.status_code == 200
    assert resp.data['role'] == 'admin'
    assert resp.data['aluno'] is None and resp.data['profissional'] is None
