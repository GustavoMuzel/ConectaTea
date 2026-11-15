"""Botão "Enviar e-mail de teste" do Painel de Gestão: mostra o motivo exato quando o Brevo recusa."""
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse

from .models import User
from .services.email import diagnosticar_brevo

pytestmark = pytest.mark.integration


def _resposta(status, mensagem=''):
    resp = MagicMock(ok=200 <= status < 300, status_code=status)
    resp.json.return_value = {'message': mensagem}
    return resp


@pytest.fixture
def brevo(settings):
    settings.BREVO_API_KEY, settings.BREVO_SENDER_EMAIL = 'chave', 'nao-responda@ex.com'
    with patch('apps.usuarios.services.email.requests.post') as post:
        yield post


@pytest.mark.django_db
def test_sem_chave_explica_o_que_falta(settings):
    settings.BREVO_API_KEY = ''
    ok, msg = diagnosticar_brevo('a@ex.com')
    assert not ok and 'BREVO_API_KEY' in msg


@pytest.mark.django_db
@pytest.mark.parametrize('status, mensagem, trecho', [
    (401, 'We have detected you are using an unrecognised IP address 1.2.3.4', 'IPs autorizados'),
    (401, 'Key not found', 'chave da API'),
    (400, 'sender is not valid', 'não está validado'),
    (500, 'erro interno', 'HTTP 500'),
])
def test_explica_cada_recusa_do_brevo(brevo, status, mensagem, trecho):
    brevo.return_value = _resposta(status, mensagem)
    ok, msg = diagnosticar_brevo('a@ex.com')
    assert not ok and trecho in msg and mensagem in msg


@pytest.mark.django_db
def test_botao_do_painel_mostra_o_resultado(client, brevo):
    brevo.return_value = _resposta(201)
    client.force_login(User.objects.create_superuser('adm@ex.com', 'Adm', 'Senha-forte-123'))
    resp = client.post(reverse('teste_email'), {'destino': 'eu@ex.com'}, follow=True)
    assert 'E-mail de teste enviado para eu@ex.com' in resp.content.decode()
    assert brevo.call_args.kwargs['json']['to'] == [{'email': 'eu@ex.com'}]


@pytest.mark.django_db
def test_so_gestor_usa_o_teste(client, brevo):
    client.force_login(User.objects.create_user('p@ex.com', 'P', 'Senha-forte-123', role=User.Role.PROFISSIONAL))
    assert client.post(reverse('teste_email')).status_code == 403
    brevo.assert_not_called()
