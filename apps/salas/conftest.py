import datetime

import pytest

from apps.usuarios.models import Aluno, Profissional, User

SENHA = 'Senha-forte-123'


@pytest.fixture
def criar_prof(db):
    def _criar(email, aprovado=True):
        user = User.objects.create_user(email, email.split('@')[0].title(), SENHA, role=User.Role.PROFISSIONAL)
        return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=aprovado)
    return _criar


@pytest.fixture
def criar_aluno(db):
    def _criar(email, profissional=None, ativo=True):
        user = User.objects.create_user(email, email.split('@')[0].title(), SENHA, role=User.Role.ALUNO,
                                        is_active=ativo)
        return Aluno.objects.create(user=user, profissional=profissional, birth_date=datetime.date(2011, 1, 1),
                                    guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')
    return _criar
