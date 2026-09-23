import datetime
from unittest.mock import patch

import pytest
import requests

from .models import Aluno, Profissional, User
from .services.email import BREVO_URL, enviar_boas_vindas, enviar_notificacao_aluno_criado


@pytest.fixture
def user(db):
    return User.objects.create_user('a@ex.com', '<b>Ana</b>', 'x', role=User.Role.ALUNO)


@pytest.fixture
def aluno_user(db):
    prof = Profissional.objects.create(
        user=User.objects.create_user('prof@ex.com', 'Prof', 'x', role=User.Role.PROFISSIONAL),
        especialidade='Psicologia', is_approved=True,
    )
    user = User.objects.create_user('aluno@ex.com', 'Aluno', 'x', role=User.Role.ALUNO)
    Aluno.objects.create(
        user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
        guardian_name='Resp', guardian_phone='11999999999', guardian_email='resp@ex.com',
        consentimento_data=datetime.datetime(2026, 1, 1, 12, 0, tzinfo=datetime.timezone.utc),
    )
    return user


def test_envia_pelo_brevo_sem_o_nome_do_usuario(user, settings):
    settings.BREVO_API_KEY = 'chave'
    settings.BREVO_SENDER_EMAIL = 'nao-responda@ex.com'
    with patch('apps.usuarios.services.email.requests.post') as post:
        assert enviar_boas_vindas(user) is True

    url, kwargs = post.call_args.args[0], post.call_args.kwargs
    assert url == BREVO_URL
    assert kwargs['headers']['api-key'] == 'chave'
    assert kwargs['timeout'] == (3, 5)
    assert kwargs['json']['to'] == [{'email': 'a@ex.com'}]
    assert kwargs['json']['sender']['email'] == 'nao-responda@ex.com'
    assert 'Ana' not in str(kwargs['json'])
    assert 'Aluno' in kwargs['json']['htmlContent']


def test_sem_chave_nao_chama_api(user, settings):
    settings.BREVO_API_KEY = ''
    with patch('apps.usuarios.services.email.requests.post') as post:
        assert enviar_boas_vindas(user) is False
    post.assert_not_called()


def test_timeout_nao_levanta_excecao(user, settings):
    settings.BREVO_API_KEY = 'chave'
    with patch('apps.usuarios.services.email.requests.post', side_effect=requests.Timeout):
        assert enviar_boas_vindas(user) is False


def test_resposta_de_erro_nao_levanta_excecao(user, settings):
    settings.BREVO_API_KEY = 'chave'
    with patch('apps.usuarios.services.email.requests.post') as post:
        post.return_value.raise_for_status.side_effect = requests.HTTPError('401')
        assert enviar_boas_vindas(user) is False


def test_notificacao_aluno_criado_avisa_o_responsavel(aluno_user, settings):
    settings.BREVO_API_KEY = 'chave'
    with patch('apps.usuarios.services.email.requests.post') as post:
        assert enviar_notificacao_aluno_criado(aluno_user) is True

    kwargs = post.call_args.kwargs
    assert kwargs['json']['to'] == [{'email': 'resp@ex.com'}]
    assert 'Termos de Uso' in kwargs['json']['htmlContent']
    assert 'Política de Privacidade' in kwargs['json']['htmlContent']
