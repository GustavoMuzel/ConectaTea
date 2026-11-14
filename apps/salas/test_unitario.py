"""Testes unitários da sala da equipe: senha de acesso e quem participa. Sem banco e sem rede."""

import pytest

from apps.usuarios.models import Aluno, Profissional, User

from .forms import EntrarSalaForm
from .models import ALFABETO_SENHA, Sala, gerar_senha_sala

pytestmark = pytest.mark.unit


# Senha da sala -------------------------------------------------------------------------------------------

def test_senha_tem_6_caracteres_do_alfabeto_permitido():
    for _ in range(200):
        senha = gerar_senha_sala()
        assert len(senha) == 6
        assert set(senha) <= set(ALFABETO_SENHA)


def test_alfabeto_nao_tem_caracteres_que_se_confundem_ao_ditar():
    for confuso in '0O1IL':
        assert confuso not in ALFABETO_SENHA


def test_senhas_sao_aleatorias():
    assert len({gerar_senha_sala() for _ in range(50)}) > 45


@pytest.mark.parametrize('digitada, esperada', [
    ('abc234', 'ABC234'),
    ('  ab c2 34 ', 'ABC234'),
    ('ABC234', 'ABC234'),
])
def test_senha_digitada_e_normalizada(digitada, esperada):
    form = EntrarSalaForm(data={'senha': digitada})
    assert form.is_valid()
    assert form.cleaned_data['senha'] == esperada


def test_senha_vazia_e_recusada():
    assert not EntrarSalaForm(data={'senha': '   '}).is_valid()


# Quem participa da sala (os casos que não dependem da lista de membros) ------------------------------------

@pytest.fixture
def sala():
    aluno_user = User(id=1, email='aluno@ex.com', name='Aluno', role=User.Role.ALUNO)
    dono = Profissional(id=10, user=User(id=2, email='dono@ex.com', name='Dono', role=User.Role.PROFISSIONAL))
    aluno = Aluno(id=5, user=aluno_user, profissional_id=10)
    return Sala(aluno=aluno, dono=dono)


def test_o_proprio_aluno_participa(sala):
    assert sala.participa(User(id=1)) is True


def test_o_dono_participa_enquanto_acompanha_o_aluno(sala):
    assert sala.participa(User(id=2)) is True


def test_sala_fica_dormente_quando_o_aluno_muda_de_profissional(sala):
    sala.aluno.profissional_id = 99  # o vínculo agora é com outro profissional
    assert sala.participa(User(id=2)) is False
    assert sala.participa(User(id=3)) is False


def test_o_aluno_continua_na_propria_sala_mesmo_com_a_troca(sala):
    sala.aluno.profissional_id = None
    assert sala.participa(User(id=1)) is True


def test_sala_aparece_pelo_nome_do_aluno(sala):
    assert str(sala) == 'Sala de Aluno'
