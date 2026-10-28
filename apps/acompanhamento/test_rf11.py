import datetime

import pytest
from django.db.models import ProtectedError
from django.urls import reverse

from apps.usuarios.models import Aluno, Profissional, User

from .models import Anotacao

SENHA = 'Senha-forte-123'
PRIVADA, COMPARTILHADA = Anotacao.Visibilidade.PRIVADA, Anotacao.Visibilidade.COMPARTILHADA


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


def _aluno(email, prof):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


@pytest.fixture
def cenario():
    prof, outro = _prof('prof@ex.com'), _prof('outro@ex.com')
    aluno = _aluno('aluno@ex.com', prof)
    return {
        'prof': prof, 'outro_prof': outro, 'aluno': aluno,
        'colega': _aluno('colega@ex.com', prof),
        'alheio': _aluno('alheio@ex.com', outro),
        'url_prof': reverse('anotacoes_profissional', args=[aluno.pk]),
        'url_aluno': reverse('anotacoes_aluno'),
    }


def _escrever(client, quem, url, texto, visibilidade):
    client.force_login(quem)
    return client.post(url, {'texto': texto, 'visibilidade': visibilidade})


def _ve(client, quem, url, texto):
    client.force_login(quem)
    return texto in client.get(url).content.decode()


@pytest.mark.django_db
def test_profissional_cria_anotacao_privada(client, cenario):
    resp = _escrever(client, cenario['prof'].user, cenario['url_prof'], 'Só para mim.', PRIVADA)
    assert resp.status_code == 302 and resp.url == cenario['url_prof']
    anotacao = Anotacao.objects.get()
    assert (anotacao.autor, anotacao.aluno, anotacao.visibilidade) == (cenario['prof'].user, cenario['aluno'], PRIVADA)
    assert _ve(client, cenario['prof'].user, cenario['url_prof'], 'Só para mim.')
    assert not _ve(client, cenario['aluno'].user, cenario['url_aluno'], 'Só para mim.')


@pytest.mark.django_db
def test_profissional_cria_anotacao_compartilhada(client, cenario):
    _escrever(client, cenario['prof'].user, cenario['url_prof'], 'Combinado de rotina.', COMPARTILHADA)
    assert _ve(client, cenario['aluno'].user, cenario['url_aluno'], 'Combinado de rotina.')
    # O aluno lê, mas a anotação continua sendo do profissional.
    assert not _ve(client, cenario['colega'].user, reverse('anotacoes_aluno'), 'Combinado de rotina.')


@pytest.mark.django_db
def test_aluno_cria_anotacao_compartilhada(client, cenario):
    resp = _escrever(client, cenario['aluno'].user, cenario['url_aluno'], 'Gostei da atividade.', COMPARTILHADA)
    assert resp.status_code == 302 and resp.url == cenario['url_aluno']
    assert Anotacao.objects.get().aluno == cenario['aluno']
    assert _ve(client, cenario['prof'].user, cenario['url_prof'], 'Gostei da atividade.')


@pytest.mark.django_db
def test_aluno_cria_anotacao_privada(client, cenario):
    _escrever(client, cenario['aluno'].user, cenario['url_aluno'], 'Meu segredo.', PRIVADA)
    assert _ve(client, cenario['aluno'].user, cenario['url_aluno'], 'Meu segredo.')
    assert not _ve(client, cenario['prof'].user, cenario['url_prof'], 'Meu segredo.')


@pytest.mark.django_db
def test_autor_edita_e_exclui_e_terceiros_nao(client, cenario):
    _escrever(client, cenario['prof'].user, cenario['url_prof'], 'Texto original.', COMPARTILHADA)
    anotacao = Anotacao.objects.get()
    editar, excluir = reverse('editar_anotacao', args=[anotacao.pk]), reverse('excluir_anotacao', args=[anotacao.pk])

    # Terceiros: o aluno (que lê a compartilhada) e outro profissional; depois, o visitante.
    for quem in [cenario['aluno'].user, cenario['outro_prof'].user]:
        client.force_login(quem)
        assert [client.get(editar).status_code, client.get(excluir).status_code] == [404, 404]
        assert client.post(editar, {'texto': 'Invadida', 'visibilidade': PRIVADA}).status_code == 404
        assert client.post(excluir).status_code == 404
    client.logout()
    assert client.get(editar).status_code == 302
    anotacao.refresh_from_db()
    assert anotacao.texto == 'Texto original.'

    # O autor edita e exclui.
    client.force_login(cenario['prof'].user)
    assert 'Texto original.' in client.get(editar).content.decode()
    resp = client.post(editar, {'texto': 'Texto revisado.', 'visibilidade': PRIVADA})
    assert resp.status_code == 302 and resp.url == cenario['url_prof']
    anotacao.refresh_from_db()
    assert (anotacao.texto, anotacao.visibilidade) == ('Texto revisado.', PRIVADA)
    assert client.get(excluir).status_code == 200  # pede confirmação antes
    assert Anotacao.objects.count() == 1
    resp = client.post(excluir)
    assert resp.status_code == 302 and resp.url == cenario['url_prof']
    assert not Anotacao.objects.exists()


