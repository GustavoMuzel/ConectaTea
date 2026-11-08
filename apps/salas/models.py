"""Vínculo com aceite do aluno, sala da equipe de cada aluno e videochamada (RF13)."""

import secrets
import uuid

from django.db import models
from django.db.models import F, Q

from apps.usuarios.models import Aluno, Profissional, User

# Sem 0/O e 1/I/L, que se confundem ao ditar a senha.
ALFABETO_SENHA = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


def gerar_senha_sala():
    return ''.join(secrets.choice(ALFABETO_SENHA) for _ in range(6))


class SolicitacaoVinculo(models.Model):
    """Pedido do profissional aprovado para acompanhar um aluno sem vínculo. Só vale depois que o aluno aceita."""

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Aguardando o aluno'
        ACEITA = 'aceita', 'Aceita'
        RECUSADA = 'recusada', 'Recusada'
        CANCELADA = 'cancelada', 'Cancelada'

    id = models.BigAutoField(primary_key=True, db_column='solicitacao_id')
    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='solicitacoes_vinculo')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='solicitacoes_vinculo')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    criada_em = models.DateTimeField('enviada em', auto_now_add=True)
    respondida_em = models.DateTimeField('respondida em', null=True, blank=True)

    class Meta:
        db_table = 'solicitacoes_vinculo'
        verbose_name = 'solicitação de vínculo'
        verbose_name_plural = 'solicitações de vínculo'
        ordering = ['-criada_em', '-pk']
        constraints = [
            models.UniqueConstraint(fields=['profissional', 'aluno'], condition=Q(status='pendente'),
                                    name='um_pedido_pendente_por_profissional_aluno'),
        ]

    def __str__(self):
        return f'{self.profissional} → {self.aluno} ({self.get_status_display()})'


class Sala(models.Model):
    """Sala da equipe que acompanha um aluno. Nasce quando o aluno aceita o vínculo; o profissional é o dono."""

    id = models.BigAutoField(primary_key=True, db_column='sala_id')
    aluno = models.OneToOneField(Aluno, on_delete=models.PROTECT, related_name='sala')
    dono = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='salas_criadas')
    senha = models.CharField('senha de acesso', max_length=12, unique=True, default=gerar_senha_sala)
    # Nome da sala no Jitsi: aleatório, para ninguém adivinhar e entrar na chamada (RF13).
    id_videochamada = models.UUIDField('identificador da videochamada', default=uuid.uuid4, unique=True,
                                       editable=False)
    criada_em = models.DateTimeField('criada em', auto_now_add=True)

    class Meta:
        db_table = 'salas'
        verbose_name = 'sala'
        verbose_name_plural = 'salas'

    def __str__(self):
        return f'Sala de {self.aluno}'

    def membros_aprovados(self):
        return self.membros.filter(status=MembroSala.Status.APROVADO).select_related('profissional__user')

    def participa(self, user):
        """O próprio aluno; dono e membros aprovados só enquanto o dono ainda é o profissional do aluno.
        Se o vínculo mudou ou foi desfeito, a sala fica dormente para toda a equipe antiga."""
        if user.pk == self.aluno.user_id:
            return True
        if self.dono_id != self.aluno.profissional_id:
            return False
        if user.pk == self.dono.user_id:
            return True
        return self.membros.filter(profissional__user=user, status=MembroSala.Status.APROVADO).exists()


class MembroSala(models.Model):
    """Profissional que pediu para entrar na sala com a senha. Só participa depois que o dono aprova."""

    class Status(models.TextChoices):
        PENDENTE = 'pendente', 'Aguardando o dono'
        APROVADO = 'aprovado', 'Aprovado'
        RECUSADO = 'recusado', 'Recusado'
        REMOVIDO = 'removido', 'Removido'

    id = models.BigAutoField(primary_key=True, db_column='membro_id')
    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name='membros')
    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='participacoes')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDENTE)
    solicitado_em = models.DateTimeField('pedido em', auto_now_add=True)
    respondido_em = models.DateTimeField('respondido em', null=True, blank=True)

    class Meta:
        db_table = 'membros_sala'
        verbose_name = 'membro da sala'
        verbose_name_plural = 'membros da sala'
        ordering = ['solicitado_em', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['sala', 'profissional'], name='um_registro_por_profissional_sala'),
        ]

    def __str__(self):
        return f'{self.profissional} em {self.sala} ({self.get_status_display()})'


class ParticipacaoVideochamada(models.Model):
    """Quem entrou na videochamada da sala e quando. Áudio e vídeo nunca são gravados (RF13)."""

    id = models.BigAutoField(primary_key=True, db_column='participacao_id')
    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name='participacoes_video')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='participacoes_video')
    entrou_em = models.DateTimeField('entrou em', auto_now_add=True)

    class Meta:
        db_table = 'participacoes_sala'
        verbose_name = 'participação em videochamada'
        verbose_name_plural = 'participações em videochamada'
        ordering = ['-entrou_em', '-pk']

    def __str__(self):
        return f'{self.user} na {self.sala} ({self.entrou_em:%d/%m/%Y %H:%M})'


def alunos_do_profissional(profissional):
    """Alunos que o profissional acompanha: os seus (dono) e os das salas em que foi aprovado.
    A sala só vale enquanto o dono dela ainda é o profissional do aluno."""
    return Aluno.objects.filter(
        Q(profissional=profissional)
        | Q(sala__membros__profissional=profissional, sala__membros__status=MembroSala.Status.APROVADO,
            sala__dono=F('profissional')),
    ).distinct()
