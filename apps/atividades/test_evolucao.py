import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento.models import RegistroEvolucao
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atividade

SENHA = 'Senha-forte-123'


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _aluno(email, prof, nome=None):
    user = User.objects.create_user(email, nome or email, SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


@pytest.fixture
def cenario(client):
    prof = _prof('prof@ex.com')
    outro_prof = _prof('outro@ex.com')
    aluno = _aluno('aluno@ex.com', prof, 'Bia')
    aluno_alheio = _aluno('alheio@ex.com', outro_prof, 'Alheio')
    atividade = Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social')
    client.force_login(prof.user)
    return {
        'prof': prof, 'outro_prof': outro_prof, 'aluno': aluno, 'aluno_alheio': aluno_alheio,
        'atividade': atividade,
    }


@pytest.mark.django_db
def test_alunos_sem_login_redireciona(client):
    prof = _prof('prof@ex.com')
    aluno = _aluno('aluno@ex.com', prof)
    for url in [reverse('alunos_profissional'), reverse('evolucao_aluno', args=[aluno.pk])]:
        resp = client.get(url)
        assert resp.status_code == 302 and resp.url.startswith(reverse('login'))


@pytest.mark.django_db
def test_alunos_bloqueia_quem_nao_e_profissional_aprovado(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    sem_perfil = User.objects.create_user('semperfil@ex.com', 'X', SENHA, role=User.Role.PROFISSIONAL)
    for user in [cenario['aluno'].user, admin, sem_perfil]:
        client.force_login(user)
        assert client.get(reverse('alunos_profissional')).status_code == 403
        assert client.get(reverse('evolucao_aluno', args=[cenario['aluno'].pk])).status_code == 403


@pytest.mark.django_db
def test_lista_mostra_so_os_alunos_do_proprio_profissional(client, cenario):
    resp = client.get(reverse('alunos_profissional'))
    assert resp.status_code == 200
    assert list(resp.context['alunos']) == [cenario['aluno']]
    assert 'Alheio' not in resp.content.decode()


@pytest.mark.django_db
def test_evolucao_lista_concluidas_da_mais_recente_para_a_mais_antiga(client, cenario):
    aluno, atividade = cenario['aluno'], cenario['atividade']
    outra_atividade = Atividade.objects.create(profissional=cenario['prof'], title='Pedir ajuda', category='social')
    antiga = RegistroEvolucao.objects.create(
        aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.CONCLUIDA,
        data_realizacao=timezone.now() - datetime.timedelta(days=2),
    )
    recente = RegistroEvolucao.objects.create(
        aluno=aluno, atividade=outra_atividade, status=RegistroEvolucao.Status.CONCLUIDA,
        data_realizacao=timezone.now() - datetime.timedelta(days=1),
    )
    RegistroEvolucao.objects.create(aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.PENDENTE)

    resp = client.get(reverse('evolucao_aluno', args=[aluno.pk]))
    assert resp.status_code == 200
    assert resp.context['aluno'] == aluno
    registros = [registro for registro, _ in resp.context['registros']]
    assert registros == [recente, antiga]  # pendente não aparece; mais recente primeiro


@pytest.mark.django_db
def test_evolucao_de_aluno_de_outro_profissional_da_404(client, cenario):
    resp = client.get(reverse('evolucao_aluno', args=[cenario['aluno_alheio'].pk]))
    assert resp.status_code == 404


@pytest.mark.django_db
def test_salvar_observacao_atualiza_o_registro(client, cenario):
    registro = RegistroEvolucao.objects.create(
        aluno=cenario['aluno'], atividade=cenario['atividade'], status=RegistroEvolucao.Status.CONCLUIDA,
    )
    resp = client.post(
        reverse('salvar_observacao', args=[cenario['aluno'].pk, registro.pk]),
        {'observacoes': 'Foi muito bem, manteve contato visual.'}, follow=True,
    )
    assert resp.status_code == 200
    registro.refresh_from_db()
    assert registro.observacoes == 'Foi muito bem, manteve contato visual.'


@pytest.mark.django_db
def test_salvar_observacao_de_aluno_de_outro_profissional_da_404(client, cenario):
    registro = RegistroEvolucao.objects.create(
        aluno=cenario['aluno_alheio'], atividade=cenario['atividade'], status=RegistroEvolucao.Status.CONCLUIDA,
    )
    resp = client.post(
        reverse('salvar_observacao', args=[cenario['aluno_alheio'].pk, registro.pk]), {'observacoes': 'x'},
    )
    assert resp.status_code == 404
    registro.refresh_from_db()
    assert registro.observacoes == ''


@pytest.mark.django_db
def test_salvar_observacao_com_aluno_e_registro_incompativeis_da_404(client, cenario):
    # aluno_pk é do próprio profissional, mas o registro é de outro aluno: continua barrado.
    outro_aluno = _aluno('outro_aluno@ex.com', cenario['prof'], 'Outro')
    registro_do_outro = RegistroEvolucao.objects.create(
        aluno=outro_aluno, atividade=cenario['atividade'], status=RegistroEvolucao.Status.CONCLUIDA,
    )
    resp = client.post(
        reverse('salvar_observacao', args=[cenario['aluno'].pk, registro_do_outro.pk]), {'observacoes': 'x'},
    )
    assert resp.status_code == 404
    registro_do_outro.refresh_from_db()
    assert registro_do_outro.observacoes == ''


@pytest.mark.django_db
def test_salvar_observacao_so_por_post(client, cenario):
    registro = RegistroEvolucao.objects.create(
        aluno=cenario['aluno'], atividade=cenario['atividade'], status=RegistroEvolucao.Status.CONCLUIDA,
    )
    assert client.get(reverse('salvar_observacao', args=[cenario['aluno'].pk, registro.pk])).status_code == 405
