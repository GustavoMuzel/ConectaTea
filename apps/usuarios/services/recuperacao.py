"""Recuperação de senha por código enviado ao e-mail (RF03; OWASP Forgot Password)."""

import secrets

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.usuarios.models import CodigoVerificacao, User

from .email import enviar_codigo_recuperacao


def solicitar_codigo(email: str) -> None:
    """Gera e envia um código se a conta existir e estiver ativa. Não diz nada a quem chamou (RN05)."""
    user = User.objects.filter(email__iexact=email.strip(), is_active=True).first()
    if user is None:
        return
    codigo = f'{secrets.randbelow(10 ** 6):06d}'
    agora = timezone.now()
    with transaction.atomic():
        # RN06: um novo pedido invalida os códigos anteriores ainda abertos.
        CodigoVerificacao.objects.filter(user=user, usado_em__isnull=True, expira_em__gt=agora).update(expira_em=agora)
        CodigoVerificacao.objects.create(
            user=user, codigo_hash=make_password(codigo), expira_em=agora + CodigoVerificacao.VALIDADE,
        )
    transaction.on_commit(lambda: enviar_codigo_recuperacao(user.email, codigo), robust=True)


def conferir_codigo(email: str, codigo: str) -> CodigoVerificacao | None:
    """Devolve o código válido que confere com o digitado (travado para update) ou None.

    Errar conta uma tentativa; na quinta, o código deixa de valer (RN02). Chamar dentro de transaction.atomic().
    """
    registro = (CodigoVerificacao.objects.select_for_update().select_related('user')
                .filter(user__email__iexact=email, user__is_active=True, usado_em__isnull=True,
                        expira_em__gt=timezone.now(), tentativas__lt=CodigoVerificacao.MAX_TENTATIVAS)
                .order_by('-criado_em', '-pk').first())
    if registro is None:
        return None
    if not check_password(codigo, registro.codigo_hash):
        registro.tentativas += 1
        registro.save(update_fields=['tentativas'])
        return None
    return registro


def usar_codigo(registro: CodigoVerificacao, nova_senha: str) -> None:
    registro.user.set_password(nova_senha)
    registro.user.save(update_fields=['password'])
    registro.usado_em = timezone.now()
    registro.save(update_fields=['usado_em'])
