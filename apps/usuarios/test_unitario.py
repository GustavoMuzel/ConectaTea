"""Testes unitários de usuários: regras de perfil, LGPD, recuperação de senha, permissões e e-mail.

Sem banco e sem rede: os objetos são criados em memória (sem .save()) e a API do Brevo é simulada.
"""

import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.storage.cookie import CookieStorage
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from .context_processors import preferencias
from .forms import CadastroForm, CodigoNovaSenhaForm
from .mixins import AlunoRequiredMixin, GestorRequiredMixin, ProfissionalRequiredMixin
from .models import Aluno, CodigoVerificacao, Profissional, User
from .services.email import (BREVO_URL, enviar_boas_vindas, enviar_codigo_recuperacao, enviar_email,
                             enviar_notificacao_aluno_criado)

pytestmark = pytest.mark.unit


def profissional(aprovado=True):
    user = User(email='prof@ex.com', name='Prof', role=User.Role.PROFISSIONAL)
    user.profissional = Profissional(especialidade='Psicologia', is_approved=aprovado)
    return user


def aluno(profissional_id=None):
    user = User(email='aluno@ex.com', name='Aluno', role=User.Role.ALUNO)
    user.aluno = Aluno(profissional_id=profissional_id, birth_date=datetime.date(2011, 1, 1),
                       guardian_name='Resp', guardian_phone='11999999999', guardian_email='resp@ex.com')
    return user


# Perfis ---------------------------------------------------------------------------------------------------

def test_profissional_aprovado_atua():
    user = profissional(aprovado=True)
    assert user.is_profissional is True
    assert user.is_profissional_pendente is False


def test_profissional_pendente_nao_atua_ate_a_aprovacao():
    user = profissional(aprovado=False)
    assert user.is_profissional is False
    assert user.is_profissional_pendente is True


def test_perfil_profissional_sem_cadastro_de_profissional_nao_atua():
    user = User(email='p@ex.com', name='P', role=User.Role.PROFISSIONAL)
    assert user.is_profissional is False
    assert user.is_profissional_pendente is False


def test_aluno_sem_profissional_esta_sem_vinculo():
    user = aluno(profissional_id=None)
    assert user.is_aluno is True
    assert user.is_aluno_sem_vinculo is True


def test_aluno_vinculado_nao_esta_sem_vinculo():
    assert aluno(profissional_id=7).is_aluno_sem_vinculo is False


def test_perfis_nao_se_misturam():
    assert aluno(profissional_id=7).is_profissional is False
    assert profissional().is_aluno is False


# LGPD: e-mail parcial do aluno -----------------------------------------------------------------------------

@pytest.mark.parametrize('email, esperado', [
    ('maria@ex.com', 'm***@ex.com'),
    ('a@escola.org.br', 'a***@escola.org.br'),
])
def test_email_parcial_esconde_o_endereco(email, esperado):
    assert User(email=email).email_parcial == esperado


def test_email_parcial_nao_mostra_o_nome_inteiro():
    assert 'maria' not in User(email='maria.silva@ex.com').email_parcial


# Criação de usuário (o .save() é simulado: aqui só a regra do manager importa) -----------------------------

def test_criar_usuario_sem_email_e_recusado():
    with pytest.raises(ValueError, match='e-mail é obrigatório'):
        User.objects.create_user('', 'Sem E-mail', 'Senha-forte-123')


def test_criar_usuario_normaliza_o_email_e_guarda_so_o_hash():
    with patch.object(User, 'save'):
        user = User.objects.create_user('  Ana@Ex.COM ', 'Ana', 'Senha-forte-123', role=User.Role.ALUNO)
    assert user.email == 'ana@ex.com'
    assert user.password != 'Senha-forte-123'
    assert user.check_password('Senha-forte-123')


def test_superusuario_nasce_administrador():
    with patch.object(User, 'save'):
        user = User.objects.create_superuser('adm@ex.com', 'Adm', 'Senha-forte-123')
    assert user.role == User.Role.ADMIN
    assert user.is_staff and user.is_superuser


