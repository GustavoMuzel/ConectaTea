from django.db import models

from apps.usuarios.models import Profissional


class Atividade(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='atividade_id')
    profissional = models.ForeignKey(Profissional, on_delete=models.CASCADE, related_name='atividades')
    title = models.CharField('título', max_length=150)
    description = models.TextField('descrição', blank=True)
    category = models.CharField('categoria', max_length=50)
    created_at = models.DateTimeField('criada em', auto_now_add=True)

    class Meta:
        db_table = 'atividades'
        verbose_name = 'atividade'
        verbose_name_plural = 'atividades'

    def __str__(self):
        return self.title
