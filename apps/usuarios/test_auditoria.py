"""Aba Auditoria do Painel de Gestão (RNF05)."""
import datetime

import pytest
from django.urls import reverse

from apps.acompanhamento.models import LogAcesso
from apps.salas.models import ParticipacaoVideochamada, Sala

from .models import Aluno, Profissional, User

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'


@pytest.fixture
def dados(db):
    pu = User.objects.create_user('ana@ex.com', 'Ana Prof', SENHA, role=User.Role.PROFISSIONAL)
    prof = Profissional.objects.create(user=pu, especialidade='Psicologia', is_approved=True)
    alunos = []
    for nome in ('Bruno', 'Carla'):
        u = User.objects.create_user(f'{nome.lower()}@ex.com', nome, SENHA, role=User.Role.ALUNO)
        alunos.append(Aluno.objects.create(user=u, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                           guardian_name='R', guardian_phone='1', guardian_email='r@ex.com'))
    LogAcesso.objects.create(user=pu, aluno=alunos[0], acao='Visualizou evolução')
    LogAcesso.objects.create(user=pu, aluno=alunos[1], acao='Visualizou evolução')
    sala = Sala.objects.create(aluno=alunos[0], dono=prof)
    ParticipacaoVideochamada.objects.create(sala=sala, user=pu)
    return {'prof': prof, 'alunos': alunos}


@pytest.mark.django_db
def test_so_gestor_ve_a_auditoria(client, dados):
    url = reverse('auditoria')
    assert client.get(url).status_code == 302  # visitante vai para o login
    client.force_login(dados['prof'].user)
    assert client.get(url).status_code == 403
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', SENHA))
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_filtra_por_aluno_e_mostra_videochamadas(client, dados):
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', SENHA))
    resp = client.get(reverse('auditoria'), {'aluno': 'brun'})
    assert [log.aluno.user.name for log in resp.context['object_list']] == ['Bruno']
    resp = client.get(reverse('auditoria'), {'aba': 'videochamadas'})
    assert resp.context['object_list'].count() == 1


@pytest.mark.django_db
def test_exporta_csv(client, dados):
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', SENHA))
    resp = client.get(reverse('auditoria'), {'formato': 'csv'})
    conteudo = resp.content.decode('utf-8-sig')
    assert resp['Content-Type'].startswith('text/csv')
    assert conteudo.splitlines()[0] == 'Quando;Pessoa;Aluno;Ação' and 'Carla' in conteudo


@pytest.mark.django_db
def test_admin_nao_permite_apagar_log(client, dados):
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', SENHA))
    log = LogAcesso.objects.first()
    assert client.get(reverse('admin:acompanhamento_logacesso_changelist')).status_code == 200
    apagar = reverse('admin:acompanhamento_logacesso_delete', args=[log.pk])
    assert client.post(apagar, {'post': 'yes'}).status_code == 403
    assert LogAcesso.objects.filter(pk=log.pk).exists()
