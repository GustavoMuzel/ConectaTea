from django.db import models
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional


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


class Atribuicao(models.Model):
    """Atividade distribuída pelo profissional a um aluno (RF07)."""

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Pendente'
        EM_ANDAMENTO = 'em_andamento', 'Em andamento'
        CONCLUIDA = 'concluida', 'Concluída'
        CANCELADA = 'cancelada', 'Cancelada'

    id = models.BigAutoField(primary_key=True, db_column='atribuicao_id')
    atividade = models.ForeignKey(Atividade, on_delete=models.PROTECT, related_name='atribuicoes')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='atribuicoes')
    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='atribuicoes')
    atribuida_em = models.DateTimeField('atribuída em', auto_now_add=True)
    prazo = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)

    class Meta:
        db_table = 'atribuicoes'
        verbose_name = 'atribuição'
        verbose_name_plural = 'atribuições'
        ordering = ['-atribuida_em']
        constraints = [
            models.UniqueConstraint(fields=['atividade', 'aluno'], name='uma_atribuicao_por_aluno_atividade'),
        ]

    def __str__(self):
        return f'{self.aluno} - {self.atividade} ({self.get_status_display()})'
