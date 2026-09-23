import datetime

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError

from .models import Aluno, Profissional, User


@pytest.mark.django_db
def test_relacionamentos_usuarios():
    prof_user = User.objects.create_user('prof@ex.com', 'Prof', 'senha-forte-123', role=User.Role.PROFISSIONAL)
    aluno_user = User.objects.create_user('aluno@ex.com', 'Aluno', 'senha-forte-123', role=User.Role.ALUNO)
    prof = Profissional.objects.create(user=prof_user, especialidade='Psicologia')
    aluno = Aluno.objects.create(
        user=aluno_user, profissional=prof, birth_date=datetime.date(2011, 5, 1),
        guardian_name='Resp', guardian_phone='11999999999', guardian_email='resp@ex.com',
    )

    assert aluno_user.check_password('senha-forte-123')
    assert prof_user.profissional == prof
    assert aluno_user.aluno == aluno
    assert list(prof.alunos.all()) == [aluno]
    with pytest.raises(ProtectedError):
        prof.delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        Profissional.objects.create(user=prof_user, especialidade='Outra')
