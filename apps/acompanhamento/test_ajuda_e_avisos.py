"""Pedido de ajuda, e-mails ao responsável (atividade enviada, atividades atrasadas) e o comando diário."""
import datetime
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atribuicao, PedidoAjuda

pytestmark = pytest.mark.integration

SENHA = 'Senha-forte-123'
HOJE = datetime.date.today()


@pytest.fixture
def c(db):
    pu = User.objects.create_user('p@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    prof = Profissional.objects.create(user=pu, especialidade='Psicologia', is_approved=True)
    au = User.objects.create_user('a@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    aluno = Aluno.objects.create(user=au, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                 guardian_name='R', guardian_phone='1', guardian_email='resp@ex.com')
    atividade = Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social')
    Atribuicao.objects.create(atividade=atividade, aluno=aluno, profissional=prof)
    return {'prof': prof, 'aluno': aluno, 'atividade': atividade}


@pytest.mark.django_db
def test_aluno_pede_ajuda_e_profissional_e_avisado(client, c, django_capture_on_commit_callbacks):
    client.force_login(c['aluno'].user)
    url = reverse('pedir_ajuda', args=[c['atividade'].pk])
    with patch('apps.usuarios.services.email.enviar_email') as envio, django_capture_on_commit_callbacks(execute=True):
        resp = client.post(url, {'mensagem': 'Não entendi a pergunta 2'})
        client.post(url, {'mensagem': 'de novo'})  # segundo clique não cria outro pedido nem outro e-mail
    assert resp.url == reverse('confirmar_conclusao', args=[c['atividade'].pk])
    pedido = PedidoAjuda.objects.get()
    assert pedido.mensagem == 'Não entendi a pergunta 2'
    assert envio.call_count == 1 and envio.call_args.args[0] == 'p@ex.com'
    assert 'Você pediu ajuda' in client.get(resp.url).content.decode()

    client.force_login(c['prof'].user)
    html = client.get(reverse('alunos_profissional')).content.decode()
    assert 'Pedidos de ajuda (1)' in html and 'Não entendi a pergunta 2' in html
    assert '1<span class="visually-hidden"> pedido de ajuda</span>' in html  # contador no menu
    client.post(reverse('ajuda_respondida', args=[pedido.pk]))
    pedido.refresh_from_db()
    assert pedido.respondido_em and pedido.respondido_por == c['prof'].user


@pytest.mark.django_db
def test_so_o_profissional_responsavel_marca_respondido(client, c):
    pedido = PedidoAjuda.objects.create(aluno=c['aluno'], atividade=c['atividade'])
    outro = User.objects.create_user('o@ex.com', 'Outro', SENHA, role=User.Role.PROFISSIONAL)
    Profissional.objects.create(user=outro, especialidade='X', is_approved=True)
    client.force_login(outro)
    assert client.post(reverse('ajuda_respondida', args=[pedido.pk])).status_code == 404


@pytest.mark.django_db
def test_nao_pede_ajuda_em_atividade_nao_distribuida(client, c):
    alheia = Atividade.objects.create(profissional=c['prof'], title='Não enviada', category='x')
    client.force_login(c['aluno'].user)
    assert client.post(reverse('pedir_ajuda', args=[alheia.pk])).status_code == 404


@pytest.mark.django_db
def test_distribuir_avisa_o_responsavel(client, c, django_capture_on_commit_callbacks):
    nova = Atividade.objects.create(profissional=c['prof'], title='Nova', category='x')
    client.force_login(c['prof'].user)
    prazo = HOJE + datetime.timedelta(days=5)
    with patch('apps.usuarios.services.email.enviar_email') as envio, django_capture_on_commit_callbacks(execute=True):
        client.post(reverse('distribuir_atividade', args=[nova.pk]),
                    {'atividade': nova.pk, 'alunos': [c['aluno'].pk], 'prazo': prazo.isoformat()})
    para, _, html = envio.call_args.args
    assert para == 'resp@ex.com' and prazo.strftime('%d/%m/%Y') in html
    assert 'Aluno' not in html  # sem nome do aluno no e-mail


@pytest.mark.django_db
def test_comando_avisa_so_quem_tem_atividade_atrasada(c):
    Atribuicao.objects.filter(atividade=c['atividade']).update(prazo=HOJE - datetime.timedelta(days=1))
    saida = StringIO()
    with patch('apps.acompanhamento.management.commands.avisar_atrasadas.enviar_aviso_atividades_atrasadas') as aviso:
        call_command('avisar_atrasadas', stdout=saida)
    aviso.assert_called_once_with(c['aluno'], 1)
    assert '1 aviso(s)' in saida.getvalue()
    with patch('apps.acompanhamento.management.commands.avisar_atrasadas.enviar_aviso_atividades_atrasadas') as aviso:
        call_command('avisar_atrasadas', '--simular', stdout=StringIO())
    aviso.assert_not_called()
