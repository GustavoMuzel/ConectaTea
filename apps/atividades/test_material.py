"""Material da atividade (PDF ou Google Forms) e resposta escrita do aluno."""
import datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.acompanhamento.models import RegistroEvolucao
from apps.usuarios.models import Aluno, Profissional, User

from .models import Atividade

SENHA = 'Senha-forte-123'
PDF = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF'


@pytest.fixture(autouse=True)
def media_temporaria(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def prof():
    user = User.objects.create_user('prof@ex.com', 'Prof', SENHA, role=User.Role.PROFISSIONAL)
    return Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)


@pytest.fixture
def aluno(prof):
    user = User.objects.create_user('aluno@ex.com', 'Aluno', SENHA, role=User.Role.ALUNO)
    return Aluno.objects.create(user=user, profissional=prof, birth_date=datetime.date(2011, 1, 1),
                                guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')


def _criar(client, prof, **extra):
    client.force_login(prof.user)
    return client.post(reverse('painel'), {'title': 'Ler', 'category': 'leitura', **extra})


def _pdf(nome='atividade.pdf', conteudo=PDF):
    return SimpleUploadedFile(nome, conteudo, content_type='application/pdf')


# Profissional cria -------------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_cria_atividade_com_pdf(client, prof):
    resp = _criar(client, prof, tipo_material='pdf', arquivo_pdf=_pdf())
    assert resp.status_code == 302
    atividade = Atividade.objects.get()
    assert atividade.tipo_material == 'pdf' and atividade.arquivo_pdf and not atividade.link_formulario


@pytest.mark.django_db
@pytest.mark.parametrize('link', ['https://forms.gle/abc123', 'https://docs.google.com/forms/d/e/xyz/viewform'])
def test_cria_atividade_com_google_forms(client, prof, link):
    assert _criar(client, prof, tipo_material='formulario', link_formulario=link).status_code == 302
    assert Atividade.objects.get().link_formulario == link


@pytest.mark.django_db
@pytest.mark.parametrize('extra, campo', [
    ({}, 'tipo_material'),
    ({'tipo_material': 'pdf'}, 'arquivo_pdf'),
    ({'tipo_material': 'formulario'}, 'link_formulario'),
    ({'tipo_material': 'formulario', 'link_formulario': 'https://site-malicioso.com/forms/x'}, 'link_formulario'),
    ({'tipo_material': 'formulario', 'link_formulario': 'http://forms.gle/abc'}, 'link_formulario'),
])
def test_material_obrigatorio_e_validado(client, prof, extra, campo):
    resp = _criar(client, prof, **extra)
    assert resp.status_code == 200 and campo in resp.context['form'].errors
    assert not Atividade.objects.exists()


@pytest.mark.django_db
def test_recusa_arquivo_que_nao_e_pdf(client, prof):
    for arquivo in [_pdf('foto.png'), _pdf('falso.pdf', b'MZ\x90\x00 executavel')]:
        resp = _criar(client, prof, tipo_material='pdf', arquivo_pdf=arquivo)
        assert 'arquivo_pdf' in resp.context['form'].errors
    assert not Atividade.objects.exists()


@pytest.mark.django_db
def test_recusa_pdf_grande(client, prof):
    grande = _pdf(conteudo=PDF + b'0' * (10 * 1024 * 1024))
    assert 'arquivo_pdf' in _criar(client, prof, tipo_material='pdf', arquivo_pdf=grande).context['form'].errors


@pytest.mark.django_db
def test_trocar_pdf_por_formulario_limpa_o_pdf(client, prof):
    _criar(client, prof, tipo_material='pdf', arquivo_pdf=_pdf())
    atividade = Atividade.objects.get()
    client.post(reverse('editar_atividade', args=[atividade.pk]), {
        'title': 'Ler', 'category': 'leitura', 'tipo_material': 'formulario', 'link_formulario': 'https://forms.gle/x',
    })
    atividade.refresh_from_db()
    assert atividade.tipo_material == 'formulario' and not atividade.arquivo_pdf


# Aluno faz ---------------------------------------------------------------------------------------------------

@pytest.mark.django_db
def test_aluno_precisa_abrir_o_material_e_escrever_para_concluir(client, prof, aluno):
    _criar(client, prof, tipo_material='pdf', arquivo_pdf=_pdf())
    atividade = Atividade.objects.get()
    client.force_login(aluno.user)
    concluir = reverse('concluir_atividade', args=[atividade.pk])

    resp = client.post(concluir, {'resposta': 'Li tudo'})  # ainda não abriu o PDF
    assert resp.status_code == 200 and 'Abra o material' in resp.content.decode()
    assert not RegistroEvolucao.objects.exists()

    resp = client.get(reverse('material_atividade', args=[atividade.pk]))
    assert resp.status_code == 200 and resp['Content-Type'] == 'application/pdf'
    assert b''.join(resp.streaming_content).startswith(b'%PDF-')

    resp = client.post(concluir, {'resposta': ''})  # sem resposta
    assert 'resposta' in resp.context['form'].errors and not RegistroEvolucao.objects.exists()

    resp = client.post(concluir, {'resposta': 'Li tudo e gostei'})
    assert resp.url == reverse('aluno_atividades')
    assert RegistroEvolucao.objects.get().resposta == 'Li tudo e gostei'


@pytest.mark.django_db
def test_formulario_leva_ao_google_forms(client, prof, aluno):
    _criar(client, prof, tipo_material='formulario', link_formulario='https://forms.gle/abc')
    atividade = Atividade.objects.get()
    client.force_login(aluno.user)
    resp = client.get(reverse('material_atividade', args=[atividade.pk]))
    assert resp.status_code == 302 and resp.url == 'https://forms.gle/abc'
    assert client.post(reverse('concluir_atividade', args=[atividade.pk]), {'resposta': 'ok'}).status_code == 302


@pytest.mark.django_db
def test_profissional_ve_a_resposta_na_evolucao(client, prof, aluno):
    atividade = Atividade.objects.create(profissional=prof, title='Antiga', category='x')  # sem material: legado
    RegistroEvolucao.objects.create(aluno=aluno, atividade=atividade, status='concluida', resposta='Minha resposta')
    client.force_login(prof.user)
    assert 'Minha resposta' in client.get(reverse('evolucao_aluno', args=[aluno.pk])).content.decode()


@pytest.mark.django_db
def test_pdf_nao_e_publico(client, prof, aluno):
    _criar(client, prof, tipo_material='pdf', arquivo_pdf=_pdf())
    url = reverse('material_atividade', args=[Atividade.objects.get().pk])
    client.logout()
    assert client.get(url).status_code == 302  # visitante vai para o login
    outro_user = User.objects.create_user('o@ex.com', 'Outro', SENHA, role=User.Role.PROFISSIONAL)
    client.force_login(Profissional.objects.create(user=outro_user, especialidade='X', is_approved=True).user)
    assert client.get(url).status_code == 404
    outro_prof = Profissional.objects.get(user=outro_user)
    aluno_de_outro = Aluno.objects.create(
        user=User.objects.create_user('a2@ex.com', 'A2', SENHA, role=User.Role.ALUNO), profissional=outro_prof,
        birth_date=datetime.date(2011, 1, 1), guardian_name='R', guardian_phone='1', guardian_email='r@ex.com')
    client.force_login(aluno_de_outro.user)
    assert client.get(url).status_code == 404