# Recuperação de senha: validade do código (RF03) -----------------------------------------------------------

def codigo(**campos):
    padrao = {'expira_em': timezone.now() + CodigoVerificacao.VALIDADE, 'tentativas': 0, 'usado_em': None}
    return CodigoVerificacao(**{**padrao, **campos})


def test_codigo_novo_e_valido():
    assert codigo().valido is True


def test_codigo_vale_dez_minutos():
    assert CodigoVerificacao.VALIDADE == datetime.timedelta(minutes=10)


def test_codigo_expirado_nao_vale():
    assert codigo(expira_em=timezone.now() - datetime.timedelta(seconds=1)).valido is False


def test_codigo_usado_nao_vale_de_novo():
    assert codigo(usado_em=timezone.now()).valido is False


@pytest.mark.parametrize('tentativas, valido', [(0, True), (4, True), (5, False), (6, False)])
def test_codigo_deixa_de_valer_na_quinta_tentativa_errada(tentativas, valido):
    assert codigo(tentativas=tentativas).valido is valido


@pytest.mark.parametrize('digitado', ['12345', '1234567', 'abcdef', '12 345', ''])
def test_codigo_precisa_ter_6_numeros(digitado):
    form = CodigoNovaSenhaForm(data={'codigo': digitado, 'nova_senha1': 'Senha-forte-123',
                                     'nova_senha2': 'Senha-forte-123'})
    assert not form.is_valid()
    assert 'codigo' in form.errors


def test_senhas_novas_diferentes_sao_recusadas():
    form = CodigoNovaSenhaForm(data={'codigo': '123456', 'nova_senha1': 'Senha-forte-123',
                                     'nova_senha2': 'Senha-forte-124'})
    assert not form.is_valid()
    assert form.errors['nova_senha2'] == ['As duas senhas não são iguais.']


def test_formulario_de_senha_nova_valido():
    form = CodigoNovaSenhaForm(data={'codigo': '123456', 'nova_senha1': 'Senha-forte-123',
                                     'nova_senha2': 'Senha-forte-123'})
    assert form.is_valid()


@pytest.mark.parametrize('senha', ['12345678', 'qwerty123', 'curta1!', 'joaosilva2026'])
def test_senha_nova_fraca_e_recusada(senha):
    """RN04: mesmos validadores do cadastro (numérica, comum, curta ou parecida com os dados da conta)."""
    form = CodigoNovaSenhaForm(data={'codigo': '123456', 'nova_senha1': senha, 'nova_senha2': senha})
    assert form.is_valid()
    user = User(email='joaosilva2026@ex.com', name='João Silva')
    assert form.validar_senha_para(user) is False
    assert 'nova_senha1' in form.errors


def test_senha_nova_forte_e_aceita():
    form = CodigoNovaSenhaForm(data={'codigo': '123456', 'nova_senha1': 'Girassol-Azul-42',
                                     'nova_senha2': 'Girassol-Azul-42'})
    assert form.is_valid()
    assert form.validar_senha_para(User(email='ana@ex.com', name='Ana')) is True


# Cadastro ------------------------------------------------------------------------------------------------

def test_cadastro_publico_nao_oferece_o_perfil_admin():
    opcoes = [valor for valor, _ in CadastroForm().fields['role'].choices]
    assert opcoes == [User.Role.ALUNO, User.Role.PROFISSIONAL]
    assert User.Role.ADMIN not in opcoes


@pytest.mark.parametrize('dias, valido', [(-1, True), (0, False), (1, False)])
def test_data_de_nascimento_precisa_ser_anterior_a_hoje(dias, valido):
    form = CadastroForm()
    form.cleaned_data = {'birth_date': timezone.localdate() + datetime.timedelta(days=dias)}
    if valido:
        assert form.clean_birth_date() == form.cleaned_data['birth_date']
    else:
        with pytest.raises(ValidationError, match='anterior a hoje'):
            form.clean_birth_date()


