from django.conf import settings


def preferencias(request):
    # Visitante, ou quem nunca abriu a tela de preferências, fica com o padrão (prefs vazio).
    contexto = {'prefs': getattr(request.user, 'preferencias', None), 'contato_email': settings.CONTATO_EMAIL}
    user = getattr(request, 'user', None)
    if (user is not None and user.is_authenticated and user.is_aluno and not user.is_aluno_sem_vinculo
            and user.aluno.pk):
        from apps.acompanhamento.views import atividades_pendentes  # import local: evita ciclo entre apps

        # Contador do menu "Minhas atividades": quantas o aluno ainda tem para fazer.
        contexto['aluno_pendentes'] = atividades_pendentes(user.aluno).count()
    if user is not None and user.is_authenticated and user.is_profissional:
        from apps.acompanhamento.models import PedidoAjuda

        contexto['pedidos_ajuda_abertos'] = PedidoAjuda.objects.filter(
            aluno__profissional=user.profissional, respondido_em__isnull=True).count()
    return contexto
