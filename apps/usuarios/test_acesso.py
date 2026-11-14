"""Avisos de login, aprovação do profissional, aceite dos termos e recuperação de senha."""
import re
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from .models import CodigoVerificacao, Profissional, User

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'


def _cadastro(role, **extra):
    dados = {'name': 'Novo', 'email': 'novo@ex.com', 'password1': SENHA, 'password2': SENHA, 'role': role,
             'aceite_termos': 'on'}
    return dados | extra


def _msgs(resp):
    return [str(m) for m in get_messages(resp.wsgi_request)]


@pytest.fixture
def pendente():
    user = User.objects.create_user('pend@ex.com', 'Pendente', SENHA, role=User.Role.PROFISSIONAL)
    Profissional.objects.create(user=user, especialidade='X')
    return user


# Aceite dos termos -----------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_cadastro_sem_aceite_dos_termos_e_recusado(client):
    dados = _cadastro('profissional', especialidade='X')
    del dados['aceite_termos']
    resp = client.post(reverse('cadastro'), dados)
    assert resp.status_code == 200
    assert 'aceite_termos' in resp.context['form'].errors
    assert not User.objects.exists()


@pytest.mark.django_db
def test_cadastro_grava_data_do_aceite_dos_termos(client):
    with patch('apps.usuarios.views.enviar_boas_vindas'):
        client.post(reverse('cadastro'), _cadastro('profissional', especialidade='X'))
    assert User.objects.get().termos_aceitos_em is not None


@pytest.mark.django_db
def test_caixa_de_aceite_tem_links_para_os_documentos(client):
    html = client.get(reverse('cadastro')).content.decode()
    assert 'Li e aceito os' in html
    assert html.count(f'href="{reverse("termos")}"') >= 2  # caixa do aluno e caixa geral


# Aviso do profissional -------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_cadastro_mostra_aviso_de_aprovacao_para_profissional(client):
    assert 'Sua conta precisará ser aprovada' in client.get(reverse('cadastro')).content.decode()


@pytest.mark.django_db
def test_cadastro_de_profissional_avisa_que_aguarda_aprovacao(client):
    with patch('apps.usuarios.views.enviar_boas_vindas'):
        resp = client.post(reverse('cadastro'), _cadastro('profissional', especialidade='X'), follow=True)
    html = resp.content.decode()
    assert 'Conta criada com sucesso' in html and 'Conta aguardando aprovação' in html


@pytest.mark.django_db
def test_boas_vindas_do_profissional_fala_da_aprovacao():
    from .services.email import enviar_boas_vindas
    user = User.objects.create_user('p@ex.com', 'P', SENHA, role=User.Role.PROFISSIONAL)
    with patch('apps.usuarios.services.email.enviar_email') as envio:
        enviar_boas_vindas(user)
    assert 'aprovadas por um administrador' in envio.call_args.args[2]


# Avisos do login -------------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_login_invalido_explica_o_erro(client, pendente):
    resp = client.post(reverse('login'), {'username': 'pend@ex.com', 'password': 'errada'})
    assert 'E-mail ou senha incorretos' in resp.content.decode()


@pytest.mark.django_db
def test_login_de_conta_desativada_explica_o_motivo(client, pendente):
    User.objects.update(is_active=False)
    resp = client.post(reverse('login'), {'username': 'pend@ex.com', 'password': SENHA})
    assert 'Esta conta está desativada' in resp.content.decode()
    assert '_auth_user_id' not in client.session


@pytest.mark.django_db
def test_conta_desativada_com_senha_errada_nao_revela_que_existe(client, pendente):
    User.objects.update(is_active=False)
    resp = client.post(reverse('login'), {'username': 'pend@ex.com', 'password': 'errada'})
    assert 'E-mail ou senha incorretos' in resp.content.decode()


@pytest.mark.django_db
def test_login_de_profissional_pendente_avisa(client, pendente):
    resp = client.post(reverse('login'), {'username': 'pend@ex.com', 'password': SENHA}, follow=True)
    html = resp.content.decode()
    assert 'Você entrou' in html
    assert html.count('aguardando aprovação de um administrador') == 1  # cartão da home, sem repetir