def test_aceite_dos_termos_e_obrigatorio_no_cadastro():
    campo = CadastroForm().fields['aceite_termos']
    assert campo.required is True


# Permissões por perfil (mixins das views) ------------------------------------------------------------------

def mixin(classe, user, rf=None):
    view = classe()
    view.request = rf.get('/qualquer/') if rf else SimpleNamespace()
    view.request.user = user
    if rf:
        view.request._messages = CookieStorage(view.request)
    return view


def test_area_do_profissional_so_para_aprovados():
    assert mixin(ProfissionalRequiredMixin, profissional(aprovado=True)).test_func() is True
    assert mixin(ProfissionalRequiredMixin, profissional(aprovado=False)).test_func() is False
    assert mixin(ProfissionalRequiredMixin, aluno(7)).test_func() is False


def test_profissional_pendente_volta_ao_inicio_com_aviso(rf):
    resposta = mixin(ProfissionalRequiredMixin, profissional(aprovado=False), rf).handle_no_permission()
    assert resposta.status_code == 302
    assert resposta.url == reverse('home')


def test_aluno_na_area_do_profissional_recebe_403(rf):
    with pytest.raises(PermissionDenied):
        mixin(ProfissionalRequiredMixin, aluno(7), rf).handle_no_permission()


def test_visitante_vai_para_o_login(rf):
    resposta = mixin(ProfissionalRequiredMixin, AnonymousUser(), rf).handle_no_permission()
    assert resposta.status_code == 302
    assert resposta.url.startswith(reverse('login'))


def test_area_do_aluno_exige_vinculo():
    assert mixin(AlunoRequiredMixin, aluno(profissional_id=7)).test_func() is True
    assert mixin(AlunoRequiredMixin, aluno(profissional_id=None)).test_func() is False
    assert mixin(AlunoRequiredMixin, profissional()).test_func() is False


def test_aluno_sem_vinculo_volta_ao_inicio(rf):
    resposta = mixin(AlunoRequiredMixin, aluno(profissional_id=None), rf).handle_no_permission()
    assert resposta.url == reverse('home')


def test_gestao_aceita_superusuario():
    assert mixin(GestorRequiredMixin, User(is_staff=True, is_superuser=True)).test_func() is True


def test_gestao_exige_permissao_alem_de_is_staff():
    staff = User(is_staff=True)
    with patch.object(User, 'has_perm', return_value=False) as tem:
        assert mixin(GestorRequiredMixin, staff).test_func() is False
    tem.assert_called_once_with('usuarios.change_profissional')
    with patch.object(User, 'has_perm', return_value=True):
        assert mixin(GestorRequiredMixin, staff).test_func() is True


def test_gestao_recusa_quem_nao_e_staff():
    assert mixin(GestorRequiredMixin, profissional()).test_func() is False


# Preferências de acessibilidade ---------------------------------------------------------------------------

def test_visitante_usa_as_preferencias_padrao(settings):
    settings.CONTATO_EMAIL = 'contato@ex.com'
    contexto = preferencias(SimpleNamespace(user=AnonymousUser()))
    assert contexto == {'prefs': None, 'contato_email': 'contato@ex.com'}


def test_usuario_que_nunca_salvou_preferencias_usa_o_padrao():
    assert preferencias(SimpleNamespace(user=aluno(7)))['prefs'] is None


# E-mail pelo Brevo (API simulada) --------------------------------------------------------------------------

@pytest.fixture
def brevo(settings):
    settings.BREVO_API_KEY = 'chave-de-teste'
    settings.BREVO_SENDER_EMAIL = 'nao-responda@ex.com'
    settings.BREVO_SENDER_NAME = 'ConectaTEA'
    with patch('apps.usuarios.services.email.requests.post') as post:
        yield post


