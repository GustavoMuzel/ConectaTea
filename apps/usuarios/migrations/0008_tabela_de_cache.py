"""Cria a tabela do DatabaseCache (settings.CACHES) junto com o migrate, também no banco de testes."""

from django.core.management import call_command
from django.db import migrations


def criar_tabela_de_cache(apps, schema_editor):
    call_command('createcachetable', database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):
    dependencies = [
        ('usuarios', '0007_aluno_profissional_opcional'),
    ]

    operations = [migrations.RunPython(criar_tabela_de_cache, migrations.RunPython.noop)]
