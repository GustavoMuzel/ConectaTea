import pytest

from apps.usuarios.models import Profissional, User

from .models import Atividade


@pytest.mark.django_db
def test_atividade_pertence_ao_profissional_e_cascateia():
    user = User.objects.create_user('prof@ex.com', 'Prof', 'senha-forte-123', role=User.Role.PROFISSIONAL)
    prof = Profissional.objects.create(user=user, especialidade='Psicologia')
    atividade = Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social')

    assert atividade.created_at is not None
    assert list(prof.atividades.all()) == [atividade]
    prof.delete()
    assert not Atividade.objects.exists()
