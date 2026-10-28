def preferencias(request):
    # Visitante, ou quem nunca abriu a tela de preferências, fica com o padrão (prefs vazio).
    return {'prefs': getattr(request.user, 'preferencias', None)}
