import datetime
from unittest.mock import patch

import pytest
from django.urls import reverse
from django.utils import timezone

from .models import Aluno, Profissional, User

SENHA = 'Senha-forte-123'
ALUNO = {'birth_date': '2011-05-01', 'guardian_name': 'Resp', 'guardian_phone': '11999999999',
         'guardian_email': 'resp@ex.com', 'consentimento_responsavel': 'on'}


@pytest.fixture
def prof():
    user = User.objects.create_user('prof@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _dados(role, **extra):
    return {'name': 'Novo', 'email': 'Novo@Ex.com', 'password1': SENHA, 'password2': SENHA, 'role': role, **extra}


@pytest.mark.django_db
@pytest.mark.parametrize('nome', ['login', 'cadastro'])
def test_paginas_publicas_renderizam(client, nome):
    resp = client.get(reverse(nome))
    assert resp.status_code == 200
    assert 'bootstrap@5.3.8' in resp.content.decode()


@pytest.mark.django_db
def test_home_sem_login_mostra_pagina_publica(client):
    resp = client.get(reverse('home'))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert reverse('login') in html and reverse('cadastro') in html


@pytest.mark.django_db
@pytest.mark.parametrize('nome', ['termos', 'privacidade'])
def test_paginas_legais_publicas_retornam_200(client, nome):
    assert client.get(reverse(nome)).status_code == 200


@pytest.mark.django_db
def test_cadastro_profissional_cria_perfil_loga_e_envia_boas_vindas(client, django_capture_on_commit_callbacks):
    with patch('apps.usuarios.views.enviar_boas_vindas') as enviar, django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse('cadastro'), _dados('profissional', especialidade='Pedagogia'))

    assert resp.status_code == 302
    user = User.objects.get(email='novo@ex.com')
    assert user.role == 'profissional' and user.check_password(SENHA)
    assert user.profissional.especialidade == 'Pedagogia'
    assert user.profissional.registro_profissional is None
    assert user.profissional.is_approved is False
    enviar.assert_called_once_with(user)
    home = client.get(reverse('home'))
    assert home.status_code == 200 and 'aguardando aprovação' in home.content.decode()
    assert client.get(reverse('painel')).status_code == 403


@pytest.mark.django_db
def test_cadastro_aluno_cria_perfil_vinculado(client, prof):
    antes = timezone.now()
    with patch('apps.usuarios.views.enviar_boas_vindas'), patch('apps.usuarios.views.enviar_notificacao_aluno_criado'):
        resp = client.post(reverse('cadastro'), _dados('aluno', profissional=prof.pk, **ALUNO))

    assert resp.status_code == 302
    aluno = Aluno.objects.get(user__email='novo@ex.com')
    assert aluno.profissional == prof
    assert aluno.birth_date == datetime.date(2011, 5, 1)
    assert aluno.consentimento_data is not None and aluno.consentimento_data >= antes
    assert client.get(reverse('home')).url == reverse('aluno_atividades')


@pytest.mark.django_db
def test_cadastro_aluno_envia_notificacao_ao_responsavel(client, prof, django_capture_on_commit_callbacks):
    with patch('apps.usuarios.views.enviar_boas_vindas'), \
         patch('apps.usuarios.views.enviar_notificacao_aluno_criado') as notificar, \
         django_capture_on_commit_callbacks(execute=True):
        client.post(reverse('cadastro'), _dados('aluno', profissional=prof.pk, **ALUNO))

    notificar.assert_called_once()
    assert notificar.call_args.args[0].email == 'novo@ex.com'


@pytest.mark.django_db
def test_cadastro_profissional_nao_envia_notificacao_de_aluno(client, django_capture_on_commit_callbacks):
    with patch('apps.usuarios.views.enviar_boas_vindas'), \
         patch('apps.usuarios.views.enviar_notificacao_aluno_criado') as notificar, \
         django_capture_on_commit_callbacks(execute=True):
        client.post(reverse('cadastro'), _dados('profissional', especialidade='X'))

    notificar.assert_not_called()


@pytest.mark.django_db
def test_cadastro_mostra_links_para_termos_e_privacidade(client):
    html = client.get(reverse('cadastro')).content.decode()
    assert reverse('termos') in html and reverse('privacidade') in html


@pytest.mark.django_db
@pytest.mark.parametrize('dados, campo', [
    (_dados('admin'), 'role'),
    (_dados('profissional'), 'especialidade'),
    (_dados('aluno', **ALUNO), 'profissional'),
    (_dados('aluno', **{**ALUNO, 'birth_date': '2999-01-01'}), 'birth_date'),
    ({**_dados('profissional', especialidade='X'), 'password2': 'outra'}, 'password2'),
    (_dados('aluno', **{**ALUNO, 'consentimento_responsavel': ''}), 'consentimento_responsavel'),
])
def test_cadastro_invalido_nao_cria_nada(client, prof, dados, campo, django_capture_on_commit_callbacks):
    # execute=True: sem isso, um envio agendado via on_commit nunca rodaria e o assert_not_called seria vazio.
    with patch('apps.usuarios.views.enviar_boas_vindas') as enviar, django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse('cadastro'), dados)

    assert resp.status_code == 200
    assert campo in resp.context['form'].errors
    assert not User.objects.filter(email='novo@ex.com').exists()
    enviar.assert_not_called()


