"""Vínculo com aceite do aluno, sala da equipe de cada aluno e videochamada (RF13)."""

import secrets
import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F, Q
from django.utils import timezone

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
    # Próxima chamada combinada pelo dono: previsibilidade ajuda a pessoa autista a se preparar.
    proxima_chamada = models.DateTimeField('próxima videochamada', null=True, blank=True)
    pauta_chamada = models.CharField('o que vamos fazer na chamada', max_length=200, blank=True)
    # Resposta do aluno à chamada marcada. Volta a vazio sempre que o profissional muda o horário.
    resposta_aluno = models.CharField('resposta do aluno', max_length=10, blank=True,
                                      choices=[('sim', 'Vou participar'), ('nao', 'Não vou conseguir')])
    respondida_em = models.DateTimeField('aluno respondeu em', null=True, blank=True)

    class Meta:
        db_table = 'salas'
        verbose_name = 'sala'
        verbose_name_plural = 'salas'

    def __str__(self):
        return f'Sala de {self.aluno}'

    def membros_aprovados(self):
        return self.membros.filter(status=MembroSala.Status.APROVADO).select_related('profissional__user')

    # O aluno só entra na videochamada no horário marcado pelo profissional: de 15 min antes até 2 h depois.
    ABRE_ANTES = timedelta(minutes=15)
    FECHA_DEPOIS = timedelta(hours=2)

    def chamada_vigente(self, agora=None):
        """Há chamada marcada que ainda não terminou (o horário de fechar não passou)."""
        agora = agora or timezone.now()
        return bool(self.proxima_chamada) and agora <= self.proxima_chamada + self.FECHA_DEPOIS

    def chamada_aberta_para_aluno(self, agora=None):
        agora = agora or timezone.now()
        return self.chamada_vigente(agora) and agora >= self.proxima_chamada - self.ABRE_ANTES

    @property
    def chamada_abre_em(self):
        return self.proxima_chamada - self.ABRE_ANTES if self.proxima_chamada else None

    @staticmethod
    def habilitado(profissional):
        """Profissional que ainda pode atuar: aprovado pela administração e com a conta ativa."""
        return profissional.is_approved and profissional.user.is_active

    def ativa(self):
        """A sala funciona enquanto o dono é o profissional do aluno E continua habilitado.
        Se a aprovação do dono for revogada ou a conta desativada, a sala fica parada para todos."""
        return self.dono_id == self.aluno.profissional_id and self.habilitado(self.dono)

    def participa(self, user):
        """Aluno, dono ou membro aprovado, sempre com a sala ativa e o profissional ainda habilitado.
        Confere de novo a cada acesso: revogar a aprovação corta também a videochamada."""
        if not user.is_active or not self.ativa():
            return False
        if user.pk in (self.aluno.user_id, self.dono.user_id):
            return True
        return self.membros.filter(
            profissional__user=user, status=MembroSala.Status.APROVADO,
            profissional__is_approved=True, profissional__user__is_active=True,
        ).exists()

    def na_chamada_agora(self):
        """Participações com entrada confirmada pelo Jitsi e sem saída nas últimas 3 horas."""
        limite = timezone.now() - timedelta(hours=3)
        return (self.participacoes_video.filter(entrou_em__gte=limite, saiu_em__isnull=True)
                .select_related('user').order_by('entrou_em'))


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
    """Uso da videochamada da sala (RF13). Áudio e vídeo nunca são gravados.

    acionada_em: a pessoa abriu a chamada no ConectaTEA. entrou_em e saiu_em: confirmados pelos eventos do
    próprio Jitsi (videoConferenceJoined / videoConferenceLeft) na chamada embutida. Na chamada aberta em outra
    aba, só há o acionamento: o sistema não tem como saber se a pessoa entrou de fato.
    """

    class Forma(models.TextChoices):
        EMBUTIDA = 'embutida', 'Dentro do ConectaTEA'
        NOVA_ABA = 'nova_aba', 'Em outra aba'

    id = models.BigAutoField(primary_key=True, db_column='participacao_id')
    sala = models.ForeignKey(Sala, on_delete=models.PROTECT, related_name='participacoes_video')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='participacoes_video')
    forma = models.CharField(max_length=20, choices=Forma.choices, default=Forma.EMBUTIDA)
    acionada_em = models.DateTimeField('acionada em', auto_now_add=True)
    entrou_em = models.DateTimeField('entrada confirmada em', null=True, blank=True)
    saiu_em = models.DateTimeField('saída confirmada em', null=True, blank=True)

    class Meta:
        db_table = 'participacoes_sala'
        verbose_name = 'participação em videochamada'
        verbose_name_plural = 'participações em videochamada'
        ordering = ['-acionada_em', '-pk']

    def __str__(self):
        return f'{self.user} na {self.sala} ({self.acionada_em:%d/%m/%Y %H:%M})'

    @property
    def duracao(self):
        if self.entrou_em and self.saiu_em:
            return self.saiu_em - self.entrou_em
        return None


def alunos_do_profissional(profissional):
    """Alunos que o profissional acompanha: os seus (dono) e os das salas em que foi aprovado.
    A sala só vale enquanto o dono dela ainda é o profissional do aluno e continua aprovado e ativo."""
    return Aluno.objects.filter(
        Q(profissional=profissional)
        | Q(sala__membros__profissional=profissional, sala__membros__status=MembroSala.Status.APROVADO,
            sala__dono=F('profissional'), sala__dono__is_approved=True, sala__dono__user__is_active=True),
    ).distinct()
