import datetime

import pytest
from django.db import IntegrityError
from django.urls import reverse

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .models import RegistroEvolucao

SENHA = 'Senha-forte-123'
LISTA = reverse('aluno_atividades')


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _aluno(email, prof):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


def _concluir(client, atividade):
    return client.post(reverse('concluir_atividade', args=[atividade.pk]), follow=True)


@pytest.fixture
def cenario(client):
    prof, outro = _prof('prof@ex.com'), _prof('outro@ex.com')
    aluno = _aluno('aluno@ex.com', prof)
    client.force_login(aluno.user)
    return {
        'aluno': aluno,
        'minha1': Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social'),
        'minha2': Atividade.objects.create(profissional=prof, title='Pedir <b>ajuda</b>', category='social'),
        'alheia': Atividade.objects.create(profissional=outro, title='Alheia', category='social'),
        'outro_aluno': _aluno('colega@ex.com', outro),
    }


@pytest.mark.django_db
def test_sem_login_redireciona(client):
    urls = [
        (LISTA, client.get),
        (reverse('confirmar_conclusao', args=[1]), client.get),
        (reverse('concluir_atividade', args=[1]), client.post),
    ]
    for url, metodo in urls:
        resp = metodo(url)
        assert resp.status_code == 302 and resp.url.startswith(reverse('login'))


@pytest.mark.django_db
def test_so_aluno_acessa(client, cenario):
    admin = User.objects.create_superuser('admin@ex.com', 'Admin', SENHA)
    sem_perfil = User.objects.create_user('semperfil@ex.com', 'X', SENHA, role=User.Role.ALUNO)
    for user in [cenario['minha1'].profissional.user, admin, sem_perfil]:
        client.force_login(user)
        assert client.get(LISTA).status_code == 403
        assert client.post(reverse('concluir_atividade', args=[cenario['minha1'].pk])).status_code == 403
    assert not RegistroEvolucao.objects.exists()


@pytest.mark.django_db
def test_lista_so_atividades_do_proprio_profissional_com_botao(client, cenario):
    resp = client.get(LISTA)
    html = resp.content.decode()

    assert resp.status_code == 200
    assert list(resp.context['atividades']) == [cenario['minha1'], cenario['minha2']]
    assert 'Alheia' not in html
    assert html.count('Concluir atividade') == 2
    assert 'Pedir &lt;b&gt;ajuda&lt;/b&gt;' in html  # título escapado
    # Botão só leva à tela de confirmação; o POST que conclui não sai direto da listagem.
    assert reverse('confirmar_conclusao', args=[cenario['minha1'].pk]) in html
    assert reverse('concluir_atividade', args=[cenario['minha1'].pk]) not in html


@pytest.mark.django_db
def test_tela_de_confirmacao_mostra_o_nome_e_nao_conclui_sozinha(client, cenario):
    resp = client.get(reverse('confirmar_conclusao', args=[cenario['minha1'].pk]))

    assert resp.status_code == 200
    assert resp.context['atividade'] == cenario['minha1']
    html = resp.content.decode()
    assert 'Cumprimentar' in html
    assert 'Sim, terminei' in html and 'Não, voltar' in html
    assert not RegistroEvolucao.objects.exists()


@pytest.mark.django_db
def test_confirmar_conclusao_de_atividade_alheia_da_404(client, cenario):
    assert client.get(reverse('confirmar_conclusao', args=[cenario['alheia'].pk])).status_code == 404


@pytest.mark.django_db
def test_confirmar_so_por_get(client, cenario):
    assert client.post(reverse('confirmar_conclusao', args=[cenario['minha1'].pk])).status_code == 405


@pytest.mark.django_db
def test_concluir_registra_evolucao_e_some_da_lista(client, cenario):
    aluno, atividade = cenario['aluno'], cenario['minha1']
    resp = _concluir(client, atividade)

    assert resp.redirect_chain == [(LISTA, 302)]
    assert 'Atividade concluída: Cumprimentar.' in resp.content.decode()
    registro = RegistroEvolucao.objects.get()
    assert (registro.aluno, registro.atividade, registro.status) == (aluno, atividade, 'concluida')
    assert list(resp.context['atividades']) == [cenario['minha2']]


