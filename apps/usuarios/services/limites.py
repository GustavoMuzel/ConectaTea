"""Limites contra tentativa e erro (RNF04): login (web e API) e pedidos de código de recuperação.

Usa o cache do Django. Em produção ele é o DatabaseCache (settings.CACHES): fica no banco e vale para todos
os processos da aplicação, e não só para o processo que recebeu a requisição.
"""

import hashlib

from django.core.cache import cache

MAX_FALHAS_LOGIN = 5
BLOQUEIO_LOGIN_SEGUNDOS = 15 * 60


def _chave(prefixo: str, email: str) -> str:
    # Hash do e-mail: a chave do cache não guarda o e-mail em texto (LGPD) e tem tamanho fixo.
    return f'{prefixo}_{hashlib.sha256((email or "").strip().lower().encode()).hexdigest()}'


def login_bloqueado(email: str) -> bool:
    return cache.get(_chave('login_falhas', email), 0) >= MAX_FALHAS_LOGIN


def registrar_falha_login(email: str) -> None:
    """Conta a falha. A janela de 15 minutos começa na primeira falha; na quinta, o login fica bloqueado."""
    chave = _chave('login_falhas', email)
    cache.add(chave, 0, timeout=BLOQUEIO_LOGIN_SEGUNDOS)
    try:
        cache.incr(chave)
    except ValueError:  # a chave expirou entre o add e o incr
        cache.set(chave, 1, timeout=BLOQUEIO_LOGIN_SEGUNDOS)


def limpar_falhas_login(email: str) -> None:
    cache.delete(_chave('login_falhas', email))


def pode_pedir_codigo(email: str, segundos: int) -> bool:
    """Um pedido de código por e-mail digitado a cada `segundos`. cache.add só grava se a chave não existe."""
    return cache.add(_chave('reset_limit', email), 1, timeout=segundos)
