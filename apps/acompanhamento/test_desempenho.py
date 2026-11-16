"""RNF03: cada tela faz poucas consultas ao banco, e esse número não cresce com a quantidade de dados.

Compara, com o cenário do popular_demo, quem tem mais dados (Mariana com 4 alunos; Pedro com o histórico mais
longo) com quem tem menos (Juliana com 1 aluno; Mateus). Se uma tela passar a fazer uma consulta por aluno ou por
atividade (o problema "N+1"), os números deixam de ser iguais e o teste falha.
"""

from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, User

pytestmark = pytest.mark.integration

LIMITE_DE_CONSULTAS = 15


@pytest.fixture
def cenario(settings, tmp_path, monkeypatch, db):
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.delenv('DATABASE_URL', raising=False)
    call_command('popular_demo', stdout=StringIO())


def contar_consultas(client, chave, url):
    client.force_login(User.objects.get(email=f'{chave}@example.com'))
    client.get(url)  # a primeira visita cria a sessão e as preferências; a medida é da segunda
    with CaptureQueriesContext(connection) as consultas:
        assert client.get(url).status_code == 200, url
    return len(consultas.captured_queries)


def paginas_do_profissional(chave_prof, chave_aluno):
    aluno = Aluno.objects.get(user__email=f'{chave_aluno}@example.com')
    atividade = Atividade.objects.filter(profissional__user__email=f'{chave_prof}@example.com', aluno=None).first()
    return {
        'biblioteca': reverse('painel'),
        'meus alunos': reverse('alunos_profissional'),
        'vincular alunos': reverse('vincular_alunos'),
        'salas': reverse('salas'),
        'sala do aluno': reverse('sala', args=[aluno.sala.pk]),
        'evolução do aluno': reverse('evolucao_aluno', args=[aluno.pk]),
        'relatórios': reverse('dashboard_profissional'),
        'distribuir atividade': reverse('distribuir_atividade', args=[atividade.pk]),
    }


PAGINAS_DO_ALUNO = ['aluno_painel', 'aluno_atividades', 'historico_aluno', 'anotacoes_aluno', 'minha_equipe']


def test_telas_do_profissional_nao_crescem_com_o_numero_de_alunos(cenario, client):
    muitos = paginas_do_profissional('mariana', 'pedro')
    poucos = paginas_do_profissional('juliana', 'mateus')
    for nome in muitos:
        com_mais_dados = contar_consultas(client, 'mariana', muitos[nome])
        com_menos_dados = contar_consultas(client, 'juliana', poucos[nome])
        assert com_mais_dados == com_menos_dados, nome
        assert com_mais_dados <= LIMITE_DE_CONSULTAS, nome


def test_telas_do_aluno_nao_crescem_com_o_historico(cenario, client):
    for nome in PAGINAS_DO_ALUNO:
        url = reverse(nome)
        com_mais_dados = contar_consultas(client, 'pedro', url)
        assert com_mais_dados == contar_consultas(client, 'mateus', url), nome
        assert com_mais_dados <= LIMITE_DE_CONSULTAS, nome


def test_telas_do_gestor_fazem_poucas_consultas(cenario, client):
    for url in (reverse('painel_gestao'), reverse('auditoria'), reverse('auditoria') + '?aba=videochamadas'):
        assert contar_consultas(client, 'coordenacao', url) <= LIMITE_DE_CONSULTAS, url
