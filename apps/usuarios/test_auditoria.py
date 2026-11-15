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
    assert conteudo.splitlines()[0] == 'Quando;Tipo;Pessoa;Aluno;Ação;IP' and 'Carla' in conteudo


@pytest.mark.django_db
def test_admin_nao_permite_apagar_log(client, dados):
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', SENHA))
    log = LogAcesso.objects.first()
    assert client.get(reverse('admin:acompanhamento_logacesso_changelist')).status_code == 200
    apagar = reverse('admin:acompanhamento_logacesso_delete', args=[log.pk])
    assert client.post(apagar, {'post': 'yes'}).status_code == 403
    assert LogAcesso.objects.filter(pk=log.pk).exists()


@pytest.mark.django_db
def test_auditoria_registra_login_senha_errada_e_logout_com_ip(client, dados):
    url = reverse('login')
    client.post(url, {'username': 'ana@ex.com', 'password': 'errada'}, REMOTE_ADDR='10.0.0.5')
    client.post(url, {'username': 'ninguem@ex.com', 'password': 'errada'})
    client.post(url, {'username': 'ana@ex.com', 'password': SENHA}, HTTP_X_FORWARDED_FOR='200.1.2.3, 10.0.0.1')
    client.post(reverse('logout'))
    logs = list(LogAcesso.objects.filter(categoria='autenticacao').order_by('pk').values_list('acao', 'ip'))
    assert logs == [
        ('Tentativa de login com senha errada', '10.0.0.5'),
        ('Tentativa de login com e-mail não cadastrado (n***@ex.com)', '127.0.0.1'),
        ('Entrou no sistema', '200.1.2.3'),  # no Render, o IP real vem no X-Forwarded-For
        ('Saiu do sistema', '127.0.0.1'),
    ]


@pytest.mark.django_db
def test_auditoria_registra_gestao_e_atividades(client, dados):
    gestor = User.objects.create_superuser('adm@ex.com', 'Adm', SENHA)
    pendente = Profissional.objects.create(
        user=User.objects.create_user('nova@ex.com', 'Nova', SENHA, role=User.Role.PROFISSIONAL), especialidade='X')
    client.force_login(gestor)
    client.post(reverse('aprovar_profissional_gestao', args=[pendente.pk]))
    client.post(reverse('revogar_profissional_gestao', args=[pendente.pk]))
    client.force_login(dados['prof'].user)
    client.post(reverse('painel'), {'title': 'Nova atividade', 'category': 'x', 'tipo_material': 'formulario',
                                    'link_formulario': 'https://forms.gle/x'})
    outras = LogAcesso.objects.exclude(categoria__in=['autenticacao', 'dados_aluno'])
    acoes = list(outras.values_list('categoria', 'acao'))
    assert ('gestao', 'Aprovou o profissional Nova (X)') in acoes
    assert ('gestao', 'Revogou a aprovação de Nova') in acoes
    assert ('atividades', 'Criou a atividade "Nova atividade"') in acoes


@pytest.mark.django_db
def test_aba_todas_as_acoes_filtra_por_tipo(client, dados):
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', SENHA))  # gera "Entrou no sistema"
    resp = client.get(reverse('auditoria'), {'tipo': 'autenticacao'})
    assert {log.categoria for log in resp.context['object_list']} == {'autenticacao'}
    resp = client.get(reverse('auditoria'), {'aba': 'acessos'})
    assert {log.categoria for log in resp.context['object_list']} == {'dados_aluno'}
