import datetime

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.acompanhamento.models import RegistroEvolucao
from apps.atividades.models import Atividade

from .models import Aluno, Profissional, User

SENHA = 'senha-forte-123'


@pytest.fixture
def dados(client):
    admin_user = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    client.force_login(admin_user)
    prof = Profissional.objects.create(
        user=User.objects.create_user('prof@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL),
        especialidade='Psicologia',
    )
    aluno = Aluno.objects.create(
        user=User.objects.create_user('aluno@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO),
        profissional=prof, birth_date=datetime.date(2011, 5, 1),
        guardian_name='Resp', guardian_phone='11999999999', guardian_email='resp@ex.com',
    )
    atividade = Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social')
    RegistroEvolucao.objects.create(aluno=aluno, atividade=atividade)
    return {'aluno': aluno, 'prof': prof}


def _nada_apagado():
    assert User.objects.count() == 3
    assert Aluno.objects.count() == Profissional.objects.count() == RegistroEvolucao.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('modelo, obj', [('aluno', 'aluno'), ('profissional', 'prof'), ('user', 'aluno.user')])
def test_excluir_um_registro_so_inativa(client, dados, modelo, obj):
    alvo = dados['aluno'].user if obj == 'aluno.user' else dados[obj]
    url = reverse(f'admin:usuarios_{modelo}_delete', args=[alvo.pk])

    confirmacao = client.get(url)
    assert confirmacao.status_code == 200
    assert not confirmacao.context['protected']

    resp = client.post(url, {'post': 'yes'})
    assert resp.status_code == 302
    alvo.refresh_from_db()
    email = 'prof@ex.com' if modelo == 'profissional' else 'aluno@ex.com'
    assert list(User.objects.filter(is_active=False).values_list('email', flat=True)) == [email]
    _nada_apagado()


@pytest.mark.django_db
@pytest.mark.parametrize('modelo', ['aluno', 'profissional', 'user'])
def test_acao_em_massa_desativa_e_delete_selected_nao_existe(client, dados, modelo):
    url = reverse(f'admin:usuarios_{modelo}_changelist')
    acoes = dict(client.get(url).context['action_form'].fields['action'].choices)
    assert 'delete_selected' not in acoes
    assert 'desativar_usuarios' in acoes

    ids = {'aluno': [dados['aluno'].pk], 'profissional': [dados['prof'].pk],
           'user': [dados['aluno'].user_id, dados['prof'].user_id]}[modelo]
    resp = client.post(url, {'action': 'desativar_usuarios', '_selected_action': ids})
    assert resp.status_code == 302

    esperado = {'aluno': ['aluno@ex.com'], 'profissional': ['prof@ex.com'],
                'user': ['aluno@ex.com', 'prof@ex.com']}[modelo]
    assert sorted(User.objects.filter(is_active=False).values_list('email', flat=True)) == esperado
    assert User.objects.get(email='admin@ex.com').is_active
    _nada_apagado()


@pytest.mark.django_db
def test_usuario_inativo_nao_faz_login(client, dados):
    client.post(reverse('admin:usuarios_aluno_delete', args=[dados['aluno'].pk]), {'post': 'yes'})
    resp = client.post('/api/auth/login/', {'email': 'aluno@ex.com', 'password': SENHA},
                       content_type='application/json')
    assert resp.status_code == 401


@pytest.mark.django_db
def test_exclusao_registra_log_de_alteracao_e_mensagem_de_desativado(client, dados):
    url = reverse('admin:usuarios_aluno_delete', args=[dados['aluno'].pk])
    resp = client.post(url, {'post': 'yes'}, follow=True)

    assert 'foi desativado' in resp.content.decode()
    assert list(LogEntry.objects.values_list('action_flag', flat=True)) == [CHANGE]


@pytest.mark.django_db
def test_admin_nao_desativa_a_si_mesmo(client, dados):
    admin_user = User.objects.get(email='admin@ex.com')
    assert client.post(reverse('admin:usuarios_user_delete', args=[admin_user.pk]), {'post': 'yes'}).status_code == 403

    client.post(reverse('admin:usuarios_user_changelist'),
                {'action': 'desativar_usuarios', '_selected_action': [admin_user.pk]})
    admin_user.refresh_from_db()
    assert admin_user.is_active


def _staff(client, *perms):
    staff = User.objects.create_user('staff@ex.com', 'Staff', SENHA, is_staff=True)
    staff.user_permissions.set(Permission.objects.filter(codename__in=perms))
    client.force_login(staff)


@pytest.mark.django_db
def test_staff_nao_desativa_superusuario(client, dados):
    _staff(client, 'view_user', 'change_user', 'delete_user')
    admin_user = User.objects.get(email='admin@ex.com')
    client.post(reverse('admin:usuarios_user_changelist'),
                {'action': 'desativar_usuarios', '_selected_action': [admin_user.pk]})
    admin_user.refresh_from_db()
    assert admin_user.is_active


@pytest.mark.django_db
def test_aprovar_profissionais_em_massa(client, dados):
    pendente = Profissional.objects.create(
        user=User.objects.create_user('pendente@ex.com', 'Pendente', SENHA, role=User.Role.PROFISSIONAL),
        especialidade='Pedagogia',
    )
    resp = client.post(reverse('admin:usuarios_profissional_changelist'),
                       {'action': 'aprovar_profissionais', '_selected_action': [pendente.pk]})

    assert resp.status_code == 302
    pendente.refresh_from_db()
    assert pendente.is_approved is True
    assert dados['prof'].is_approved is False  # não selecionado: aprovação não vaza para os outros


@pytest.mark.django_db
@pytest.mark.parametrize('perms, aprovados', [
    (['view_profissional'], 0),
    (['view_profissional', 'change_profissional'], 2),
])
def test_aprovar_em_massa_exige_change_profissional(client, dados, perms, aprovados):
    pendentes = [
        Profissional.objects.create(
            user=User.objects.create_user(f'p{i}@ex.com', f'P{i}', SENHA, role=User.Role.PROFISSIONAL),
            especialidade='Pedagogia',
        ).pk
        for i in range(2)
    ]
    _staff(client, *perms)
    resp = client.post(reverse('admin:usuarios_profissional_changelist'),
                       {'action': 'aprovar_profissionais', '_selected_action': pendentes}, follow=True)

    assert Profissional.objects.filter(pk__in=pendentes, is_approved=True).count() == aprovados
    sem_permissao = 'Você não tem permissão para aprovar profissionais.' in resp.content.decode()
    assert sem_permissao is (aprovados == 0)


@pytest.mark.django_db
def test_desativar_aluno_exige_change_user(client, dados):
    _staff(client, 'view_aluno', 'delete_aluno')
    url = reverse('admin:usuarios_aluno_delete', args=[dados['aluno'].pk])
    assert client.post(url, {'post': 'yes'}).status_code == 403
    assert User.objects.get(email='aluno@ex.com').is_active
