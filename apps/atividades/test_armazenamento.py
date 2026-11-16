"""PDFs guardados no banco (ARMAZENAMENTO_ARQUIVOS=banco), usado no Render, cujo disco é temporário."""
import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.acompanhamento.models import Atribuicao
from apps.usuarios.models import Aluno, Profissional, User

from .models import ArquivoArmazenado, Atividade

pytestmark = pytest.mark.integration

PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'
SENHA = 'Senha-forte-123'


@pytest.fixture
def no_banco(settings):
    settings.STORAGES = {**settings.STORAGES,
                         'default': {'BACKEND': 'apps.atividades.armazenamento.BancoDeDadosStorage'}}


@pytest.mark.django_db
def test_pdf_vai_para_o_banco_e_volta_para_o_aluno(client, no_banco):
    pu = User.objects.create_user('p@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    prof = Profissional.objects.create(user=pu, especialidade='Psicologia', is_approved=True)
    au = User.objects.create_user('a@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    aluno = Aluno.objects.create(user=au, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                 guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')
    client.force_login(pu)
    client.post(reverse('painel'), {'title': 'Ler', 'category': 'leitura', 'tipo_material': 'pdf',
                                    'arquivo_pdf': SimpleUploadedFile('ler.pdf', PDF, 'application/pdf')})
    atividade = Atividade.objects.get()
    guardado = ArquivoArmazenado.objects.get()
    assert guardado.nome == atividade.arquivo_pdf.name and bytes(guardado.conteudo) == PDF
    assert guardado.tamanho == len(PDF)

    Atribuicao.objects.create(atividade=atividade, aluno=aluno, profissional=prof)
    client.force_login(au)
    resp = client.get(reverse('material_atividade', args=[atividade.pk]))
    assert resp.status_code == 200 and b''.join(resp.streaming_content) == PDF


@pytest.mark.django_db
def test_nomes_repetidos_nao_sobrescrevem(no_banco):
    from django.core.files.storage import default_storage
    primeiro = default_storage.save('atividades/x.pdf', SimpleUploadedFile('x.pdf', PDF))
    segundo = default_storage.save('atividades/x.pdf', SimpleUploadedFile('x.pdf', PDF + b'2'))
    assert primeiro != segundo and ArquivoArmazenado.objects.count() == 2
    default_storage.delete(primeiro)
    assert not default_storage.exists(primeiro) and default_storage.exists(segundo)
