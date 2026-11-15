"""Comando popular_demo: cria o cenário de demonstração, não duplica e apaga só o que criou."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import timezone

from apps.acompanhamento.models import Atribuicao, LogAcesso, PedidoAjuda, RegistroEvolucao
from apps.atividades.models import Atividade
from apps.salas.models import ParticipacaoVideochamada, Sala
from apps.usuarios.models import Aluno, User

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path, monkeypatch):
    settings.MEDIA_ROOT = tmp_path
    monkeypatch.delenv('DATABASE_URL', raising=False)  # o teste roda no banco de teste, nunca no do site


def popular(*args):
    call_command('popular_demo', *args, stdout=StringIO())


@pytest.mark.django_db
def test_cria_o_cenario_completo_sem_nada_no_futuro():
    popular()
    demo = User.objects.filter(email__endswith='@example.com')
    assert demo.count() == 15
    assert Aluno.objects.filter(user__in=demo, profissional__isnull=True).count() == 2
    assert Sala.objects.count() == 7
    assert RegistroEvolucao.objects.count() > 15
    assert Atribuicao.objects.filter(prazo__lt=timezone.localdate()).exclude(status='concluida').exists()
    assert PedidoAjuda.objects.filter(respondido_em__isnull=True).count() == 2
    assert Atividade.objects.filter(publicacao=Atividade.Publicacao.EM_ANALISE).count() == 1
    assert ParticipacaoVideochamada.objects.exclude(saiu_em=None).exists()
    assert not LogAcesso.objects.filter(ocorrido_em__gt=timezone.now()).exists()
    pdf = Atividade.objects.exclude(arquivo_pdf='').first().arquivo_pdf
    with pdf.open('rb') as arquivo:
        assert arquivo.read(5) == b'%PDF-'


@pytest.mark.django_db
def test_telas_principais_abrem_com_os_dados(client):
    popular()
    paginas = {
        'coordenacao': ['painel_gestao', 'auditoria'],
        'mariana': ['painel', 'alunos_profissional', 'salas', 'dashboard_profissional', 'vincular_alunos'],
        'pedro': ['aluno_painel', 'aluno_atividades', 'historico_aluno', 'minha_equipe', 'anotacoes_aluno'],
    }
    for quem, nomes in paginas.items():
        client.force_login(User.objects.get(email=f'{quem}@example.com'))
        for nome in nomes:
            assert client.get(reverse(nome)).status_code == 200, (quem, nome)
    sala = Sala.objects.get(aluno__user__email='pedro@example.com')
    client.force_login(sala.dono.user)
    resposta = client.get(reverse('sala', args=[sala.pk]))
    assert 'Treino de sons com a letra R' in resposta.content.decode()


@pytest.mark.django_db
def test_nao_duplica_e_apaga_so_os_dados_de_demonstracao(django_user_model):
    real = django_user_model.objects.create_user('real@escola.br', 'Pessoa Real', 'Senha-forte-123',
                                                 role=User.Role.ADMIN)
    LogAcesso.objects.create(user=real, acao='Entrou no sistema', categoria=LogAcesso.Categoria.AUTENTICACAO)
    popular()
    with pytest.raises(CommandError, match='já existem'):
        popular()
    popular('--apagar')
    assert list(User.objects.values_list('email', flat=True)) == ['real@escola.br']
    assert LogAcesso.objects.count() == 1
    assert not Atividade.objects.exists() and not Sala.objects.exists()
    popular()  # depois de apagar, pode criar de novo
    assert User.objects.count() == 16


@pytest.mark.django_db
def test_no_banco_do_site_exige_pdfs_no_banco(monkeypatch, settings):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://usuario@servidor/banco')
    settings.ARMAZENAMENTO_ARQUIVOS = 'disco'
    with pytest.raises(CommandError, match='ARMAZENAMENTO_ARQUIVOS=banco'):
        popular()
    assert not User.objects.exists()