@pytest.mark.django_db
def test_login_de_pendente_indo_para_outra_pagina_tambem_avisa(client, pendente):
    resp = client.post(reverse('login') + '?next=/preferencias/', {'username': 'pend@ex.com', 'password': SENHA,
                                                                   'next': '/preferencias/'})
    assert any('aguardando a aprovação' in m for m in _msgs(resp))


@pytest.mark.django_db
def test_logout_avisa(client, pendente):
    client.force_login(pendente)
    resp = client.post(reverse('logout'))
    assert any('Você saiu' in m for m in _msgs(resp))


# RF03 - Esqueci minha senha (código de 6 dígitos) ---------------------------------------------------------

NOVA = 'Nova-senha-456'


def _pedir_codigo(client, email='pend@ex.com'):
    """Pede o código e devolve o que foi "enviado" por e-mail (ou None se nada saiu)."""
    with patch('apps.usuarios.services.recuperacao.enviar_codigo_recuperacao') as envio, \
            django_capture_on_commit_callbacks_ctx():
        resp = client.post(reverse('recuperar_senha'), {'email': email})
    assert resp.status_code == 302 and resp.url == reverse('recuperar_senha_codigo')
    return envio.call_args.args[1] if envio.called else None


def django_capture_on_commit_callbacks_ctx():
    from django.test import TestCase
    return TestCase.captureOnCommitCallbacks(execute=True)


def _enviar(client, codigo, senha=NOVA):
    return client.post(reverse('recuperar_senha_codigo'),
                       {'codigo': codigo, 'nova_senha1': senha, 'nova_senha2': senha})


@pytest.mark.django_db
def test_rf03_ca01_envia_codigo_de_6_digitos_e_guarda_so_o_hash(client, pendente):
    codigo = _pedir_codigo(client, 'PEND@ex.com')
    assert re.fullmatch(r'\d{6}', codigo)
    registro = CodigoVerificacao.objects.get()
    assert registro.user == pendente and codigo not in registro.codigo_hash  # RN03
    assert registro.expira_em - registro.criado_em <= timedelta(minutes=10, seconds=1)


@pytest.mark.django_db
def test_rf03_ca02_email_inexistente_tem_a_mesma_resposta_e_nao_envia(client):
    assert _pedir_codigo(client, 'ninguem@ex.com') is None
    assert not CodigoVerificacao.objects.exists()


@pytest.mark.django_db
def test_rf03_conta_desativada_nao_recebe_codigo(client, pendente):
    User.objects.update(is_active=False)
    assert _pedir_codigo(client) is None


@pytest.mark.django_db
def test_rf03_ca03_codigo_correto_troca_a_senha_e_invalida_o_codigo(client, pendente):
    codigo = _pedir_codigo(client)
    resp = _enviar(client, codigo)
    assert resp.status_code == 302 and resp.url == reverse('login')
    pendente.refresh_from_db()
    assert pendente.check_password(NOVA)
    assert CodigoVerificacao.objects.get().usado_em is not None
    # Uso único: o mesmo código não serve de novo.
    sessao = client.session
    sessao['recuperacao_senha_email'] = 'pend@ex.com'
    sessao.save()
    assert 'codigo' in _enviar(client, codigo, 'Outra-senha-789').context['form'].errors


@pytest.mark.django_db
def test_rf03_ca04_codigo_expirado_e_recusado(client, pendente):
    codigo = _pedir_codigo(client)
    CodigoVerificacao.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
    assert 'codigo' in _enviar(client, codigo).context['form'].errors
    pendente.refresh_from_db()
    assert pendente.check_password(SENHA)


@pytest.mark.django_db
def test_rf03_ca04_cinco_tentativas_erradas_invalidam_o_codigo(client, pendente):
    codigo = _pedir_codigo(client)
    errado = '000000' if codigo != '000000' else '111111'
    for _ in range(5):
        assert 'codigo' in _enviar(client, errado).context['form'].errors
    assert CodigoVerificacao.objects.get().tentativas == 5
    assert 'codigo' in _enviar(client, codigo).context['form'].errors  # nem o certo vale mais
    pendente.refresh_from_db()
    assert pendente.check_password(SENHA)


