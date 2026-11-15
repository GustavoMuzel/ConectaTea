"""Entrada, saída e senha errada entram na auditoria pelos sinais do próprio Django (tela e API)."""

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from apps.usuarios.models import User

from .auditoria import Categoria, registrar


@receiver(user_logged_in)
def entrou(sender, request, user, **kwargs):
    registrar(request, 'Entrou no sistema', Categoria.AUTENTICACAO, user=user)


@receiver(user_logged_out)
def saiu(sender, request, user, **kwargs):
    if user is not None:
        registrar(request, 'Saiu do sistema', Categoria.AUTENTICACAO, user=user)


@receiver(user_login_failed)
def senha_errada(sender, credentials, request=None, **kwargs):
    email = (credentials.get('username') or credentials.get('email') or '').strip()
    user = User.objects.filter(email__iexact=email).first() if email else None
    if user:
        registrar(request, 'Tentativa de login com senha errada', Categoria.AUTENTICACAO, user=user)
    else:
        # E-mail que não existe: guarda só o começo, para não registrar e-mails de terceiros por inteiro.
        local, _, dominio = email.partition('@')
        registrar(request, f'Tentativa de login com e-mail não cadastrado ({local[:1]}***@{dominio})',
                  Categoria.AUTENTICACAO)