def test_email_vai_para_a_api_do_brevo_com_a_chave_e_timeout(brevo):
    assert enviar_email('ana@ex.com', 'Assunto', '<p>Oi</p>') is True
    assert brevo.call_args.args[0] == BREVO_URL
    kwargs = brevo.call_args.kwargs
    assert kwargs['headers']['api-key'] == 'chave-de-teste'
    assert kwargs['timeout'] == (3, 5)
    assert kwargs['json'] == {
        'sender': {'email': 'nao-responda@ex.com', 'name': 'ConectaTEA'},
        'to': [{'email': 'ana@ex.com'}], 'subject': 'Assunto', 'htmlContent': '<p>Oi</p>',
    }


def test_sem_chave_do_brevo_nada_e_enviado(settings):
    settings.BREVO_API_KEY = ''
    with patch('apps.usuarios.services.email.requests.post') as post:
        assert enviar_email('ana@ex.com', 'Assunto', '<p>Oi</p>') is False
    post.assert_not_called()


@pytest.mark.parametrize('falha', [requests.Timeout('lento'), requests.ConnectionError('fora do ar')])
def test_falha_de_rede_no_brevo_nao_quebra_o_fluxo(brevo, falha):
    brevo.side_effect = falha
    assert enviar_email('ana@ex.com', 'Assunto', '<p>Oi</p>') is False


def test_erro_http_do_brevo_conta_como_falha(brevo):
    brevo.return_value.raise_for_status.side_effect = requests.HTTPError('401 Key not found')
    assert enviar_email('ana@ex.com', 'Assunto', '<p>Oi</p>') is False


def test_boas_vindas_nao_usa_o_nome_digitado_no_cadastro(brevo):
    user = User(email='ana@ex.com', name='<a href="http://golpe.example">Clique</a>', role=User.Role.ALUNO)
    assert enviar_boas_vindas(user) is True
    html = brevo.call_args.kwargs['json']['htmlContent']
    assert 'golpe.example' not in html
    assert '<strong>Aluno</strong>' in html


def test_boas_vindas_do_profissional_avisa_sobre_a_aprovacao(brevo):
    enviar_boas_vindas(profissional())
    assert 'aprovadas por um administrador' in brevo.call_args.kwargs['json']['htmlContent']


def test_boas_vindas_do_aluno_nao_fala_de_aprovacao(brevo):
    enviar_boas_vindas(aluno(7))
    assert 'aprovadas por um administrador' not in brevo.call_args.kwargs['json']['htmlContent']


def test_aviso_ao_responsavel_vai_para_o_email_dele_com_a_data_do_consentimento(brevo):
    user = aluno(7)
    user.aluno.consentimento_data = datetime.datetime(2026, 9, 27, 13, 30, tzinfo=datetime.timezone.utc)
    assert enviar_notificacao_aluno_criado(user) is True
    enviado = brevo.call_args.kwargs['json']
    assert enviado['to'] == [{'email': 'resp@ex.com'}]
    assert '27/09/2026 10:30' in enviado['htmlContent']  # horário de Brasília


def test_sem_consentimento_registrado_o_responsavel_nao_recebe_aviso(brevo):
    assert enviar_notificacao_aluno_criado(aluno(7)) is False
    brevo.assert_not_called()


def test_email_de_recuperacao_leva_o_codigo(brevo):
    assert enviar_codigo_recuperacao('ana@ex.com', '042137') is True
    assert '042137' in brevo.call_args.kwargs['json']['htmlContent']


def test_codigo_so_aparece_no_log_em_desenvolvimento(settings, caplog):
    settings.BREVO_API_KEY = ''
    settings.DEBUG = False
    enviar_codigo_recuperacao('ana@ex.com', '042137')
    assert '042137' not in caplog.text
    settings.DEBUG = True
    with caplog.at_level('INFO', logger='apps.usuarios.services.email'):
        enviar_codigo_recuperacao('ana@ex.com', '042137')
    assert '042137' in caplog.text
