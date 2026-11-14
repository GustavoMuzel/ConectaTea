"""Sala do aluno: senha, pedido de entrada aprovado pelo dono, atividades com análise e videochamada."""
import pytest
from django.urls import reverse
from django.utils import timezone

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
    # Chamada marcada para agora: o aluno só entra no horário marcado pelo profissional.
    sala = Sala.objects.create(aluno=aluno, dono=dono, proxima_chamada=timezone.now())
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
def test_videochamada_abre_dentro_do_sistema_e_registra_acionamento(client, cenario, settings):
    settings.JITSI_DOMINIO = 'meet.exemplo.com'
    sala = cenario['sala']
    client.force_login(cenario['aluno'].user)
    resp = client.get(reverse('videochamada', args=[sala.pk]))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert 'meet.exemplo.com' in html and f'ConectaTEA-{sala.id_videochamada}' in html
    participacao = ParticipacaoVideochamada.objects.get(user=cenario['aluno'].user)
    assert participacao.forma == 'embutida' and participacao.entrou_em is None  # só o acionamento
    client.force_login(cenario['fono'].user)  # ainda não aprovado
    assert client.get(reverse('videochamada', args=[sala.pk])).status_code == 404


@pytest.mark.django_db
def test_entrada_e_saida_vem_dos_eventos_do_jitsi(client, cenario):
    sala = cenario['sala']
    client.force_login(cenario['aluno'].user)
    client.get(reverse('videochamada', args=[sala.pk]))
    p = ParticipacaoVideochamada.objects.get()
    url = reverse('evento_videochamada', args=[sala.pk, p.pk])
    assert client.post(url, {'tipo': 'entrou'}).status_code == 200
    p.refresh_from_db()
    assert p.entrou_em and not p.saiu_em
    assert p in sala.na_chamada_agora()
    client.post(url, {'tipo': 'saiu'})
    p.refresh_from_db()
    assert p.saiu_em and p.duracao is not None
    assert client.post(url, {'tipo': 'qualquer'}).status_code == 400


@pytest.mark.django_db
def test_ninguem_registra_evento_na_participacao_de_outro(client, cenario):
    sala = cenario['sala']
    client.force_login(cenario['aluno'].user)
    client.get(reverse('videochamada', args=[sala.pk]))
    p = ParticipacaoVideochamada.objects.get()
    client.force_login(cenario['dono'].user)
    assert client.post(reverse('evento_videochamada', args=[sala.pk, p.pk]), {'tipo': 'entrou'}).status_code == 404


@pytest.mark.django_db
def test_revogar_aprovacao_do_dono_bloqueia_a_videochamada(client, cenario):
    # Caso do parecer: com a aprovação revogada, o dono perde o acesso à chamada também.
    sala, dono = cenario['sala'], cenario['dono']
    client.force_login(dono.user)
    assert client.get(reverse('videochamada', args=[sala.pk])).status_code == 200
    dono.is_approved = False
    dono.save()
    for nome in ('videochamada', 'videochamada_nova_aba'):
        assert client.get(reverse(nome, args=[sala.pk])).status_code == 404
    client.force_login(cenario['aluno'].user)  # sala parada para todos
    assert client.get(reverse('videochamada', args=[sala.pk])).status_code == 404
    assert 'Sua sala está parada' in client.get(reverse('minha_equipe')).content.decode()


@pytest.mark.django_db
def test_membro_revogado_pela_administracao_perde_a_videochamada(client, cenario):
    membro = _aprovar(client, cenario)
    fono = cenario['fono']
    client.force_login(fono.user)
    assert client.get(reverse('videochamada', args=[cenario['sala'].pk])).status_code == 200
    fono.is_approved = False
    fono.save()
    assert client.get(reverse('videochamada', args=[cenario['sala'].pk])).status_code == 404
    assert membro.status == 'aprovado'  # continua na sala, mas sem acesso enquanto estiver revogado


@pytest.mark.django_db
def test_remover_membro_troca_o_endereco_da_chamada(client, cenario):
    membro = _aprovar(client, cenario)
    antes = cenario['sala'].id_videochamada
    client.force_login(cenario['dono'].user)
    client.post(reverse('decidir_membro', args=[cenario['sala'].pk, membro.pk, 'remover']))
    cenario['sala'].refresh_from_db()
    assert cenario['sala'].id_videochamada != antes


@pytest.mark.django_db
def test_nova_aba_registra_so_o_acionamento(client, cenario, settings):
    settings.JITSI_DOMINIO = 'meet.exemplo.com'
    client.force_login(cenario['aluno'].user)
    resp = client.get(reverse('videochamada_nova_aba', args=[cenario['sala'].pk]))
    assert resp.url.startswith(f"https://meet.exemplo.com/ConectaTEA-{cenario['sala'].id_videochamada}")
    assert ParticipacaoVideochamada.objects.get().forma == 'nova_aba'


