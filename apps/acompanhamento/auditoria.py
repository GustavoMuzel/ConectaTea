"""Registro de auditoria: um ponto só para gravar as ações, com o IP de quem fez."""

from .models import LogAcesso

Categoria = LogAcesso.Categoria


def ip_do_pedido(request):
    """IP de quem fez o pedido. No Render (atrás de proxy), o IP real vem no primeiro item do X-Forwarded-For."""
    if request is None:
        return None
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = encaminhado.split(',')[0].strip() if encaminhado else request.META.get('REMOTE_ADDR')
    return ip or None


def registrar(request, acao, categoria, user=None, aluno=None):
    if user is None and request is not None and getattr(request, 'user', None) and request.user.is_authenticated:
        user = request.user
    return LogAcesso.objects.create(user=user, aluno=aluno, categoria=categoria, acao=acao[:200],
                                    ip=ip_do_pedido(request))
