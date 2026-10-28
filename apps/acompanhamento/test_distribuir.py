import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .forms import DistribuicaoAtividadeForm
from .models import Atribuicao

SENHA = 'Senha-forte-123'


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _aluno(email, prof):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


@pytest.fixture
def cenario(client):
    prof = _prof('prof@ex.com')
    client.force_login(prof.user)
    return {
        'prof': prof,
        'atividade': Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social'),
        'alunos': [_aluno(f'aluno{i}@ex.com', prof) for i in range(3)],
        'alheio': _aluno('alheio@ex.com', _prof('outro@ex.com')),
    }


def _dados(cenario, alunos, **extra):
    return {'atividade': cenario['atividade'].pk, 'alunos': [a.pk for a in alunos], **extra}


def _url(cenario):
    return reverse('distribuir_atividade', args=[cenario['atividade'].pk])


@pytest.mark.django_db
def test_distribuir_cria_atribuicoes_pendentes(client, cenario):  # CA01
    resp = client.post(_url(cenario), _dados(cenario, cenario['alunos'][:2]))
    assert resp.status_code == 302 and resp.url == reverse('painel')
    atribuicoes = Atribuicao.objects.all()
    assert {a.aluno for a in atribuicoes} == set(cenario['alunos'][:2])
    assert all(a.status == Atribuicao.Status.PENDENTE and a.profissional == cenario['prof'] for a in atribuicoes)


@pytest.mark.django_db
def test_distribuir_recusa_aluno_de_outro_profissional(client, cenario):  # CA02
    form = DistribuicaoAtividadeForm(_dados(cenario, [cenario['alheio']]), profissional=cenario['prof'])
    assert not form.is_valid() and 'alunos' in form.errors
    resp = client.post(_url(cenario), _dados(cenario, [cenario['alheio']]))
    assert resp.status_code == 200 and not Atribuicao.objects.exists()


@pytest.mark.django_db
def test_distribuir_recusa_atividade_arquivada(client, cenario):  # CA03
    Atividade.objects.filter(pk=cenario['atividade'].pk).update(arquivada=True)
    form = DistribuicaoAtividadeForm(_dados(cenario, cenario['alunos'][:1]), profissional=cenario['prof'])
    assert not form.is_valid() and 'atividade' in form.errors
    resp = client.post(_url(cenario), _dados(cenario, cenario['alunos'][:1]))
    assert resp.status_code == 404 and not Atribuicao.objects.exists()


@pytest.mark.django_db
def test_distribuir_recusa_prazo_no_passado(client, cenario):  # CA04
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    form = DistribuicaoAtividadeForm(_dados(cenario, cenario['alunos'][:1], prazo=ontem), profissional=cenario['prof'])
    assert not form.is_valid() and 'prazo' in form.errors
    hoje = timezone.localdate()
    form = DistribuicaoAtividadeForm(_dados(cenario, cenario['alunos'][:1], prazo=hoje), profissional=cenario['prof'])
    assert form.is_valid()


@pytest.mark.django_db
def test_distribuir_exige_autenticacao_profissional(client, cenario):
    url = _url(cenario)
    client.logout()
    resp = client.get(url)
    assert resp.status_code == 302 and resp.url.startswith(reverse('login'))
    client.force_login(cenario['alunos'][0].user)
    assert client.get(url).status_code == 403
    assert client.post(url, _dados(cenario, cenario['alunos'][:1])).status_code == 403
    client.force_login(cenario['alheio'].profissional.user)
    assert client.get(url).status_code == 404  # atividade de outro profissional
    assert not Atribuicao.objects.exists()


@pytest.mark.django_db
def test_distribuir_unicidade(client, cenario):
    for _ in range(2):
        client.post(_url(cenario), _dados(cenario, cenario['alunos'][:1]))
    assert Atribuicao.objects.count() == 1
