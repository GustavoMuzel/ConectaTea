from django.db import models

from apps.usuarios.models import Aluno, Profissional


class Atividade(models.Model):
    class Publicacao(models.TextChoices):
        PUBLICADA = 'publicada', 'Publicada'
        EM_ANALISE = 'em_analise', 'Aguardando análise do dono da sala'
        RECUSADA = 'recusada', 'Recusada pelo dono da sala'

    class TipoMaterial(models.TextChoices):
        PDF = 'pdf', 'Arquivo PDF'
        FORMULARIO = 'formulario', 'Link do Google Forms'

    id = models.BigAutoField(primary_key=True, db_column='atividade_id')
    # Dono da biblioteca. Atividade proposta numa sala fica na biblioteca do dono da sala.
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE, related_name='atividades')
    # Preenchidos só em atividade postada numa sala: vale apenas para aquele aluno, e "autor" é quem escreveu.
    aluno = models.ForeignKey(Aluno, on_delete=models.PROTECT, related_name='atividades_exclusivas',
                              null=True, blank=True)
    autor = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='atividades_propostas',
                              null=True, blank=True)
    publicacao = models.CharField('publicação', max_length=20, choices=Publicacao.choices,
                                  default=Publicacao.PUBLICADA)
    motivo_recusa = models.TextField('motivo da recusa', blank=True)
    title = models.CharField('título', max_length=150)
    description = models.TextField('descrição', blank=True)
    category = models.CharField('categoria', max_length=50)
    # Material que o aluno abre antes de concluir: um PDF enviado OU um link do Google Forms.
    # Vazio só em atividades antigas, criadas antes desta opção.
    tipo_material = models.CharField('tipo de material', max_length=20, choices=TipoMaterial.choices, blank=True)
    arquivo_pdf = models.FileField('arquivo PDF', upload_to='atividades/%Y/%m/', blank=True)
    link_formulario = models.URLField('link do Google Forms', max_length=500, blank=True)
    arquivada = models.BooleanField(default=False)
    created_at = models.DateTimeField('criada em', auto_now_add=True)

    class Meta:
        db_table = 'atividades'
        verbose_name = 'atividade'
        verbose_name_plural = 'atividades'

    def __str__(self):
        return self.title
