from django.db import models
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno


class RegistroEvolucao(models.Model):
    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        EM_ANDAMENTO = 'em_andamento', 'Em andamento'
        CONCLUIDA = 'concluida', 'Concluída'

    id = models.BigAutoField(primary_key=True, db_column='registro_id')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='registros_evolucao')
    atividade = models.ForeignKey(Atividade, on_delete=models.PROTECT, related_name='registros_evolucao')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    observacoes = models.TextField('observações', blank=True)
    data_realizacao = models.DateTimeField('data de realização', default=timezone.now)

    class Meta:
        db_table = 'registros_evolucao'
        verbose_name = 'registro de evolução'
        verbose_name_plural = 'registros de evolução'
        constraints = [
            # Duplo clique ou duas abas não geram duas conclusões da mesma atividade.
            models.UniqueConstraint(
                fields=['aluno', 'atividade'], condition=models.Q(status='concluida'),
                name='uma_conclusao_por_aluno_atividade',
            ),
        ]

    def __str__(self):
        return f'{self.aluno} - {self.atividade} ({self.get_status_display()})'
