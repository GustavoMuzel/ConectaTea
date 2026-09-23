import datetime

import pytest
from django.urls import reverse

from apps.usuarios.models import Aluno, Profissional, User

from .models import Atividade

SENHA = 'Senha-forte-123'


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


@pytest.fixture
def prof(client):
    prof = _prof('prof@ex.com')
    client.force_login(prof.user)
    return prof


@pytest.mark.django_db
def test_painel_sem_login_redireciona(client):
    resp = client.get(reverse('painel'))
    assert resp.status_code == 302 and resp.url.startswith(reverse('login'))


@pytest.mark.django_db
def test_painel_bloqueia_aluno_admin_profissional_sem_perfil_e_nao_aprovado(client):
    prof = _prof('outro@ex.com')
    aluno = User.objects.create_user('aluno@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    Aluno.objects.create(user=aluno, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                         guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    sem_perfil = User.objects.create_user('semperfil@ex.com', 'X', SENHA, role=User.Role.PROFISSIONAL)
    pendente = _prof('pendente@ex.com')
    Profissional.objects.filter(pk=pendente.pk).update(is_approved=False)

    for user in [aluno, admin, sem_perfil, User.objects.get(pk=pendente.user_id)]:
        client.force_login(user)
        assert client.get(reverse('painel')).status_code == 403
        assert client.post(reverse('painel'), {'title': 'T', 'category': 'C'}).status_code == 403
    assert not Atividade.objects.exists()


@pytest.mark.django_db
def test_painel_lista_so_atividades_do_profissional(client, prof):
    Atividade.objects.create(profissional=prof, title='Minha', category='social')
    Atividade.objects.create(profissional=_prof('outro@ex.com'), title='Alheia', category='social')

    resp = client.get(reverse('painel'))
    assert resp.status_code == 200
    assert [a.title for a in resp.context['atividades']] == ['Minha']
    assert 'Alheia' not in resp.content.decode()


@pytest.mark.django_db
def test_painel_vazio_mostra_aviso(client, prof):
    assert 'ainda não cadastrou' in client.get(reverse('painel')).content.decode()


@pytest.mark.django_db
def test_cadastrar_atividade_usa_o_profissional_da_sessao(client, prof):
    outro = _prof('outro@ex.com')
    resp = client.post(reverse('painel'), {
        'title': 'Cumprimentar', 'description': 'Dizer oi', 'category': 'social', 'profissional': outro.pk,
    }, follow=True)

    atividade = Atividade.objects.get()
    assert atividade.profissional == prof
    assert atividade.description == 'Dizer oi'
    assert 'Atividade &quot;Cumprimentar&quot; cadastrada.' in resp.content.decode()


@pytest.mark.django_db
def test_cadastrar_atividade_invalida_mostra_erros(client, prof):
    resp = client.post(reverse('painel'), {'title': '', 'category': ''})
    assert resp.status_code == 200
    assert {'title', 'category'} <= resp.context['form'].errors.keys()
    assert not Atividade.objects.exists()
