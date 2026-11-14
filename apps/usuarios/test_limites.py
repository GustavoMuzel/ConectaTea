"""RNF04: bloqueio depois de 5 tentativas erradas de login, na tela e na API."""
import pytest
from django.urls import reverse

from .models import Profissional, User

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'


@pytest.fixture
def prof(db):
    user = User.objects.create_user('prof@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)
    return user


def _entrar(client, senha, email='prof@ex.com'):
    return client.post(reverse('login'), {'username': email, 'password': senha})


@pytest.mark.django_db
def test_quinta_falha_bloqueia_ate_a_senha_certa(client, prof):
    for _ in range(4):
        assert 'E-mail ou senha incorretos' in _entrar(client, 'errada').content.decode()
    _entrar(client, 'errada')  # quinta
    resp = _entrar(client, SENHA)
    assert 'Muitas tentativas' in resp.content.decode()
    assert '_auth_user_id' not in client.session


@pytest.mark.django_db
def test_acerto_antes_do_limite_zera_a_contagem(client, prof):
    for _ in range(4):
        _entrar(client, 'errada')
    assert _entrar(client, SENHA).status_code == 302
    client.logout()
    for _ in range(4):
        _entrar(client, 'errada')
    assert _entrar(client, SENHA).status_code == 302  # 4 + 4 não somam: a contagem recomeçou


@pytest.mark.django_db
def test_bloqueio_e_por_email_e_ignora_maiusculas(client, prof):
    User.objects.create_user('outro@ex.com', 'Outro', SENHA, role=User.Role.PROFISSIONAL)
    for _ in range(5):
        _entrar(client, 'errada', 'PROF@ex.com')
    assert 'Muitas tentativas' in _entrar(client, SENHA, 'prof@ex.com').content.decode()
    assert _entrar(client, SENHA, 'outro@ex.com').status_code == 302  # outro e-mail não é afetado


@pytest.mark.django_db
def test_api_de_login_tem_o_mesmo_limite(client, prof):
    url = reverse('token_obtain_pair')
    for _ in range(5):
        assert client.post(url, {'email': 'prof@ex.com', 'password': 'errada'}).status_code == 401
    assert client.post(url, {'email': 'prof@ex.com', 'password': SENHA}).status_code == 429


@pytest.mark.django_db
def test_bloqueio_na_tela_vale_na_api_e_vice_versa(client, prof):
    for _ in range(5):
        client.post(reverse('token_obtain_pair'), {'email': 'prof@ex.com', 'password': 'errada'})
    assert 'Muitas tentativas' in _entrar(client, SENHA).content.decode()


@pytest.mark.django_db
def test_cache_e_compartilhado_entre_processos(settings):
    # Com LocMemCache, cada processo (worker) teria a sua própria contagem e o limite seria furado.
    assert settings.CACHES['default']['BACKEND'] == 'django.core.cache.backends.db.DatabaseCache'
