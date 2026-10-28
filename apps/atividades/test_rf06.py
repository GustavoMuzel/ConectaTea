import pytest
from django.urls import reverse

from apps.acompanhamento.forms import DistribuicaoAtividadeForm
from apps.usuarios.models import Profissional, User

from .models import Atividade

SENHA = 'Senha-forte-123'


def _prof(email):
    user = User.objects.create_user(email, email, SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


@pytest.fixture
def cenario(client):
    prof, outro = _prof('prof@ex.com'), _prof('outro@ex.com')
    client.force_login(prof.user)
    return {
        'prof': prof,
        'minha': Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social'),
        'alheia': Atividade.objects.create(profissional=outro, title='Alheia', category='social'),
    }


@pytest.mark.django_db
def test_profissional_edita_a_propria_atividade(client, cenario):
    url = reverse('editar_atividade', args=[cenario['minha'].pk])
    assert client.get(url).status_code == 200
    resp = client.post(url, {'title': 'Cumprimentar bem', 'description': 'Olhar nos olhos', 'category': 'social',
                             'arquivada': 'on'})  # o form não aceita arquivar por edição
    assert resp.status_code == 302 and resp.url == reverse('painel')
    cenario['minha'].refresh_from_db()
    assert (cenario['minha'].title, cenario['minha'].description) == ('Cumprimentar bem', 'Olhar nos olhos')
    assert cenario['minha'].profissional == cenario['prof'] and not cenario['minha'].arquivada


@pytest.mark.django_db
def test_profissional_nao_edita_nem_arquiva_atividade_de_outro(client, cenario):
    alheia = cenario['alheia']
    url = reverse('editar_atividade', args=[alheia.pk])
    assert client.get(url).status_code == 404
    assert client.post(url, {'title': 'Invadida', 'category': 'x'}).status_code == 404
    assert client.post(reverse('arquivar_atividade', args=[alheia.pk])).status_code == 404
    alheia.refresh_from_db()
    assert alheia.title == 'Alheia' and not alheia.arquivada


@pytest.mark.django_db
def test_so_profissional_aprovado_acessa_edicao_e_arquivamento(client, cenario):
    urls = [reverse('editar_atividade', args=[cenario['minha'].pk]),
            reverse('arquivar_atividade', args=[cenario['minha'].pk])]
    client.logout()
    for url in urls:
        resp = client.get(url)
        assert resp.status_code == 302 and resp.url.startswith(reverse('login'))
    aluno = User.objects.create_user('aluno@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    client.force_login(aluno)
    assert [client.get(url).status_code for url in urls] == [403, 403]
    assert client.post(urls[1]).status_code == 403
    cenario['minha'].refresh_from_db()
    assert not cenario['minha'].arquivada


@pytest.mark.django_db
def test_profissional_arquiva_a_propria_atividade(client, cenario):
    url = reverse('arquivar_atividade', args=[cenario['minha'].pk])
    assert client.get(url).status_code == 405
    resp = client.post(url)
    assert resp.status_code == 302 and resp.url == reverse('painel')
    cenario['minha'].refresh_from_db()
    assert cenario['minha'].arquivada
    # Continua no painel (histórico), marcada como arquivada e sem o botão de distribuir.
    html = client.get(reverse('painel')).content.decode()
    assert 'Cumprimentar' in html and 'Arquivada' in html
    assert reverse('distribuir_atividade', args=[cenario['minha'].pk]) not in html


@pytest.mark.django_db
def test_atividade_arquivada_nao_aparece_na_distribuicao(client, cenario):
    client.post(reverse('arquivar_atividade', args=[cenario['minha'].pk]))
    form = DistribuicaoAtividadeForm(profissional=cenario['prof'])
    assert cenario['minha'] not in form.fields['atividade'].queryset
    assert client.get(reverse('distribuir_atividade', args=[cenario['minha'].pk])).status_code == 404
