"""Alunos que já tinham profissional antes das salas ganham a sala deles, com esse profissional como dono."""

import secrets
import uuid

from django.db import migrations

ALFABETO_SENHA = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


def criar_salas(apps, schema_editor):
    Aluno = apps.get_model('usuarios', 'Aluno')
    Sala = apps.get_model('salas', 'Sala')
    usadas = set(Sala.objects.values_list('senha', flat=True))
    for aluno in Aluno.objects.filter(profissional__isnull=False, sala__isnull=True):
        senha = ''.join(secrets.choice(ALFABETO_SENHA) for _ in range(6))
        while senha in usadas:
            senha = ''.join(secrets.choice(ALFABETO_SENHA) for _ in range(6))
        usadas.add(senha)
        Sala.objects.create(aluno=aluno, dono_id=aluno.profissional_id, senha=senha, id_videochamada=uuid.uuid4())


class Migration(migrations.Migration):
    dependencies = [
        ('salas', '0001_initial'),
        ('usuarios', '0007_aluno_profissional_opcional'),
    ]

    operations = [migrations.RunPython(criar_salas, migrations.RunPython.noop)]
