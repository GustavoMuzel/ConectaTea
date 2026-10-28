import datetime

import pytest
from django.urls import reverse

from apps.acompanhamento.models import Atribuicao, LogAcesso, RegistroEvolucao
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atividade

SENHA = 'Senha-forte-123'


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _aluno(email, prof):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


@pytest.fixture
def cenario():
    prof = _prof('prof@ex.com')
    return {
        'prof': prof,
        'aluno': _aluno('aluno@ex.com', prof),
        'colega': _aluno('colega@ex.com', prof),
        'atividade': Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social'),
    }


@pytest.mark.django_db
def test_profissional_salva_observacao_e_ela_aparece_na_evolucao(client, cenario):
    registro = RegistroEvolucao.objects.create(
        aluno=cenario['aluno'], atividade=cenario['atividade'], status=RegistroEvolucao.Status.CONCLUIDA,
    )
    client.force_login(cenario['prof'].user)
    client.post(reverse('salvar_observacao', args=[cenario['aluno'].pk, registro.pk]),
                {'observacoes': 'Manteve contato visual.'})
    registro.refresh_from_db()
    assert registro.observacoes == 'Manteve contato visual.'
    pagina = client.get(reverse('evolucao_aluno', args=[cenario['aluno'].pk])).content.decode()
    assert 'Manteve contato visual.' in pagina


@pytest.mark.django_db
def test_aluno_nao_acessa_evolucao_de_outro_aluno(client, cenario):
    registro = RegistroEvolucao.objects.create(
        aluno=cenario['colega'], atividade=cenario['atividade'], status=RegistroEvolucao.Status.CONCLUIDA,
    )
    client.force_login(cenario['aluno'].user)
    assert client.get(reverse('evolucao_aluno', args=[cenario['colega'].pk])).status_code == 403
    resp = client.post(reverse('salvar_observacao', args=[cenario['colega'].pk, registro.pk]), {'observacoes': 'x'})
    assert resp.status_code == 403
    registro.refresh_from_db()
    assert registro.observacoes == ''


@pytest.mark.django_db
def test_concluir_atualiza_a_atribuicao_para_concluida(client, cenario):
    aluno, atividade = cenario['aluno'], cenario['atividade']
    atribuicao = Atribuicao.objects.create(atividade=atividade, aluno=aluno, profissional=cenario['prof'])
    client.force_login(aluno.user)
    url = reverse('concluir_atividade', args=[atividade.pk])
    client.post(url)
    client.post(url)  # segundo envio não duplica nada
    atribuicao.refresh_from_db()
    assert atribuicao.status == Atribuicao.Status.CONCLUIDA
    assert Atribuicao.objects.count() == 1 and RegistroEvolucao.objects.count() == 1


@pytest.mark.django_db
def test_concluir_sem_distribuicao_previa_cria_atribuicao_concluida(client, cenario):
    client.force_login(cenario['aluno'].user)
    client.post(reverse('concluir_atividade', args=[cenario['atividade'].pk]))
    atribuicao = Atribuicao.objects.get()
    assert (atribuicao.aluno, atribuicao.profissional) == (cenario['aluno'], cenario['prof'])
    assert atribuicao.status == Atribuicao.Status.CONCLUIDA


@pytest.mark.django_db
def test_visualizar_evolucao_registra_log_de_acesso(client, cenario):
    client.force_login(cenario['prof'].user)
    assert client.get(reverse('evolucao_aluno', args=[cenario['aluno'].pk])).status_code == 200
    log = LogAcesso.objects.get()
    assert (log.user, log.aluno, log.acao) == (cenario['prof'].user, cenario['aluno'], 'Visualizou evolução')
    assert log.ocorrido_em is not None
