import datetime

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento.models import RegistroEvolucao
from apps.atividades.models import Atividade

from .models import Aluno, Profissional, User

SENHA = 'Senha-forte-123'


def _prof(email, aprovado=True):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=aprovado)


def _aluno(email, prof, ativo=True):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.ALUNO, is_active=ativo)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


@pytest.fixture
def cenario():
    prof = _prof('prof@ex.com')
    pendente = _prof('pendente@ex.com', aprovado=False)
    aluno = _aluno('aluno@ex.com', prof)
    Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social')
    return {'prof': prof, 'pendente': pendente, 'aluno': aluno}


@pytest.mark.django_db
def test_sem_login_redireciona(client, cenario):
    resp = client.get(reverse('painel_gestao'))
    assert resp.status_code == 302 and resp.url.startswith(reverse('login'))

    resp = client.post(reverse('aprovar_profissional_gestao', args=[cenario['pendente'].pk]))
    assert resp.status_code == 302 and resp.url.startswith(reverse('login'))


@pytest.mark.django_db
def test_aluno_e_profissional_comum_recebem_403(client, cenario):
    for user in [cenario['aluno'].user, cenario['prof'].user]:
        client.force_login(user)
        assert client.get(reverse('painel_gestao')).status_code == 403
        assert client.post(reverse('aprovar_profissional_gestao', args=[cenario['pendente'].pk])).status_code == 403
    cenario['pendente'].refresh_from_db()
    assert cenario['pendente'].is_approved is False


@pytest.mark.django_db
def test_staff_sem_permissao_de_model_recebe_403(client, cenario):
    # is_staff sozinho só dá acesso ao /admin/; sem a permissão do model, não é "gestor" aqui.
    staff = User.objects.create_user('staff@ex.com', 'Staff', SENHA, is_staff=True)
    client.force_login(staff)
    assert client.get(reverse('painel_gestao')).status_code == 403
    resp = client.post(reverse('aprovar_profissional_gestao', args=[cenario['pendente'].pk]))
    assert resp.status_code == 403
    cenario['pendente'].refresh_from_db()
    assert cenario['pendente'].is_approved is False


@pytest.mark.django_db
def test_staff_com_permissao_de_model_acessa(client, cenario):
    staff = User.objects.create_user('staff@ex.com', 'Staff', SENHA, is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename='change_profissional'))
    client.force_login(staff)
    assert client.get(reverse('painel_gestao')).status_code == 200


@pytest.mark.django_db
def test_superuser_acessa_e_ve_kpis_corretos(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    inativo_prof = _prof('inativo@ex.com')
    _aluno('inativo_aluno@ex.com', cenario['prof'], ativo=False)
    client.force_login(admin)

    resp = client.get(reverse('painel_gestao'))

    assert resp.status_code == 200
    assert resp.context['total_alunos_ativos'] == 1  # o inativo não conta
    assert resp.context['total_profissionais_aprovados'] == 2  # prof + inativo_prof (aprovados)
    assert resp.context['total_profissionais_pendentes'] == 1
    assert list(resp.context['profissionais_pendentes']) == [cenario['pendente']]
    assert resp.context['total_atividades'] == 1
    assert 'pendente@ex.com' in resp.content.decode()
    assert inativo_prof.pk  # criado só para inflar a contagem de aprovados


@pytest.mark.django_db
def test_aprovar_profissional_via_post(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    client.force_login(admin)

    resp = client.post(reverse('aprovar_profissional_gestao', args=[cenario['pendente'].pk]), follow=True)

    assert resp.redirect_chain == [(reverse('painel_gestao'), 302)]
    assert 'aprovado' in resp.content.decode()
    cenario['pendente'].refresh_from_db()
    assert cenario['pendente'].is_approved is True


@pytest.mark.django_db
def test_aprovar_so_por_post(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    client.force_login(admin)
    assert client.get(reverse('aprovar_profissional_gestao', args=[cenario['pendente'].pk])).status_code == 405


@pytest.mark.django_db
def test_link_do_painel_so_aparece_para_staff_e_superuser(client, cenario):
    client.force_login(cenario['prof'].user)
    assert reverse('painel_gestao') not in client.get(reverse('painel')).content.decode()

    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    client.force_login(admin)
    assert reverse('painel_gestao') in client.get(reverse('painel_gestao')).content.decode()


@pytest.mark.django_db
def test_painel_mostra_grafico_de_conclusoes_por_semana(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    atividade = Atividade.objects.get()
    RegistroEvolucao.objects.create(aluno=cenario['aluno'], atividade=atividade,
                                    status=RegistroEvolucao.Status.CONCLUIDA)
    client.force_login(admin)

    resp = client.get(reverse('painel_gestao'))

    assert resp.status_code == 200
    assert 'canvas' in resp.content.decode()
    assert resp.context['dados']['valores'] == [1]


@pytest.mark.django_db
def test_painel_grafico_ignora_conclusoes_antigas_e_nao_concluidas(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    atividade = Atividade.objects.get()
    antiga = timezone.now() - datetime.timedelta(days=120)
    RegistroEvolucao.objects.create(aluno=cenario['aluno'], atividade=atividade,
                                    status=RegistroEvolucao.Status.CONCLUIDA, data_realizacao=antiga)
    RegistroEvolucao.objects.create(aluno=cenario['aluno'], atividade=atividade,
                                    status=RegistroEvolucao.Status.EM_ANDAMENTO)
    client.force_login(admin)

    resp = client.get(reverse('painel_gestao'))

    assert resp.context['dados'] == {'rotulos': [], 'valores': []}
    assert 'canvas' not in resp.content.decode()
