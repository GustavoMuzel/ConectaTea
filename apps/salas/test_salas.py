"""Sala do aluno: senha, pedido de entrada aprovado pelo dono, atividades com análise e videochamada."""
import pytest
from django.urls import reverse

from apps.acompanhamento.models import LogAcesso
from apps.atividades.models import Atividade

from apps.usuarios.models import Aluno

from .models import MembroSala, ParticipacaoVideochamada, Sala, SolicitacaoVinculo

pytestmark = pytest.mark.integration

FORMS = {'tipo_material': 'formulario', 'link_formulario': 'https://forms.gle/abc'}


@pytest.fixture
def cenario(criar_prof, criar_aluno):
    dono = criar_prof('dono@ex.com')
    aluno = criar_aluno('aluno@ex.com', profissional=dono)
    sala = Sala.objects.create(aluno=aluno, dono=dono)
    return {'dono': dono, 'aluno': aluno, 'sala': sala, 'fono': criar_prof('fono@ex.com')}


def _entrar(client, prof, senha):
    client.force_login(prof.user)
    return client.post(reverse('entrar_sala'), {'senha': senha})


def _aprovar(client, c):
    _entrar(client, c['fono'], c['sala'].senha)
    membro = MembroSala.objects.get(profissional=c['fono'])
    client.force_login(c['dono'].user)
    client.post(reverse('decidir_membro', args=[c['sala'].pk, membro.pk, 'aprovar']))
    membro.refresh_from_db()
    return membro


@pytest.mark.django_db
def test_senha_tem_6_caracteres_sem_confusos(cenario):
    senha = cenario['sala'].senha
    assert len(senha) == 6 and not set(senha) & set('0O1IL')


@pytest.mark.django_db
def test_senha_errada_nao_cria_pedido(client, cenario):
    resp = _entrar(client, cenario['fono'], 'ZZZZZZ')
    assert 'senha' in resp.context['form'].errors and not MembroSala.objects.exists()


@pytest.mark.django_db
def test_senha_certa_cria_pedido_mas_nao_da_acesso(client, cenario):
    resp = _entrar(client, cenario['fono'], cenario['sala'].senha.lower())  # aceita minúsculas
    assert resp.url == reverse('salas')
    assert MembroSala.objects.get().status == 'pendente'
    assert client.get(reverse('sala', args=[cenario['sala'].pk])).status_code == 404
    assert client.get(reverse('evolucao_aluno', args=[cenario['aluno'].pk])).status_code == 404


@pytest.mark.django_db
def test_dono_aprova_e_membro_ve_evolucao_e_corrige(client, cenario):
    membro = _aprovar(client, cenario)
    assert membro.status == 'aprovado'
    assert LogAcesso.objects.filter(user=cenario['dono'].user, aluno=cenario['aluno']).exists()
    client.force_login(cenario['fono'].user)
    assert client.get(reverse('sala', args=[cenario['sala'].pk])).status_code == 200
    resp = client.get(reverse('evolucao_aluno', args=[cenario['aluno'].pk]))
    assert resp.status_code == 200 and resp.context['eh_dono'] is False
    assert cenario['aluno'] in client.get(reverse('alunos_profissional')).context['da_equipe']
    # Anotações privadas do vínculo continuam só do dono.
    assert client.get(reverse('anotacoes_profissional', args=[cenario['aluno'].pk])).status_code == 404


@pytest.mark.django_db
def test_so_o_dono_aprova_troca_senha_e_remove(client, cenario):
    membro = _aprovar(client, cenario)
    outro = cenario['fono']
    client.force_login(outro.user)
    sala = cenario['sala']
    assert client.post(reverse('trocar_senha_sala', args=[sala.pk])).status_code == 404
    assert client.post(reverse('decidir_membro', args=[sala.pk, membro.pk, 'remover'])).status_code == 404

    client.force_login(cenario['dono'].user)
    antiga = sala.senha
    client.post(reverse('trocar_senha_sala', args=[sala.pk]))
    sala.refresh_from_db()
    assert sala.senha != antiga
    client.post(reverse('decidir_membro', args=[sala.pk, membro.pk, 'remover']))
    client.force_login(outro.user)
    assert client.get(reverse('sala', args=[sala.pk])).status_code == 404


@pytest.mark.django_db
def test_atividade_do_membro_so_chega_ao_aluno_depois_da_aprovacao(client, cenario):
    _aprovar(client, cenario)
    sala, aluno = cenario['sala'], cenario['aluno']
    client.force_login(cenario['fono'].user)
    client.post(reverse('propor_atividade', args=[sala.pk]), {'title': 'Proposta', 'category': 'fala', **FORMS})
    atividade = Atividade.objects.get(title='Proposta')
    assert atividade.publicacao == 'em_analise' and atividade.autor == cenario['fono']
    # Membro não aprova a própria atividade.
    assert client.post(reverse('analisar_atividade', args=[sala.pk, atividade.pk, 'aprovar'])).status_code == 404

    client.force_login(aluno.user)
    assert atividade not in client.get(reverse('aluno_atividades')).context['atividades']

    client.force_login(cenario['dono'].user)
    client.post(reverse('analisar_atividade', args=[sala.pk, atividade.pk, 'aprovar']))
    client.force_login(aluno.user)
    assert atividade in client.get(reverse('aluno_atividades')).context['atividades']


