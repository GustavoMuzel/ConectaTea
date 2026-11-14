"""Início do aluno: alerta das atividades em aberto, números e contador no menu."""
import datetime

import pytest
from django.urls import reverse

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atribuicao, RegistroEvolucao

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'
HOJE = datetime.date.today()


@pytest.fixture
def cenario(client, db):
    pu = User.objects.create_user('p@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    prof = Profissional.objects.create(user=pu, especialidade='Psicologia', is_approved=True)
    au = User.objects.create_user('a@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    aluno = Aluno.objects.create(user=au, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                 guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')
    client.force_login(au)
    return {'prof': prof, 'aluno': aluno}


def _distribuir(c, titulo, prazo=None):
    atividade = Atividade.objects.create(profissional=c['prof'], title=titulo, category='x')
    Atribuicao.objects.create(atividade=atividade, aluno=c['aluno'], profissional=c['prof'], prazo=prazo)
    return atividade


@pytest.mark.django_db
def test_tudo_em_dia(client, cenario):
    html = client.get(reverse('aluno_painel')).content.decode()
    assert 'Tudo em dia!' in html


@pytest.mark.django_db
def test_alerta_de_atividades_em_aberto_e_contador_no_menu(client, cenario):
    _distribuir(cenario, 'Cumprimentar', HOJE + datetime.timedelta(days=2))
    _distribuir(cenario, 'Pedir ajuda')
    resp = client.get(reverse('aluno_painel'))
    html = resp.content.decode()
    assert 'Você tem 2 atividades para fazer' in html
    assert 'O prazo de Cumprimentar' in html
    assert '2<span class="visually-hidden"> para fazer</span>' in html  # contador do menu


@pytest.mark.django_db
def test_alerta_de_atividade_atrasada(client, cenario):
    atrasada = _distribuir(cenario, 'Atrasada', HOJE - datetime.timedelta(days=1))
    resp = client.get(reverse('aluno_painel'))
    html = resp.content.decode()
    assert '1 atividade passou do prazo' in html
    assert reverse('confirmar_conclusao', args=[atrasada.pk]) in html
    assert resp.context['atrasadas'] == [atrasada]


@pytest.mark.django_db
def test_numeros_de_concluidas(client, cenario):
    feita = _distribuir(cenario, 'Feita')
    RegistroEvolucao.objects.create(aluno=cenario['aluno'], atividade=feita, status='concluida')
    resp = client.get(reverse('aluno_painel'))
    assert (resp.context['total_concluidas'], resp.context['concluidas_semana']) == (1, 1)
    assert resp.context['pendentes'] == []


@pytest.mark.django_db
def test_painel_so_para_aluno_com_vinculo(client, cenario):
    Aluno.objects.filter(pk=cenario['aluno'].pk).update(profissional=None)
    assert client.get(reverse('aluno_painel')).url == reverse('home')
    client.force_login(cenario['prof'].user)
    assert client.get(reverse('aluno_painel')).status_code == 403
