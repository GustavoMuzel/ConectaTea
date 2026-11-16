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
    resposta = models.TextField('resposta do aluno', blank=True)
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
        if aluno.profissional_id is None:  # sem vínculo não há "outro participante"
            return self.filter(aluno=aluno, autor=usuario)
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
    """Auditoria (RF10, RNF05): quem fez o quê, quando e de qual IP.

    Cobre o acesso a dados de alunos e também entrada/saída, gestão, atividades e salas. O IP atende ao art. 15
    do Marco Civil da Internet (guarda dos registros de acesso a aplicações). Só leitura: não se edita nem apaga.
    """

    class Categoria(models.TextChoices):
        DADOS_ALUNO = 'dados_aluno', 'Dados de aluno'
        AUTENTICACAO = 'autenticacao', 'Entrada e conta'
        GESTAO = 'gestao', 'Gestão'
        ATIVIDADES = 'atividades', 'Atividades'
        SALAS = 'salas', 'Salas e vínculos'

    id = models.BigAutoField(primary_key=True, db_column='log_acesso_id')
    # Vazio só em tentativa de login com e-mail que não existe.
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='logs_acesso', null=True, blank=True)
    # Preenchido quando a ação envolve um aluno.
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='logs_acesso', null=True, blank=True)
    categoria = models.CharField(max_length=20, choices=Categoria.choices, default=Categoria.DADOS_ALUNO)
    acao = models.CharField('ação', max_length=200)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    ocorrido_em = models.DateTimeField('ocorrido em', auto_now_add=True)

    class Meta:
        db_table = 'logs_acesso'
        verbose_name = 'log de acesso'
        verbose_name_plural = 'logs de acesso'
        ordering = ['-ocorrido_em', '-pk']

    def __str__(self):
        return f'{self.user or "?"} - {self.acao}'


class PedidoAjuda(models.Model):
    """Botão "Preciso de ajuda" da atividade: o aluno avisa o profissional responsável, que marca como respondido.

    Saber pedir ajuda é uma das dificuldades citadas no guia da UNESP; o pedido tem um clique e texto opcional.
    """

    id = models.BigAutoField(primary_key=True, db_column='pedido_ajuda_id')
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='pedidos_ajuda')
    atividade = models.ForeignKey(Atividade, on_delete=models.PROTECT, related_name='pedidos_ajuda')
    mensagem = models.TextField('o que está difícil', blank=True)
    criado_em = models.DateTimeField('pedido em', auto_now_add=True)
    respondido_em = models.DateTimeField('respondido em', null=True, blank=True)
    respondido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        db_table = 'pedidos_ajuda'
        verbose_name = 'pedido de ajuda'
        verbose_name_plural = 'pedidos de ajuda'
        ordering = ['-criado_em', '-pk']
        constraints = [
            # Um pedido aberto por atividade: clicar de novo não manda outro aviso.
            models.UniqueConstraint(fields=['aluno', 'atividade'], condition=models.Q(respondido_em__isnull=True),
                                    name='um_pedido_de_ajuda_aberto_por_atividade'),
        ]

    def __str__(self):
        return f'{self.aluno} pediu ajuda em {self.atividade}'