@pytest.mark.django_db
def test_dono_recusa_com_motivo_e_membro_ve(client, cenario):
    _aprovar(client, cenario)
    sala = cenario['sala']
    client.force_login(cenario['fono'].user)
    client.post(reverse('propor_atividade', args=[sala.pk]), {'title': 'Proposta', 'category': 'fala', **FORMS})
    atividade = Atividade.objects.get()
    client.force_login(cenario['dono'].user)
    client.post(reverse('analisar_atividade', args=[sala.pk, atividade.pk, 'recusar']), {'motivo': 'Muito longa'})
    atividade.refresh_from_db()
    assert atividade.publicacao == 'recusada' and atividade.motivo_recusa == 'Muito longa'
    client.force_login(cenario['fono'].user)
    assert 'Muito longa' in client.get(reverse('sala', args=[sala.pk])).content.decode()


@pytest.mark.django_db
def test_atividade_exclusiva_nao_aparece_para_outro_aluno(client, cenario, criar_aluno):
    outro = criar_aluno('outro@ex.com', profissional=cenario['dono'])
    client.force_login(cenario['dono'].user)
    dados = {'title': 'Só do aluno', 'category': 'x', **FORMS}
    client.post(reverse('propor_atividade', args=[cenario['sala'].pk]), dados)
    atividade = Atividade.objects.get()
    assert atividade.publicacao == 'publicada'  # do dono, publica na hora
    client.force_login(outro.user)
    assert atividade not in client.get(reverse('aluno_atividades')).context['atividades']
    client.force_login(cenario['dono'].user)
    assert atividade not in client.get(reverse('painel')).context['atividades']  # fica na sala, não na biblioteca


@pytest.mark.django_db
def test_videochamada_registra_e_so_entra_quem_participa(client, cenario, settings):
    settings.JITSI_DOMINIO = 'meet.exemplo.com'
    sala = cenario['sala']
    client.force_login(cenario['aluno'].user)
    resp = client.get(reverse('videochamada', args=[sala.pk]))
    assert resp.url.startswith(f'https://meet.exemplo.com/ConectaTEA-{sala.id_videochamada}')
    assert ParticipacaoVideochamada.objects.filter(user=cenario['aluno'].user).exists()
    client.force_login(cenario['fono'].user)  # ainda não aprovado
    assert client.get(reverse('videochamada', args=[sala.pk])).status_code == 404


@pytest.mark.django_db
def test_aluno_ve_a_equipe(client, cenario):
    _aprovar(client, cenario)
    client.force_login(cenario['aluno'].user)
    html = client.get(reverse('minha_equipe')).content.decode()
    assert 'Dono' in html and 'Fono' in html


@pytest.mark.django_db
def test_recusado_pode_pedir_de_novo(client, cenario):
    _entrar(client, cenario['fono'], cenario['sala'].senha)
    membro = MembroSala.objects.get()
    client.force_login(cenario['dono'].user)
    client.post(reverse('decidir_membro', args=[cenario['sala'].pk, membro.pk, 'recusar']))
    _entrar(client, cenario['fono'], cenario['sala'].senha)
    membro.refresh_from_db()
    assert membro.status == 'pendente'


@pytest.mark.django_db
def test_h1_antigo_profissional_perde_acesso_a_sala(client, cenario, criar_prof):
    _aprovar(client, cenario)
    novo = criar_prof('novo@ex.com')
    sala, aluno, senha_antiga = cenario['sala'], cenario['aluno'], cenario['sala'].senha
    video_antigo = sala.id_videochamada

    Aluno.objects.filter(pk=aluno.pk).update(profissional=None)  # vínculo desfeito (ex.: pelo admin)
    for antigo in (cenario['dono'], cenario['fono']):  # dono e membro aprovado
        client.force_login(antigo.user)
        for nome, arg in [('sala', sala.pk), ('videochamada', sala.pk), ('evolucao_aluno', aluno.pk)]:
            assert client.get(reverse(nome, args=[arg])).status_code == 404

    pedido = SolicitacaoVinculo.objects.create(profissional=novo, aluno=aluno)
    client.force_login(aluno.user)
    client.post(reverse('responder_vinculo', args=[pedido.pk, 'aceitar']))
    sala.refresh_from_db()
    assert sala.dono == novo and sala.senha != senha_antiga  # o novo assume a sala
    assert sala.id_videochamada != video_antigo  # a equipe antiga não volta pela URL do Jitsi
    assert not MembroSala.objects.exclude(status=MembroSala.Status.REMOVIDO).exists()
    client.force_login(novo.user)
    assert client.get(reverse('sala', args=[sala.pk])).status_code == 200
    client.force_login(cenario['fono'].user)
    assert client.get(reverse('sala', args=[sala.pk])).status_code == 404
