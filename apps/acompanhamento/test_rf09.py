import datetime

import pytest
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atribuicao, RegistroEvolucao

SENHA = 'Senha-forte-123'
HISTORICO = reverse('historico_aluno')
CONCLUIDA, EM_ANDAMENTO = RegistroEvolucao.Status.CONCLUIDA, RegistroEvolucao.Status.EM_ANDAMENTO


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
        'cumprimentar': Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social'),
        'pedir': Atividade.objects.create(profissional=prof, title='Pedir ajuda', category='social'),
    }


def _concluir(aluno, atividade, dias_atras=0):
    return RegistroEvolucao.objects.create(
        aluno=aluno, atividade=atividade, status=CONCLUIDA,
        data_realizacao=timezone.now() - datetime.timedelta(days=dias_atras),
    )


@pytest.mark.django_db
def test_aluno_ve_o_proprio_historico(client, cenario):
    aluno = cenario['aluno']
    _concluir(aluno, cenario['cumprimentar'], dias_atras=3)
    _concluir(aluno, cenario['cumprimentar'], dias_atras=1)
    _concluir(aluno, cenario['pedir'], dias_atras=2)
    RegistroEvolucao.objects.create(aluno=aluno, atividade=cenario['pedir'], status=EM_ANDAMENTO)  # não conta
    client.force_login(aluno.user)
    resp = client.get(HISTORICO)
    assert resp.status_code == 200
    linhas = [(linha['atividade__title'], linha['tentativas']) for linha in resp.context['atividades']]
    assert linhas == [('Cumprimentar', 2), ('Pedir ajuda', 1)]  # uma linha por atividade, a mais recente primeiro
    assert 'Fazer de novo' in resp.content.decode()


@pytest.mark.django_db
def test_aluno_nao_ve_historico_de_outro(client, cenario):
    _concluir(cenario['colega'], cenario['cumprimentar'])
    client.force_login(cenario['aluno'].user)
    resp = client.get(HISTORICO)
    assert list(resp.context['atividades']) == []
    # Sem concluir nada, não dá para refazer; e a refeita do colega não aparece por id.
    assert client.post(reverse('refazer_atividade', args=[cenario['cumprimentar'].pk])).status_code == 404
    client.force_login(cenario['prof'].user)
    assert client.get(HISTORICO).status_code == 403
    client.logout()
    assert client.get(HISTORICO).status_code == 302
    # Profissional desativado: o histórico some junto com a entrega das atividades.
    _concluir(cenario['aluno'], cenario['cumprimentar'])
    client.force_login(cenario['aluno'].user)
    assert len(client.get(HISTORICO).context['atividades']) == 1
    User.objects.filter(pk=cenario['prof'].user.pk).update(is_active=False)
    assert list(client.get(HISTORICO).context['atividades']) == []


@pytest.mark.django_db
def test_fazer_de_novo_abre_tentativa_em_andamento_e_concluir_fecha_ela(client, cenario):
    aluno, atividade = cenario['aluno'], cenario['cumprimentar']
    _concluir(aluno, atividade, dias_atras=5)
    client.force_login(aluno.user)
    url = reverse('refazer_atividade', args=[atividade.pk])
    assert client.get(url).status_code == 405

    resp = client.post(url)
    assert resp.status_code == 302 and resp.url == reverse('confirmar_conclusao', args=[atividade.pk])
    assert RegistroEvolucao.objects.filter(aluno=aluno, atividade=atividade, status=EM_ANDAMENTO).count() == 1
    client.post(url)  # segundo clique retoma a mesma tentativa
    assert RegistroEvolucao.objects.filter(status=EM_ANDAMENTO).count() == 1

    concluir = reverse('concluir_atividade', args=[atividade.pk])
    client.post(concluir)
    client.post(concluir)  # duplo clique não cria uma terceira conclusão
    assert RegistroEvolucao.objects.filter(status=EM_ANDAMENTO).count() == 0
    assert RegistroEvolucao.objects.filter(status=CONCLUIDA).count() == 2
    assert Atribuicao.objects.get(aluno=aluno, atividade=atividade).status == Atribuicao.Status.CONCLUIDA


@pytest.mark.django_db
def test_banco_barra_segunda_tentativa_em_andamento(cenario):
    dados = {'aluno': cenario['aluno'], 'atividade': cenario['cumprimentar'], 'status': EM_ANDAMENTO}
    RegistroEvolucao.objects.create(**dados)
    with pytest.raises(IntegrityError):
        RegistroEvolucao.objects.create(**dados)


@pytest.mark.django_db
def test_profissional_ve_historico_de_tentativas_do_aluno(client, cenario):
    aluno, atividade = cenario['aluno'], cenario['cumprimentar']
    primeira, segunda = _concluir(aluno, atividade, dias_atras=4), _concluir(aluno, atividade, dias_atras=1)
    RegistroEvolucao.objects.filter(pk=primeira.pk).update(observacoes='Precisou de ajuda.')
    RegistroEvolucao.objects.filter(pk=segunda.pk).update(observacoes='Fez sozinho.')
    client.force_login(cenario['prof'].user)
    resp = client.get(reverse('evolucao_aluno', args=[aluno.pk]))
    registros = [(registro.pk, registro.tentativa) for registro, _ in resp.context['registros']]
    assert registros == [(segunda.pk, 2), (primeira.pk, 1)]  # mais recente primeiro
    pagina = resp.content.decode()
    assert 'tentativa 2' in pagina and 'Fez sozinho.' in pagina and 'Precisou de ajuda.' in pagina
