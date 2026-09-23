import datetime

import pytest
from django.db.models import ProtectedError
from django.urls import reverse

from apps.atividades.models import Atividade
from apps.usuarios.models import Aluno, Profissional, User

from .models import RegistroEvolucao


@pytest.fixture
def registro():
    prof_user = User.objects.create_user('prof@ex.com', 'Prof', 'senha-forte-123', role=User.Role.PROFISSIONAL)
    aluno_user = User.objects.create_user('aluno@ex.com', 'Aluno', 'senha-forte-123', role=User.Role.ALUNO)
    prof = Profissional.objects.create(user=prof_user, especialidade='Psicologia')
    aluno = Aluno.objects.create(
        user=aluno_user, profissional=prof, birth_date=datetime.date(2011, 5, 1),
        guardian_name='Resp', guardian_phone='11999999999', guardian_email='resp@ex.com',
    )
    atividade = Atividade.objects.create(profissional=prof, title='Cumprimentar', category='social')
    return RegistroEvolucao.objects.create(aluno=aluno, atividade=atividade)


@pytest.mark.django_db
def test_registro_padroes_e_relacoes(registro):
    assert registro.status == RegistroEvolucao.Status.PENDENTE
    assert registro.data_realizacao is not None
    assert list(registro.aluno.registros_evolucao.all()) == [registro]
    assert list(registro.atividade.registros_evolucao.all()) == [registro]


@pytest.mark.django_db
@pytest.mark.parametrize('apagar', [lambda r: r.aluno, lambda r: r.aluno.user])
def test_aluno_com_historico_nao_pode_ser_apagado(registro, apagar):
    with pytest.raises(ProtectedError):
        apagar(registro).delete()
    assert RegistroEvolucao.objects.filter(pk=registro.pk).exists()


@pytest.mark.django_db
def test_atividade_com_historico_nao_pode_ser_apagada(registro):
    with pytest.raises(ProtectedError):
        registro.atividade.delete()
    assert RegistroEvolucao.objects.filter(pk=registro.pk).exists()


@pytest.mark.django_db
def test_admin_nao_apaga_registro_de_evolucao(client, registro):
    client.force_login(User.objects.create_superuser('admin@ex.com', 'Admin', 'senha-forte-123'))
    url = reverse('admin:acompanhamento_registroevolucao_changelist')

    assert client.post(reverse('admin:acompanhamento_registroevolucao_delete', args=[registro.pk]),
                       {'post': 'yes'}).status_code == 403
    assert client.get(url).context['action_form'] is None  # delete_selected era a única action
    assert RegistroEvolucao.objects.filter(pk=registro.pk).exists()