@pytest.mark.django_db
def test_rf03_rn04_senha_fraca_e_recusada_sem_gastar_tentativa(client, pendente):
    codigo = _pedir_codigo(client)
    resp = _enviar(client, codigo, '12345678')
    assert 'nova_senha1' in resp.context['form'].errors
    assert CodigoVerificacao.objects.get().tentativas == 0
    assert _enviar(client, codigo).url == reverse('login')


@pytest.mark.django_db
def test_rf03_rn06_novo_pedido_invalida_o_codigo_anterior(client, pendente):
    primeiro = _pedir_codigo(client)
    cache.clear()  # passa o limite de 5 min do H2; aqui se testa só a RN06
    segundo = _pedir_codigo(client)
    if primeiro != segundo:
        assert 'codigo' in _enviar(client, primeiro).context['form'].errors
    assert _enviar(client, segundo).url == reverse('login')


@pytest.mark.django_db
def test_rf03_tela_do_codigo_sem_pedido_volta_ao_inicio(client):
    assert client.get(reverse('recuperar_senha_codigo')).url == reverse('recuperar_senha')


@pytest.mark.django_db
def test_rf03_email_do_codigo_mostra_o_codigo_e_a_validade():
    from .services.email import enviar_codigo_recuperacao
    with patch('apps.usuarios.services.email.enviar_email') as envio:
        enviar_codigo_recuperacao('x@ex.com', '123456')
    para, _, html = envio.call_args.args
    assert para == 'x@ex.com' and '123456' in html and '10 minutos' in html


@pytest.mark.django_db
def test_login_tem_link_esqueci_minha_senha(client):
    html = client.get(reverse('login')).content.decode()
    assert 'Esqueci minha senha' in html and reverse('recuperar_senha') in html


# Documentos legais e menu ----------------------------------------------------------------------------------

@pytest.mark.django_db
def test_privacidade_menciona_brevo_e_contato(client, settings):
    settings.CONTATO_EMAIL = 'dpo@ex.com'
    html = client.get(reverse('privacidade')).content.decode()
    assert 'Brevo' in html and 'dpo@ex.com' in html


@pytest.mark.django_db
def test_termos_tem_versao_e_aviso_de_que_nao_substitui_tratamento(client):
    html = client.get(reverse('termos')).content.decode()
    assert 'Versão 2.0' in html and 'não substitui consulta' in html


@pytest.mark.django_db
def test_link_do_painel_de_gestao_so_para_quem_tem_permissao(client):
    staff = User.objects.create_user('s@ex.com', 'Staff', SENHA, role=User.Role.ADMIN, is_staff=True)
    client.force_login(staff)
    assert 'Painel de Gestão' not in client.get(reverse('preferencias')).content.decode()
    client.force_login(User.objects.create_superuser('a@ex.com', 'Admin', SENHA))
    assert 'Painel de Gestão' in client.get(reverse('preferencias')).content.decode()


@pytest.mark.django_db
def test_h2_recusa_muitos_pedidos_de_senha(client, pendente):
    assert _pedir_codigo(client) is not None
    assert _pedir_codigo(client) is None  # mesmo e-mail dentro de 5 min: nada novo é gerado nem enviado
    assert CodigoVerificacao.objects.count() == 1
    # E-mail sem conta recebe o mesmo bloqueio: o limite não revela se a conta existe.
    _pedir_codigo(client, 'ninguem@ex.com')
    resp = client.post(reverse('recuperar_senha'), {'email': 'ninguem@ex.com'})
    assert resp.url == reverse('recuperar_senha_codigo')
    assert any('Aguarde 5 minutos' in m for m in _msgs(resp))
    cache.clear()  # passados os 5 minutos
    assert _pedir_codigo(client) is not None and CodigoVerificacao.objects.count() == 2
