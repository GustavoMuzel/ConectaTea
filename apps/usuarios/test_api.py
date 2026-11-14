"""API REST: documentação OpenAPI (RNF12), atividades do aluno e alunos do profissional."""
import datetime

import pytest
from django.urls import reverse

from apps.acompanhamento.models import Atribuicao, RegistroEvolucao
from apps.atividades.models import Atividade
from apps.salas.models import MembroSala, Sala

from .models import Aluno, Profissional, User

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'


def _prof(email, aprovado=True):
    user = User.objects.create_user(email, email.split('@')[0].title(), SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=aprovado)


def _aluno(email, prof):
    user = User.objects.create_user(email, email.split('@')[0].title(), SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


def _token(client, email):
    resp = client.post(reverse('token_obtain_pair'), {'email': email, 'password': SENHA})
    return {'HTTP_AUTHORIZATION': f"Bearer {resp.json()['access']}"}


@pytest.mark.django_db
def test_documentacao_openapi_disponivel(client):
    assert client.get(reverse('api_docs')).status_code == 200
    schema = client.get(reverse('api_schema')).content.decode()
    for rota in ('/api/auth/login/', '/api/aluno/atividades/', '/api/profissional/alunos/'):
        assert rota in schema


@pytest.mark.django_db
def test_saude_e_publica(client):
    assert client.get(reverse('api_saude')).json()['status'] == 'ok'


@pytest.mark.django_db
def test_aluno_recebe_so_as_atividades_distribuidas_a_ele(client):
    prof = _prof('prof@ex.com')
    aluno, colega = _aluno('a@ex.com', prof), _aluno('b@ex.com', prof)
    so_do_a = Atividade.objects.create(profissional=prof, title='Só do A', category='x')
    Atribuicao.objects.create(atividade=so_do_a, aluno=aluno, profissional=prof, prazo=datetime.date(2030, 1, 2))
    Atividade.objects.create(profissional=prof, title='Não enviada', category='x')

    dados = client.get(reverse('api_atividades_aluno'), **_token(client, 'a@ex.com')).json()
    assert [(d['title'], d['prazo'], d['concluida']) for d in dados] == [('Só do A', '2030-01-02', False)]
    assert client.get(reverse('api_atividades_aluno'), **_token(client, 'b@ex.com')).json() == []
    RegistroEvolucao.objects.create(aluno=aluno, atividade=so_do_a, status='concluida')
    assert client.get(reverse('api_atividades_aluno'), **_token(client, 'a@ex.com')).json()[0]['concluida'] is True
    assert colega.pk  # o colega existe e continua sem nada


@pytest.mark.django_db
def test_profissional_ve_alunos_proprios_e_da_equipe(client):
    dono, fono, outro = _prof('dono@ex.com'), _prof('fono@ex.com'), _prof('outro@ex.com')
    aluno = _aluno('a@ex.com', dono)
    sala = Sala.objects.create(aluno=aluno, dono=dono)
    MembroSala.objects.create(sala=sala, profissional=fono, status=MembroSala.Status.APROVADO)
    _aluno('alheio@ex.com', outro)

    dados = client.get(reverse('api_alunos_profissional'), **_token(client, 'fono@ex.com')).json()
    assert [(d['nome'], d['papel']) for d in dados] == [('A', 'equipe')]
    dados = client.get(reverse('api_alunos_profissional'), **_token(client, 'dono@ex.com')).json()
    assert [(d['nome'], d['papel']) for d in dados] == [('A', 'responsavel')]


@pytest.mark.django_db
def test_permissoes_da_api(client):
    prof = _prof('prof@ex.com')
    _aluno('a@ex.com', prof)
    _prof('pend@ex.com', aprovado=False)
    assert client.get(reverse('api_atividades_aluno')).status_code == 401  # sem token
    assert client.get(reverse('api_atividades_aluno'), **_token(client, 'prof@ex.com')).status_code == 403
    assert client.get(reverse('api_alunos_profissional'), **_token(client, 'a@ex.com')).status_code == 403
    assert client.get(reverse('api_alunos_profissional'), **_token(client, 'pend@ex.com')).status_code == 403