@pytest.mark.django_db
def test_anotacao_vazia_e_recusada(client, cenario):
    resp = _escrever(client, cenario['aluno'].user, cenario['url_aluno'], '   ', COMPARTILHADA)
    assert resp.status_code == 200 and 'texto' in resp.context['form'].errors
    assert not Anotacao.objects.exists()


@pytest.mark.django_db
def test_anotacoes_respeitam_o_vinculo(client, cenario):
    # Profissional só mexe nos próprios alunos; aluno não entra na rota do profissional.
    client.force_login(cenario['outro_prof'].user)
    assert client.get(cenario['url_prof']).status_code == 404
    assert client.post(cenario['url_prof'], {'texto': 'x', 'visibilidade': PRIVADA}).status_code == 404
    client.force_login(cenario['aluno'].user)
    assert client.get(cenario['url_prof']).status_code == 403
    client.force_login(cenario['prof'].user)
    assert client.get(cenario['url_aluno']).status_code == 403
    client.logout()
    assert client.get(cenario['url_aluno']).status_code == 302
    assert not Anotacao.objects.exists()

    # Trocou de profissional: o novo não lê o que o antigo compartilhou, e o aluno também não o relê.
    _escrever(client, cenario['prof'].user, cenario['url_prof'], 'Do antigo.', COMPARTILHADA)
    Aluno.objects.filter(pk=cenario['aluno'].pk).update(profissional=cenario['outro_prof'])
    assert not _ve(client, cenario['outro_prof'].user, cenario['url_prof'], 'Do antigo.')
    assert not _ve(client, cenario['aluno'].user, cenario['url_aluno'], 'Do antigo.')


@pytest.mark.django_db
def test_anotacao_escapa_html_e_ignora_autor_e_aluno_do_post(client, cenario):
    client.force_login(cenario['aluno'].user)
    client.post(cenario['url_aluno'], {
        'texto': '<script>alert(1)</script>', 'visibilidade': COMPARTILHADA,
        'autor': cenario['prof'].user.pk, 'aluno': cenario['colega'].pk,
    })
    anotacao = Anotacao.objects.get()
    assert (anotacao.autor, anotacao.aluno) == (cenario['aluno'].user, cenario['aluno'])
    pagina = client.get(cenario['url_aluno']).content.decode()
    assert '<script>alert(1)</script>' not in pagina and '&lt;script&gt;' in pagina


@pytest.mark.django_db
def test_ex_profissional_edita_a_propria_anotacao_e_volta_para_a_lista_de_alunos(client, cenario):
    _escrever(client, cenario['prof'].user, cenario['url_prof'], 'Antiga.', PRIVADA)
    anotacao = Anotacao.objects.get()
    Aluno.objects.filter(pk=cenario['aluno'].pk).update(profissional=cenario['outro_prof'])
    resp = client.post(reverse('editar_anotacao', args=[anotacao.pk]), {'texto': 'Revisada.', 'visibilidade': PRIVADA})
    assert resp.status_code == 302 and resp.url == reverse('alunos_profissional')
    # Quem não é participante do vínculo não lê nada pelo queryset.
    anotacao.refresh_from_db()
    assert anotacao.texto == 'Revisada.'
    aluno = Aluno.objects.get(pk=cenario['aluno'].pk)  # recarrega: o vínculo mudou no banco
    assert not Anotacao.objects.visiveis_para(cenario['prof'].user, aluno).exists()


@pytest.mark.django_db
def test_nao_apaga_usuario_nem_aluno_com_anotacoes(client, cenario):
    _escrever(client, cenario['aluno'].user, cenario['url_aluno'], 'Histórico.', PRIVADA)
    with pytest.raises(ProtectedError):
        cenario['aluno'].delete()
    with pytest.raises(ProtectedError):
        cenario['aluno'].user.delete()
    assert Anotacao.objects.count() == 1
