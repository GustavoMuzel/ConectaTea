"""Envio de e-mail transacional pela API REST do Brevo."""

import logging

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html

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
    html = format_html(
        '<p>Olá.</p><p>Sua conta no ConectaTEA foi criada com o perfil <strong>{}</strong>.</p>'
        '<p>Para entrar, use este e-mail e a senha que você cadastrou.</p>',
        user.get_role_display(),
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
