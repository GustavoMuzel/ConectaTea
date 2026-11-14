"""Avisa por e-mail o responsável de cada aluno que tem atividades com prazo vencido.

Para rodar uma vez por dia (Agendador de Tarefas do Windows, cron ou "Cron Job" do Render):
    python manage.py avisar_atrasadas
Use --simular para só listar quantos avisos sairiam, sem enviar nada.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.acompanhamento.views import atividades_pendentes
from apps.usuarios.models import Aluno
from apps.usuarios.services.email import enviar_aviso_atividades_atrasadas


class Command(BaseCommand):
    help = 'Envia ao responsável o aviso de atividades com prazo vencido.'

    def add_arguments(self, parser):
        parser.add_argument('--simular', action='store_true', help='Só conta os avisos, sem enviar e-mails.')

    def handle(self, *args, **options):
        hoje = timezone.localdate()
        avisos = 0
        alunos = Aluno.objects.filter(user__is_active=True, profissional__isnull=False).select_related('user')
        for aluno in alunos:
            atrasadas = [a for a in atividades_pendentes(aluno) if a.prazo and a.prazo < hoje]
            if not atrasadas:
                continue
            avisos += 1
            if not options['simular']:
                enviar_aviso_atividades_atrasadas(aluno, len(atrasadas))
        acao = 'seriam enviados' if options['simular'] else 'enviados'
        self.stdout.write(self.style.SUCCESS(f'{avisos} aviso(s) de atividades atrasadas {acao}.'))
