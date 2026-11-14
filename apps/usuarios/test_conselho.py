"""Profissão e registro no conselho: cadastro, validação, conferência pelo gestor e revogação."""
from unittest.mock import patch

import pytest
from django.urls import reverse

from .models import Profissional, User

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'


def _dados(**extra):
    return {'name': 'Nova', 'email': 'nova@ex.com', 'password1': SENHA, 'password2': SENHA, 'role': 'profissional',
            'aceite_termos': 'on', **extra}


def _cadastrar(client, **extra):
    with patch('apps.usuarios.views.enviar_boas_vindas'):
        return client.post(reverse('cadastro'), _dados(**extra))


@pytest.mark.django_db
def test_psicologa_cadastra_com_crp_e_area(client):
    resp = _cadastrar(client, profissao='psicologia', uf_registro='SP', numero_registro=' 06/123456 ',
                      area_atuacao='ABA')
    assert resp.status_code == 302
    prof = Profissional.objects.get()
    assert (prof.profissao, prof.uf_registro, prof.numero_registro) == ('psicologia', 'SP', '06/123456')
    assert prof.especialidade == 'Psicologia · ABA'
    assert prof.registro_formatado == 'CRP-SP 06/123456' and prof.conselho[0] == 'CRP'


@pytest.mark.django_db
@pytest.mark.parametrize('profissao, numero', [('terapia_ocupacional', '12345-to'), ('fonoaudiologia', '2-12345')])
def test_terapeutas_cadastram_com_o_conselho_certo(client, profissao, numero):
    assert _cadastrar(client, profissao=profissao, uf_registro='MG', numero_registro=numero).status_code == 302
    prof = Profissional.objects.get()
    assert prof.numero_registro == numero.upper()
    assert prof.conselho[0] == {'terapia_ocupacional': 'CREFITO', 'fonoaudiologia': 'CRFa'}[profissao]


@pytest.mark.django_db
def test_pedagogia_nao_pede_registro(client):
    assert _cadastrar(client, profissao='pedagogia').status_code == 302
    prof = Profissional.objects.get()
    assert prof.conselho is None and prof.numero_registro == ''


@pytest.mark.django_db
@pytest.mark.parametrize('extra, campo', [
    ({}, 'profissao'),
    ({'profissao': 'psicologia'}, 'uf_registro'),
    ({'profissao': 'psicologia', 'uf_registro': 'SP'}, 'numero_registro'),
    ({'profissao': 'psicologia', 'uf_registro': 'SP', 'numero_registro': 'abc'}, 'numero_registro'),
    ({'profissao': 'psicologia', 'uf_registro': 'XX', 'numero_registro': '06/1234'}, 'uf_registro'),
])
def test_dados_do_registro_sao_validados(client, extra, campo):
    resp = _cadastrar(client, **extra)
    assert resp.status_code == 200 and campo in resp.context['form'].errors
    assert not User.objects.exists()


@pytest.mark.django_db
def test_mesmo_registro_nao_serve_para_duas_contas(client):
    _cadastrar(client, profissao='psicologia', uf_registro='SP', numero_registro='06/123456')
    client.logout()
    resp = _cadastrar(client, email='outra@ex.com', profissao='psicologia', uf_registro='SP',
                      numero_registro='06/123456')
    assert 'já está cadastrado' in str(resp.context['form'].errors['numero_registro'])
    assert Profissional.objects.count() == 1


@pytest.fixture
def gestor(db):
    return User.objects.create_superuser('adm@ex.com', 'Adm', SENHA)


@pytest.mark.django_db
def test_painel_mostra_registro_e_link_do_conselho(client, gestor):
    _cadastrar(client, profissao='psicologia', uf_registro='SP', numero_registro='06/123456')
    client.force_login(gestor)
    html = client.get(reverse('painel_gestao')).content.decode()
    assert 'CRP-SP 06/123456' in html and 'https://cadastro.cfp.org.br/' in html


@pytest.mark.django_db
def test_aprovar_registra_quem_e_quando_e_revogar_corta_o_acesso(client, gestor):
    _cadastrar(client, profissao='pedagogia')
    prof = Profissional.objects.get()
    client.force_login(gestor)
    client.post(reverse('aprovar_profissional_gestao', args=[prof.pk]))
    prof.refresh_from_db()
    assert prof.is_approved and prof.aprovado_por == gestor and prof.aprovado_em

    client.force_login(prof.user)
    assert client.get(reverse('painel')).status_code == 200
    client.force_login(gestor)
    client.post(reverse('revogar_profissional_gestao', args=[prof.pk]))
    prof.refresh_from_db()
    assert not prof.is_approved
    client.force_login(prof.user)
    assert client.get(reverse('painel')).url == reverse('home')


@pytest.mark.django_db
def test_so_gestor_revoga(client, gestor):
    _cadastrar(client, profissao='pedagogia')
    prof = Profissional.objects.get()
    Profissional.objects.filter(pk=prof.pk).update(is_approved=True)
    client.force_login(prof.user)
    assert client.post(reverse('revogar_profissional_gestao', args=[prof.pk])).status_code == 403
    prof.refresh_from_db()
    assert prof.is_approved