@pytest.mark.django_db
def test_dono_marca_a_proxima_chamada_e_o_aluno_ve(client, cenario):
    from datetime import timedelta

    from django.utils import timezone
    sala = cenario['sala']
    quando = (timezone.localtime() + timedelta(days=2)).replace(hour=15, minute=0, second=0, microsecond=0)
    client.force_login(cenario['dono'].user)
    client.post(reverse('agendar_chamada', args=[sala.pk]),
                {'proxima_chamada': quando.strftime('%Y-%m-%dT%H:%M'), 'pauta_chamada': 'Treinar cumprimentos'})
    sala.refresh_from_db()
    assert sala.proxima_chamada == quando and sala.pauta_chamada == 'Treinar cumprimentos'
    client.force_login(cenario['aluno'].user)
    html = client.get(reverse('minha_equipe')).content.decode()
    assert 'Treinar cumprimentos' in html and '15h00' in html
    # Membro não marca chamada; data passada é recusada.
    client.force_login(cenario['dono'].user)
    client.post(reverse('agendar_chamada', args=[sala.pk]), {'proxima_chamada': '2000-01-01T10:00'})
    sala.refresh_from_db()
    assert sala.proxima_chamada == quando


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


@pytest.mark.django_db
def test_aluno_so_entra_na_chamada_no_horario_marcado(client, cenario):
    from datetime import timedelta
    sala, agora = cenario['sala'], timezone.now()
    client.force_login(cenario['aluno'].user)
    url = reverse('videochamada', args=[sala.pk])
    for quando, entra in [(None, False), (agora + timedelta(days=1), False), (agora + timedelta(minutes=10), True),
                          (agora - timedelta(hours=1), True), (agora - timedelta(hours=3), False)]:
        Sala.objects.filter(pk=sala.pk).update(proxima_chamada=quando)
        resp = client.get(url)
        assert (resp.status_code == 200) is entra, quando
        if not entra:
            assert resp.url == reverse('minha_equipe')
        assert (client.get(reverse('videochamada_nova_aba', args=[sala.pk])).status_code == 302)
    # Fora do horário, nada é registrado como acionamento do aluno pela nova aba.
    assert not ParticipacaoVideochamada.objects.filter(user=cenario['aluno'].user, forma='nova_aba',
                                                       acionada_em__lt=agora - timedelta(minutes=1)).exists()


@pytest.mark.django_db
def test_minha_equipe_mostra_quando_a_chamada_abre(client, cenario):
    from datetime import timedelta
    sala = cenario['sala']
    Sala.objects.filter(pk=sala.pk).update(proxima_chamada=timezone.now() + timedelta(days=1))
    client.force_login(cenario['aluno'].user)
    html = client.get(reverse('minha_equipe')).content.decode()
    assert 'O botão para entrar aparece' in html and reverse('videochamada', args=[sala.pk]) not in html
    Sala.objects.filter(pk=sala.pk).update(proxima_chamada=None)
    assert 'Ainda não tem videochamada marcada' in client.get(reverse('minha_equipe')).content.decode()


@pytest.mark.django_db
def test_profissionais_entram_a_qualquer_hora(client, cenario):
    Sala.objects.filter(pk=cenario['sala'].pk).update(proxima_chamada=None)
    client.force_login(cenario['dono'].user)
    assert client.get(reverse('videochamada', args=[cenario['sala'].pk])).status_code == 200


@pytest.mark.django_db
def test_aluno_responde_se_vai_participar_e_o_dono_ve(client, cenario):
    from datetime import timedelta
    sala = cenario['sala']
    Sala.objects.filter(pk=sala.pk).update(proxima_chamada=timezone.now() + timedelta(days=1))
    client.force_login(cenario['aluno'].user)
    client.post(reverse('responder_chamada', args=['sim']))
    sala.refresh_from_db()
    assert sala.resposta_aluno == 'sim' and sala.respondida_em
    assert 'Você avisou que vai participar' in client.get(reverse('minha_equipe')).content.decode()
    client.force_login(cenario['dono'].user)
    assert 'vai participar' in client.get(reverse('sala', args=[sala.pk])).content.decode()


@pytest.mark.django_db
def test_remarcar_a_chamada_apaga_a_resposta_e_avisa_por_email(client, cenario, django_capture_on_commit_callbacks):
    from datetime import timedelta
    from unittest.mock import patch
    sala = cenario['sala']
    Sala.objects.filter(pk=sala.pk).update(resposta_aluno='sim', respondida_em=timezone.now())
    quando = timezone.localtime() + timedelta(days=2)
    client.force_login(cenario['dono'].user)
    with patch('apps.usuarios.services.email.enviar_email') as envio, django_capture_on_commit_callbacks(execute=True):
        client.post(reverse('agendar_chamada', args=[sala.pk]),
                    {'proxima_chamada': quando.strftime('%Y-%m-%dT%H:%M')})
    sala.refresh_from_db()
    assert sala.resposta_aluno == '' and sala.respondida_em is None
    destinatarios = {c.args[0] for c in envio.call_args_list}
    assert destinatarios == {cenario['aluno'].guardian_email, cenario['aluno'].user.email}
    assert quando.strftime('%d/%m/%Y') in envio.call_args.args[2]


@pytest.mark.django_db
def test_sem_chamada_marcada_nao_da_para_responder(client, cenario):
    Sala.objects.filter(pk=cenario['sala'].pk).update(proxima_chamada=None)
    client.force_login(cenario['aluno'].user)
    client.post(reverse('responder_chamada', args=['sim']))
    cenario['sala'].refresh_from_db()
    assert cenario['sala'].resposta_aluno == ''
    assert client.post(reverse('responder_chamada', args=['talvez'])).status_code == 404
