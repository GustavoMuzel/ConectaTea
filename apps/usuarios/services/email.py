"""Envio de e-mail transacional pela API REST do Brevo."""

import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.usuarios.models import User

logger = logging.getLogger(__name__)

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


def enviar_email(para_email: str, assunto: str, html: str) -> bool:
    """Envia um e-mail. Nunca levanta exceção: falha de e-mail não pode quebrar o fluxo do usuário."""
    if not settings.BREVO_API_KEY:
        logger.warning('BREVO_API_KEY ausente; e-mail "%s" não enviado.', assunto)
        return False
    payload = {
        'sender': {'email': settings.BREVO_SENDER_EMAIL, 'name': settings.BREVO_SENDER_NAME},
        'to': [{'email': para_email}],
        'subject': assunto,
        'htmlContent': html,
    }
    try:
        resp = requests.post(
            BREVO_URL, json=payload, timeout=(3, 5),
            headers={'api-key': settings.BREVO_API_KEY, 'accept': 'application/json'},
        )
        resp.raise_for_status()
    except requests.RequestException:
        logger.exception('Falha ao enviar e-mail "%s" pelo Brevo.', assunto)
        return False
    return True


def enviar_boas_vindas(user: User) -> bool:
    # Sem user.name no e-mail: o nome é texto livre do cadastro e viraria conteúdo de phishing.
    aviso = ''
    if user.role == User.Role.PROFISSIONAL:
        aviso = mark_safe(  # texto fixo, sem dado do usuário
            '<p><strong>Atenção:</strong> contas de profissional precisam ser aprovadas por um administrador. '
            'Você já pode entrar, mas só poderá cadastrar atividades e acompanhar alunos depois da aprovação.</p>',
        )
    html = format_html(
        '<p>Olá.</p><p>Sua conta no ConectaTEA foi criada com o perfil <strong>{}</strong>.</p>{}'
        '<p>Para entrar, use este e-mail e a senha que você cadastrou.</p>',
        user.get_role_display(), aviso,
    )
    return enviar_email(user.email, 'Bem-vindo ao ConectaTEA', html)


def enviar_notificacao_aluno_criado(user: User) -> bool:
    """Avisa o responsável, no e-mail informado no cadastro, sobre a conta e o consentimento registrado."""
    aluno = user.aluno
    if not aluno.consentimento_data:
        logger.warning('Aluno %s sem consentimento_data; notificação ao responsável não enviada.', aluno.pk)
        return False
    html = format_html(
        '<p>Olá.</p>'
        '<p>Uma conta de aluno foi criada no ConectaTEA com você como responsável.</p>'
        '<p>Ao concluir o cadastro em {}, foi registrada a sua autorização aos Termos de Uso e à '
        'Política de Privacidade do ConectaTEA.</p>',
        timezone.localtime(aluno.consentimento_data).strftime('%d/%m/%Y %H:%M'),
    )
    return enviar_email(aluno.guardian_email, 'Conta de aluno criada no ConectaTEA', html)


def enviar_codigo_recuperacao(para_email: str, codigo: str) -> bool:
    html = format_html(
        '<p>Olá.</p><p>Recebemos um pedido para criar uma senha nova na sua conta do ConectaTEA.</p>'
        '<p>Seu código de verificação é:</p>'
        '<p style="font-size:28px;font-weight:bold;letter-spacing:6px">{}</p>'
        '<p>O código vale por 10 minutos e só pode ser usado uma vez.</p>'
        '<p>Se não foi você que pediu, ignore este e-mail: sua senha continua a mesma.</p>',
        codigo,
    )
    enviado = enviar_email(para_email, 'Código para criar uma senha nova no ConectaTEA', html)
    if not enviado and settings.DEBUG:
        # Só em desenvolvimento e sem Brevo: mostra o código no terminal para dar para testar o fluxo.
        logger.info('Código de recuperação de senha para %s (DEBUG): %s', para_email, codigo)
    return enviado


# Avisos ao responsável e ao profissional. Sem nomes nem conteúdo de atividades no e-mail: só o essencial e o
# convite para entrar no sistema (menos dado de menor circulando por e-mail e menos risco de phishing).

def _formatar(quando):
    return timezone.localtime(quando).strftime('%d/%m/%Y às %Hh%M')


def enviar_aviso_chamada_marcada(aluno, quando) -> bool:
    html = format_html(
        '<p>Olá.</p><p>O profissional que acompanha o aluno no ConectaTEA marcou uma videochamada para '
        '<strong>{}</strong>.</p><p>Ela abre 15 minutos antes, em "Minha equipe". A chamada não é gravada.</p>',
        _formatar(quando),
    )
    enviado = enviar_email(aluno.guardian_email, 'Videochamada marcada no ConectaTEA', html)
    enviar_email(aluno.user.email, 'Videochamada marcada no ConectaTEA', html)
    return enviado


def enviar_aviso_atividade_enviada(aluno, prazo) -> bool:
    html = format_html(
        '<p>Olá.</p><p>O aluno recebeu uma nova atividade no ConectaTEA{}.</p>'
        '<p>Ela aparece no Início e em "Minhas atividades".</p>',
        format_html(', com prazo até <strong>{}</strong>', prazo.strftime('%d/%m/%Y')) if prazo else '',
    )
    return enviar_email(aluno.guardian_email, 'Nova atividade no ConectaTEA', html)


def enviar_aviso_atividades_atrasadas(aluno, quantidade) -> bool:
    html = format_html(
        '<p>Olá.</p><p>O aluno tem <strong>{}</strong> atividade(s) no ConectaTEA que passaram do prazo. '
        'Ele ainda pode fazer.</p><p>Se precisar, o botão "Preciso de ajuda" avisa o profissional.</p>',
        quantidade,
    )
    return enviar_email(aluno.guardian_email, 'Atividades com prazo vencido no ConectaTEA', html)


def enviar_aviso_pedido_ajuda(profissional) -> bool:
    html = mark_safe(  # texto fixo, sem dado do usuário
        '<p>Olá.</p><p>Um aluno pediu ajuda em uma atividade no ConectaTEA.</p>'
        '<p>Veja o pedido em "Meus alunos".</p>'
    )
    return enviar_email(profissional.user.email, 'Pedido de ajuda no ConectaTEA', html)
