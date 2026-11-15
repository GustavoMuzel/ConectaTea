"""Cadastro: celular do responsável com 11 números e botão "Mostrar" nos campos de senha."""

import pytest
from django.urls import reverse

from .models import Aluno, User

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'


def cadastrar(client, role='aluno', **extra):
    dados = {'name': 'Novo', 'email': 'novo@ex.com', 'password1': SENHA, 'password2': SENHA, 'role': role,
             'aceite_termos': 'on', 'birth_date': '2011-05-01', 'guardian_name': 'Resp',
             'guardian_email': 'resp@ex.com', 'consentimento_responsavel': 'on', **extra}
    return client.post(reverse('cadastro'), dados)


@pytest.mark.django_db
@pytest.mark.parametrize('digitado, gravado', [
    ('11999999999', '(11) 99999-9999'),
    ('(21) 98765-4321', '(21) 98765-4321'),
    ('21 98765 4321', '(21) 98765-4321'),
    ('+55 (21) 98765-4321', '(21) 98765-4321'),
])
def test_celular_com_11_numeros_e_gravado_formatado(client, digitado, gravado):
    cadastrar(client, guardian_phone=digitado)
    assert Aluno.objects.get(user__email='novo@ex.com').guardian_phone == gravado


@pytest.mark.django_db
@pytest.mark.parametrize('digitado, aviso', [
    ('1199999999', 'Você digitou 10'),
    ('119999999999', 'Você digitou 12'),
    ('9999-9999', 'Você digitou 8'),
    ('01987654321', 'o DDD não começa com 0'),
    ('11887654321', 'começa com 9'),
    ('11 9abc8765432', 'Use só números'),
])
def test_celular_fora_do_formato_nao_cria_conta(client, digitado, aviso):
    resposta = cadastrar(client, guardian_phone=digitado)
    assert aviso in resposta.content.decode()
    assert not User.objects.filter(email='novo@ex.com').exists()


@pytest.mark.django_db
def test_celular_vazio_pede_preenchimento(client):
    resposta = cadastrar(client, guardian_phone='')
    assert 'Preencha este campo.' in resposta.content.decode()
    assert not User.objects.exists()


@pytest.mark.django_db
def test_profissional_nao_e_barrado_pelo_celular_escondido(client):
    """O bloco do aluno fica escondido para profissional: o que estiver nele não pode impedir o cadastro."""
    cadastrar(client, role='profissional', profissao='pedagogia', guardian_phone='123')
    assert User.objects.get(email='novo@ex.com').is_profissional_pendente


@pytest.mark.django_db
@pytest.mark.parametrize('pagina', ['login', 'cadastro', 'recuperar_senha_codigo'])
def test_paginas_com_senha_carregam_o_botao_mostrar(client, pagina):
    resposta = client.get(reverse(pagina), follow=True)
    html = resposta.content.decode()
    assert 'js/mostrar-senha.js' in html
