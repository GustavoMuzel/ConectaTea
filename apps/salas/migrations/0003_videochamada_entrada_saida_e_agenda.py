"""Videochamada: o registro antigo era só o acionamento; entrada e saída passam a vir dos eventos do Jitsi."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('salas', '0002_salas_dos_alunos_ja_vinculados'),
    ]

    operations = [
        migrations.RenameField('participacaovideochamada', 'entrou_em', 'acionada_em'),
        migrations.AlterField(
            model_name='participacaovideochamada', name='acionada_em',
            field=models.DateTimeField(auto_now_add=True, verbose_name='acionada em'),
        ),
        migrations.AddField(
            model_name='participacaovideochamada', name='forma',
            field=models.CharField(choices=[('embutida', 'Dentro do ConectaTEA'), ('nova_aba', 'Em outra aba')],
                                   default='nova_aba', max_length=20),
        ),
        migrations.AlterField(
            model_name='participacaovideochamada', name='forma',
            field=models.CharField(choices=[('embutida', 'Dentro do ConectaTEA'), ('nova_aba', 'Em outra aba')],
                                   default='embutida', max_length=20),
        ),
        migrations.AddField(
            model_name='participacaovideochamada', name='entrou_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='entrada confirmada em'),
        ),
        migrations.AddField(
            model_name='participacaovideochamada', name='saiu_em',
            field=models.DateTimeField(blank=True, null=True, verbose_name='saída confirmada em'),
        ),
        migrations.AlterModelOptions(
            name='participacaovideochamada',
            options={'ordering': ['-acionada_em', '-pk'], 'verbose_name': 'participação em videochamada',
                     'verbose_name_plural': 'participações em videochamada'},
        ),
        migrations.AddField(
            model_name='sala', name='proxima_chamada',
            field=models.DateTimeField(blank=True, null=True, verbose_name='próxima videochamada'),
        ),
        migrations.AddField(
            model_name='sala', name='pauta_chamada',
            field=models.CharField(blank=True, max_length=200, verbose_name='o que vamos fazer na chamada'),
        ),
    ]