@pytest.mark.django_db
def test_cadastro_rejeita_email_repetido_sem_diferenciar_maiusculas(client, prof, django_capture_on_commit_callbacks):
    with patch('apps.usuarios.views.enviar_boas_vindas') as enviar, django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse('cadastro'), {**_dados('profissional', especialidade='X'), 'email': 'PROF@ex.com'})
    assert 'email' in resp.context['form'].errors
    assert User.objects.count() == 1
    enviar.assert_not_called()


@pytest.mark.django_db
def test_cadastro_nao_permite_escalar_privilegio(client):
    with patch('apps.usuarios.views.enviar_boas_vindas'):
        client.post(reverse('cadastro'), _dados('profissional', especialidade='X', is_staff='on', is_superuser='on'))
    user = User.objects.get(email='novo@ex.com')
    assert not user.is_staff and not user.is_superuser


@pytest.mark.django_db
def test_login_e_logout_por_sessao(client, prof):
    resp = client.post(reverse('login'), {'username': 'prof@ex.com', 'password': SENHA})
    assert resp.status_code == 302 and resp.url == reverse('home')

    assert client.get(reverse('logout')).status_code == 405  # sair só por POST
    client.post(reverse('logout'))
    assert '_auth_user_id' not in client.session
    assert client.get(reverse('home')).status_code == 200  # home é pública; sem sessão só some o menu logado


@pytest.mark.django_db
def test_login_invalido_e_usuario_inativo(client, prof):
    resp = client.post(reverse('login'), {'username': 'prof@ex.com', 'password': 'errada'})
    assert resp.status_code == 200 and resp.context['form'].non_field_errors()

    User.objects.update(is_active=False)
    resp = client.post(reverse('login'), {'username': 'prof@ex.com', 'password': SENHA})
    assert resp.status_code == 200
    assert '_auth_user_id' not in client.session


@pytest.mark.django_db(transaction=True)
def test_falha_inesperada_no_email_nao_quebra_cadastro(client):
    # transaction=True: on_commit roda de verdade, fora da transação do teste.
    with patch('apps.usuarios.views.enviar_boas_vindas', side_effect=RuntimeError('brevo fora')) as enviar:
        resp = client.post(reverse('cadastro'), _dados('profissional', especialidade='X'))
    assert resp.status_code == 302
    enviar.assert_called_once()
    assert User.objects.filter(email='novo@ex.com').exists()


@pytest.mark.django_db
def test_login_ignora_maiusculas_no_email(client, prof):
    resp = client.post(reverse('login'), {'username': 'PROF@Ex.com', 'password': SENHA})
    assert resp.status_code == 302


@pytest.mark.django_db
def test_login_nao_redireciona_para_site_externo(client, prof):
    resp = client.post(reverse('login') + '?next=https://golpe.example/',
                       {'username': 'prof@ex.com', 'password': SENHA, 'next': 'https://golpe.example/'})
    assert resp.status_code == 302 and resp.url == reverse('home')


@pytest.mark.django_db
def test_cadastro_esconde_senha_e_dados_do_responsavel_em_relatorio_de_erro(rf):
    from django.contrib.auth.models import AnonymousUser

    from .views import CadastroView

    request = rf.post(reverse('cadastro'), {})
    request.user = AnonymousUser()
    CadastroView.as_view()(request)
    assert request.sensitive_post_parameters == '__ALL__'


@pytest.mark.django_db
def test_cadastro_aluno_sem_consentimento_mostra_erro_e_nao_cria(client, prof):
    dados = _dados('aluno', profissional=prof.pk, **ALUNO)
    del dados['consentimento_responsavel']
    resp = client.post(reverse('cadastro'), dados)

    assert resp.status_code == 200
    assert resp.context['form'].errors['consentimento_responsavel'] == ['Marque esta caixa para continuar.']
    assert not User.objects.filter(email='novo@ex.com').exists()


@pytest.mark.django_db
def test_cadastro_profissional_nao_exige_consentimento(client):
    with patch('apps.usuarios.views.enviar_boas_vindas'):
        resp = client.post(reverse('cadastro'), _dados('profissional', especialidade='X'))
    assert resp.status_code == 302


@pytest.mark.django_db
def test_cadastro_lista_so_profissionais_aprovados(client, prof):
    pendente = Profissional.objects.create(
        user=User.objects.create_user('pend@ex.com', 'Pendente Silva', SENHA, role=User.Role.PROFISSIONAL),
        especialidade='X',
    )
    resp = client.get(reverse('cadastro'))
    assert list(resp.context['form'].fields['profissional'].queryset) == [prof]
    assert 'Pendente Silva' not in resp.content.decode()

    with patch('apps.usuarios.views.enviar_boas_vindas'):
        resp = client.post(reverse('cadastro'), _dados('aluno', profissional=pendente.pk, **ALUNO))
    assert 'profissional' in resp.context['form'].errors
    assert not Aluno.objects.exists()


@pytest.mark.django_db
def test_home_de_profissional_sem_perfil_nao_fala_em_aprovacao(client):
    client.force_login(User.objects.create_user('x@ex.com', 'X', SENHA, role=User.Role.PROFISSIONAL))
    html = client.get(reverse('home')).content.decode()
    assert 'aguardando aprovação' not in html
