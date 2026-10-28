from django.db import models
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User


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
            # O aluno pode refazer (várias conclusões), mas só tem uma tentativa em andamento por atividade.
            models.UniqueConstraint(
                fields=['aluno', 'atividade'], condition=models.Q(status='em_andamento'),
                name='uma_em_andamento_por_aluno_atividade',
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


class AnotacaoQuerySet(models.QuerySet):
    def visiveis_para(self, usuario, aluno):
        """Anotações sobre o aluno que `usuario` (o aluno ou o profissional dele) pode ler: as suas, mais
        as compartilhadas pelo outro participante do vínculo atual. Quem não é participante não lê nada."""
        profissional_uid = aluno.profissional.user_id
        if usuario.pk == aluno.user_id:
            outro_id = profissional_uid
        elif usuario.pk == profissional_uid:
            outro_id = aluno.user_id
        else:
            return self.none()
        return self.filter(aluno=aluno).filter(
            models.Q(autor=usuario) | models.Q(autor_id=outro_id, visibilidade=Anotacao.Visibilidade.COMPARTILHADA),
        )


class Anotacao(models.Model):
    """Texto sobre um aluno, escrito por ele ou pelo profissional (RF11)."""

    class Visibilidade(models.TextChoices):
        PRIVADA = 'privada', 'Privada'
        COMPARTILHADA = 'compartilhada', 'Compartilhada'

    id = models.BigAutoField(primary_key=True, db_column='anotacao_id')
    autor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='anotacoes')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='anotacoes')
    texto = models.TextField()
    visibilidade = models.CharField(max_length=20, choices=Visibilidade.choices, default=Visibilidade.PRIVADA)
    criado_em = models.DateTimeField('criada em', auto_now_add=True)
    atualizado_em = models.DateTimeField('atualizada em', auto_now=True)

    objects = AnotacaoQuerySet.as_manager()

    class Meta:
        db_table = 'anotacoes'
        verbose_name = 'anotação'
        verbose_name_plural = 'anotações'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'{self.autor} sobre {self.aluno} ({self.get_visibilidade_display()})'


class LogAcesso(models.Model):
    """Auditoria de acesso a dados de um aluno, p.ex. o profissional vendo o histórico dele (RF10, RNF05)."""

    id = models.BigAutoField(primary_key=True, db_column='log_acesso_id')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='logs_acesso')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='logs_acesso')
    acao = models.CharField('ação', max_length=100)
    ocorrido_em = models.DateTimeField('ocorrido em', auto_now_add=True)

    class Meta:
        db_table = 'logs_acesso'
        verbose_name = 'log de acesso'
        verbose_name_plural = 'logs de acesso'
        ordering = ['-ocorrido_em', '-pk']

    def __str__(self):
        return f'{self.user} - {self.acao} ({self.aluno})'
