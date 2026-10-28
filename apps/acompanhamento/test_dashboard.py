import datetime

import pytest
from django.urls import reverse

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atribuicao, RegistroEvolucao

SENHA = 'Senha-forte-123'
URL = reverse('dashboard_profissional')


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _aluno(email, prof, nome=None):
    user = User.objects.create_user(email, nome or email, SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


def _atividade(prof, titulo):
    return Atividade.objects.create(profissional=prof, title=titulo, category='social')


def _concluir(aluno, atividade):
    return RegistroEvolucao.objects.create(aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.CONCLUIDA)


@pytest.fixture
def cenario(client):
    a, b = _prof('a@ex.com'), _prof('b@ex.com')
    ana, ari, bia = _aluno('ana@ex.com', a), _aluno('ari@ex.com', a), _aluno('bia@ex.com', b)
    ativ_a1, ativ_a2, ativ_a3 = _atividade(a, 'A1'), _atividade(a, 'A2'), _atividade(a, 'A3')
    ativ_b1, ativ_b2 = _atividade(b, 'B1'), _atividade(b, 'B2')
    _concluir(ana, ativ_a1)
    _concluir(ana, ativ_a2)
    _concluir(ari, ativ_a1)
    _concluir(bia, ativ_b1)
    # Registro não concluído não conta nos gráficos nem nas concluídas.
    RegistroEvolucao.objects.create(aluno=ari, atividade=ativ_a2, status=RegistroEvolucao.Status.EM_ANDAMENTO)
    Atribuicao.objects.create(atividade=ativ_a3, aluno=ana, profissional=a)  # a única pendente de verdade
    Atribuicao.objects.create(atividade=ativ_a1, aluno=ari, profissional=a)  # pendente, mas ari já concluiu
    Atribuicao.objects.create(atividade=ativ_a2, aluno=ari, profissional=a, status=Atribuicao.Status.CONCLUIDA)
    Atribuicao.objects.create(atividade=ativ_b2, aluno=bia, profissional=b)
    client.force_login(a.user)
    return {'a': a, 'b': b, 'ana': ana, 'ativ_a3': ativ_a3}


@pytest.mark.django_db
def test_dashboard_exige_profissional(client, cenario):
    client.logout()
    resp = client.get(URL)
    assert resp.status_code == 302 and resp.url.startswith(reverse('login'))
    client.force_login(Aluno.objects.get(user__email='ana@ex.com').user)
    assert client.get(URL).status_code == 403


@pytest.mark.django_db
def test_dashboard_isolamento(client, cenario):
    resp = client.get(URL)
    assert resp.status_code == 200
    assert sorted(resp.context['dados']['alunos']['rotulos']) == ['ana@ex.com', 'ari@ex.com']
    assert 'bia@ex.com' not in resp.content.decode()
    client.force_login(cenario['b'].user)
    ctx = client.get(URL).context
    assert (ctx['total_alunos'], ctx['total_pendentes'], ctx['total_concluidas']) == (1, 1, 1)
    assert ctx['dados']['alunos']['rotulos'] == ['bia@ex.com']


@pytest.mark.django_db
def test_dashboard_contexto_numeros(client, cenario):
    ctx = client.get(URL).context
    assert ctx['total_alunos'] == 2
    assert ctx['total_pendentes'] == 1  # fora: atribuição CONCLUIDA e a de quem já concluiu
    assert ctx['total_concluidas'] == 3
    assert ctx['dados']['alunos'] == {'rotulos': ['ana@ex.com', 'ari@ex.com'], 'valores': [2, 1]}
    assert sum(ctx['dados']['semanas']['valores']) == 3
    # Homônimos: o rótulo ganha o id do aluno para as barras não ficarem iguais.
    outra_ana = _aluno('outra@ex.com', cenario['a'], nome='ana@ex.com')
    _concluir(outra_ana, cenario['ativ_a3'])
    rotulos = client.get(URL).context['dados']['alunos']['rotulos']
    assert set(rotulos) == {f"ana@ex.com (#{cenario['ana'].pk})", f'ana@ex.com (#{outra_ana.pk})', 'ari@ex.com'}
