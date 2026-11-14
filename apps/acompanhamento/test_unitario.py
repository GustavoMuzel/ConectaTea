"""Testes unitários do acompanhamento: prazo da distribuição, conclusão e quem lê as anotações.

Sem banco e sem rede: o profissional é um dublê que devolve consultas vazias (.none() não consulta o banco).
"""

import datetime
from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .forms import AnotacaoForm, ConclusaoForm, DistribuicaoAtividadeForm
from .models import Anotacao, RegistroEvolucao

pytestmark = pytest.mark.unit


def form_distribuicao(prazo):
    vazio = SimpleNamespace(select_related=lambda *a: Aluno.objects.none())
    profissional = SimpleNamespace(
        atividades=SimpleNamespace(filter=lambda **filtros: Atividade.objects.none()),
        alunos=SimpleNamespace(filter=lambda **filtros: vazio),
    )
    form = DistribuicaoAtividadeForm(profissional=profissional)
    form.cleaned_data = {'prazo': prazo}
    return form


# Prazo da distribuição (RF07) -----------------------------------------------------------------------------

def test_prazo_e_opcional():
    assert form_distribuicao(None).clean_prazo() is None


def test_prazo_hoje_e_aceito():
    hoje = timezone.localdate()
    assert form_distribuicao(hoje).clean_prazo() == hoje


def test_prazo_no_futuro_e_aceito():
    amanha = timezone.localdate() + datetime.timedelta(days=1)
    assert form_distribuicao(amanha).clean_prazo() == amanha


def test_prazo_no_passado_e_recusado():
    ontem = timezone.localdate() - datetime.timedelta(days=1)
    with pytest.raises(ValidationError, match='não pode ser anterior a hoje'):
        form_distribuicao(ontem).clean_prazo()


# Conclusão da atividade pelo aluno -----------------------------------------------------------------------

def test_concluir_exige_resposta():
    form = ConclusaoForm(data={'resposta': '   '})
    assert not form.is_valid()
    assert form.errors['resposta'] == ['Escreva a sua resposta antes de concluir.']


def test_resposta_tem_limite_de_5000_caracteres():
    assert ConclusaoForm(data={'resposta': 'a' * 5000}).is_valid()
    assert not ConclusaoForm(data={'resposta': 'a' * 5001}).is_valid()


def test_resposta_valida():
    form = ConclusaoForm(data={'resposta': 'Conversei com o Pedro no intervalo.'})
    assert form.is_valid()
    assert form.cleaned_data['resposta'] == 'Conversei com o Pedro no intervalo.'


# Anotações (RF11) ----------------------------------------------------------------------------------------

@pytest.mark.parametrize('visibilidade', ['privada', 'compartilhada'])
def test_anotacao_aceita_as_duas_visibilidades(visibilidade):
    assert AnotacaoForm(data={'texto': 'Hoje foi bom.', 'visibilidade': visibilidade}).is_valid()


def test_anotacao_recusa_visibilidade_desconhecida():
    form = AnotacaoForm(data={'texto': 'Hoje foi bom.', 'visibilidade': 'publica'})
    assert not form.is_valid()
    assert 'visibilidade' in form.errors


def test_anotacao_nasce_privada():
    assert Anotacao().visibilidade == Anotacao.Visibilidade.PRIVADA


def test_quem_nao_participa_do_vinculo_nao_le_nenhuma_anotacao():
    """LGPD: um terceiro (outro profissional, outro aluno) recebe uma consulta vazia, sem ir ao banco."""
    profissional = Profissional(id=10, user=User(id=2))
    aluno = Aluno(id=5, user=User(id=1), profissional=profissional)
    visiveis = Anotacao.objects.visiveis_para(User(id=3), aluno)
    assert list(visiveis) == []


# Registro de evolução -------------------------------------------------------------------------------------

def test_registro_de_evolucao_nasce_pendente_e_com_data():
    registro = RegistroEvolucao()
    assert registro.status == RegistroEvolucao.Status.PENDENTE
    assert abs(registro.data_realizacao - timezone.now()) < datetime.timedelta(seconds=5)
