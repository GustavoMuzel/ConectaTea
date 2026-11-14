"""Vínculo: o profissional aprovado envia o pedido e o aluno aceita ou recusa."""
import pytest
from django.urls import reverse

from apps.acompanhamento.models import Anotacao, LogAcesso

from .models import Sala, SolicitacaoVinculo

pytestmark = pytest.mark.integration


@pytest.mark.django_db
def test_lista_mostra_so_alunos_ativos_sem_vinculo(client, criar_prof, criar_aluno):
    prof = criar_prof('ana@ex.com')
    livre = criar_aluno('livre@ex.com')
    criar_aluno('ocupado@ex.com', profissional=criar_prof('outro@ex.com'))
    criar_aluno('inativo@ex.com', ativo=False)
    client.force_login(prof.user)
    assert list(client.get(reverse('vincular_alunos')).context['alunos']) == [livre]


@pytest.mark.django_db
def test_pedido_nao_vincula_ate_o_aluno_aceitar(client, criar_prof, criar_aluno):
    prof, aluno = criar_prof('ana@ex.com'), criar_aluno('livre@ex.com')
    client.force_login(prof.user)
    client.post(reverse('pedir_vinculo', args=[aluno.pk]))
    client.post(reverse('pedir_vinculo', args=[aluno.pk]))  # repetido não duplica
    assert SolicitacaoVinculo.objects.filter(aluno=aluno, status='pendente').count() == 1
    aluno.refresh_from_db()
    assert aluno.profissional is None
    assert aluno.pk in client.get(reverse('vincular_alunos')).context['ja_pedidos']


@pytest.mark.django_db
def test_aluno_aceita_cria_vinculo_sala_e_log(client, criar_prof, criar_aluno):
    ana, bia, aluno = criar_prof('ana@ex.com'), criar_prof('bia@ex.com'), criar_aluno('livre@ex.com')
    pedido = SolicitacaoVinculo.objects.create(profissional=ana, aluno=aluno)
    outro = SolicitacaoVinculo.objects.create(profissional=bia, aluno=aluno)
    client.force_login(aluno.user)
    assert 'Ana' in client.get(reverse('home')).content.decode()  # o pedido aparece para o aluno

    resp = client.post(reverse('responder_vinculo', args=[pedido.pk, 'aceitar']))
    assert resp.url == reverse('aluno_atividades')
    aluno.refresh_from_db()
    assert aluno.profissional == ana
    assert Sala.objects.get(aluno=aluno).dono == ana
    outro.refresh_from_db()
    assert outro.status == 'cancelada'
    assert LogAcesso.objects.filter(user=aluno.user, aluno=aluno).exists()
    # Aceitar de novo (dois cliques) não cria outra sala.
    client.post(reverse('responder_vinculo', args=[pedido.pk, 'aceitar']))
    assert Sala.objects.count() == 1


@pytest.mark.django_db
def test_aluno_recusa(client, criar_prof, criar_aluno):
    aluno = criar_aluno('livre@ex.com')
    pedido = SolicitacaoVinculo.objects.create(profissional=criar_prof('ana@ex.com'), aluno=aluno)
    client.force_login(aluno.user)
    client.post(reverse('responder_vinculo', args=[pedido.pk, 'recusar']))
    pedido.refresh_from_db()
    aluno.refresh_from_db()
    assert pedido.status == 'recusada' and aluno.profissional is None and not Sala.objects.exists()


@pytest.mark.django_db
def test_aluno_nao_responde_pedido_de_outro(client, criar_prof, criar_aluno):
    pedido = SolicitacaoVinculo.objects.create(profissional=criar_prof('ana@ex.com'), aluno=criar_aluno('a@ex.com'))
    client.force_login(criar_aluno('b@ex.com').user)
    assert client.post(reverse('responder_vinculo', args=[pedido.pk, 'aceitar'])).status_code == 404


@pytest.mark.django_db
def test_pedido_de_profissional_que_perdeu_aprovacao_nao_vale(client, criar_prof, criar_aluno):
    prof, aluno = criar_prof('ana@ex.com'), criar_aluno('livre@ex.com')
    pedido = SolicitacaoVinculo.objects.create(profissional=prof, aluno=aluno)
    prof.is_approved = False
    prof.save()
    client.force_login(aluno.user)
    client.post(reverse('responder_vinculo', args=[pedido.pk, 'aceitar']))
    aluno.refresh_from_db()
    assert aluno.profissional is None


@pytest.mark.django_db
def test_pendente_e_aluno_nao_enviam_pedido(client, criar_prof, criar_aluno):
    aluno = criar_aluno('livre@ex.com')
    client.force_login(criar_prof('pend@ex.com', aprovado=False).user)
    assert client.post(reverse('pedir_vinculo', args=[aluno.pk])).url == reverse('home')
    client.force_login(criar_aluno('outro@ex.com', profissional=criar_prof('p@ex.com')).user)
    assert client.get(reverse('vincular_alunos')).status_code == 403
    assert not SolicitacaoVinculo.objects.exists()


@pytest.mark.django_db
def test_aluno_sem_vinculo_ve_so_o_aviso(client, criar_aluno):
    aluno = criar_aluno('livre@ex.com')
    client.force_login(aluno.user)
    html = client.get(reverse('home')).content.decode()
    assert 'ainda não está ligada a um profissional' in html and 'Minhas atividades' not in html
    for nome in ['aluno_atividades', 'historico_aluno', 'anotacoes_aluno', 'minha_equipe']:
        assert client.get(reverse(nome)).url == reverse('home')
    assert list(Anotacao.objects.visiveis_para(aluno.user, aluno)) == []


@pytest.mark.django_db
def test_h3_esconde_email_de_menores(client, criar_prof, criar_aluno):
    prof = criar_prof('ana@ex.com')
    criar_aluno('maria.souza@exemplo.com')
    client.force_login(prof.user)
    html = client.get(reverse('vincular_alunos')).content.decode()
    assert 'Maria.Souza' in html  # o nome aparece
    assert 'maria.souza@exemplo.com' not in html
    assert 'm***@exemplo.com' in html