@pytest.mark.django_db
def test_conclusao_de_outro_aluno_nao_esconde_a_atividade(client, cenario):
    # Mesma atividade, outro aluno do mesmo profissional.
    colega = _aluno('colega2@ex.com', cenario['aluno'].profissional)
    RegistroEvolucao.objects.create(aluno=colega, atividade=cenario['minha1'],
                                    status=RegistroEvolucao.Status.CONCLUIDA)
    assert cenario['minha1'] in client.get(LISTA).context['atividades']


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['pendente', 'em_andamento'])
def test_registro_nao_concluido_mantem_atividade_na_lista(client, cenario, status):
    RegistroEvolucao.objects.create(aluno=cenario['aluno'], atividade=cenario['minha1'], status=status)
    assert cenario['minha1'] in client.get(LISTA).context['atividades']

    _concluir(client, cenario['minha1'])
    assert RegistroEvolucao.objects.count() == 2  # histórico anterior preservado
    assert cenario['minha1'] not in client.get(LISTA).context['atividades']


@pytest.mark.django_db
def test_concluir_duas_vezes_nao_duplica(client, cenario):
    _concluir(client, cenario['minha1'])
    resp = _concluir(client, cenario['minha1'])

    assert RegistroEvolucao.objects.count() == 1
    assert 'já estava concluída' in resp.content.decode()


@pytest.mark.django_db
def test_banco_barra_segunda_conclusao(cenario):
    dados = {'aluno': cenario['aluno'], 'atividade': cenario['minha1'], 'status': 'concluida'}
    RegistroEvolucao.objects.create(**dados)
    with pytest.raises(IntegrityError):
        RegistroEvolucao.objects.create(**dados)


@pytest.mark.django_db
def test_nao_conclui_atividade_de_outro_profissional(client, cenario):
    resp = client.post(reverse('concluir_atividade', args=[cenario['alheia'].pk]))
    assert resp.status_code == 404
    assert client.post(reverse('concluir_atividade', args=[999999])).status_code == 404
    assert not RegistroEvolucao.objects.exists()


@pytest.mark.django_db
def test_concluir_so_por_post(client, cenario):
    assert client.get(reverse('concluir_atividade', args=[cenario['minha1'].pk])).status_code == 405
    assert not RegistroEvolucao.objects.exists()


@pytest.mark.django_db
def test_concluir_exige_csrf(cenario):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(cenario['aluno'].user)
    assert client.post(reverse('concluir_atividade', args=[cenario['minha1'].pk])).status_code == 403
    assert not RegistroEvolucao.objects.exists()


@pytest.mark.django_db
def test_lista_vazia_mostra_aviso(client, cenario):
    for chave in ['minha1', 'minha2']:
        _concluir(client, cenario[chave])
    assert 'não tem atividades para fazer agora' in client.get(LISTA).content.decode()


@pytest.mark.django_db
def test_home_do_aluno_leva_para_atividades(client, cenario):
    assert client.get(reverse('home')).url == LISTA


@pytest.mark.django_db
@pytest.mark.parametrize('bloqueio', [
    lambda prof: Profissional.objects.filter(pk=prof.pk).update(is_approved=False),
    lambda prof: User.objects.filter(pk=prof.user_id).update(is_active=False),
], ids=['aprovacao_revogada', 'profissional_desativado'])
def test_profissional_bloqueado_nao_entrega_atividades(client, cenario, bloqueio):
    bloqueio(cenario['minha1'].profissional)

    assert list(client.get(LISTA).context['atividades']) == []
    assert client.post(reverse('concluir_atividade', args=[cenario['minha1'].pk])).status_code == 404
    assert not RegistroEvolucao.objects.exists()
