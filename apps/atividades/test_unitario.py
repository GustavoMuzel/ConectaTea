"""Testes unitários das regras do material da atividade (PDF ou Google Forms). Sem banco e sem rede."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from .forms import PDF_MAX_MB, AtividadeForm, link_e_google_forms
from .models import Atividade

pytestmark = pytest.mark.unit

PDF = b'%PDF-1.7\n%conteudo de teste\n'


def dados(**campos):
    return {'title': 'Aula 1', 'description': 'Siga os passos.', 'category': 'Scripts de conversa', **campos}


def pdf(nome='aula.pdf', conteudo=PDF, tipo='application/pdf'):
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


# Link do Google Forms -------------------------------------------------------------------------------------

@pytest.mark.parametrize('url', [
    'https://forms.gle/AbC123xyz',
    'https://docs.google.com/forms/d/e/1FAIpQLSc/viewform',
])
def test_links_do_google_forms_sao_aceitos(url):
    assert link_e_google_forms(url) is True


@pytest.mark.parametrize('url', [
    'http://forms.gle/AbC123xyz',                    # sem HTTPS
    'https://docs.google.com/document/d/123/edit',   # Google Docs, não Forms
    'https://forms.gle.golpe.example/AbC',           # domínio parecido
    'https://golpe.example/forms/d/123',             # caminho parecido em outro domínio
    'javascript:alert(1)',
    '',
])
def test_outros_links_sao_recusados(url):
    assert link_e_google_forms(url) is False


# Atividade com PDF -----------------------------------------------------------------------------------------

def test_atividade_com_pdf_valido():
    form = AtividadeForm(data=dados(tipo_material='pdf'), files={'arquivo_pdf': pdf()})
    assert form.is_valid(), form.errors


def test_pdf_e_obrigatorio_quando_o_material_e_pdf():
    form = AtividadeForm(data=dados(tipo_material='pdf'))
    assert not form.is_valid()
    assert form.errors['arquivo_pdf'] == ['Escolha o arquivo PDF da atividade.']


def test_arquivo_que_nao_termina_em_pdf_e_recusado():
    form = AtividadeForm(data=dados(tipo_material='pdf'), files={'arquivo_pdf': pdf(nome='aula.docx')})
    assert not form.is_valid()
    assert form.errors['arquivo_pdf'] == ['Envie um arquivo PDF.']


def test_nome_pdf_com_conteudo_que_nao_e_pdf_e_recusado():
    falso = pdf(nome='aula.pdf', conteudo=b'MZ\x90\x00 executavel disfarcado')
    form = AtividadeForm(data=dados(tipo_material='pdf'), files={'arquivo_pdf': falso})
    assert not form.is_valid()
    assert form.errors['arquivo_pdf'] == ['Este arquivo não é um PDF válido.']


def test_pdf_no_limite_de_tamanho_e_aceito():
    no_limite = pdf(conteudo=PDF + b'0' * (PDF_MAX_MB * 1024 * 1024 - len(PDF)))
    form = AtividadeForm(data=dados(tipo_material='pdf'), files={'arquivo_pdf': no_limite})
    assert form.is_valid(), form.errors


def test_pdf_acima_de_10_mb_e_recusado():
    grande = pdf(conteudo=PDF + b'0' * (PDF_MAX_MB * 1024 * 1024 - len(PDF) + 1))
    form = AtividadeForm(data=dados(tipo_material='pdf'), files={'arquivo_pdf': grande})
    assert not form.is_valid()
    assert form.errors['arquivo_pdf'] == ['O PDF passa de 10 MB. Envie um arquivo menor.']


def test_validar_o_pdf_nao_consome_o_arquivo():
    arquivo = pdf()
    form = AtividadeForm(data=dados(tipo_material='pdf'), files={'arquivo_pdf': arquivo})
    assert form.is_valid()
    assert form.cleaned_data['arquivo_pdf'].read(5) == b'%PDF-'


def test_material_pdf_descarta_o_link_enviado_junto():
    form = AtividadeForm(data=dados(tipo_material='pdf', link_formulario='https://forms.gle/AbC'),
                         files={'arquivo_pdf': pdf()})
    assert form.is_valid()
    assert form.cleaned_data['link_formulario'] == ''


# Atividade com Google Forms --------------------------------------------------------------------------------

def test_atividade_com_google_forms_valida():
    form = AtividadeForm(data=dados(tipo_material='formulario', link_formulario='  https://forms.gle/AbC  '))
    assert form.is_valid(), form.errors
    assert form.cleaned_data['link_formulario'] == 'https://forms.gle/AbC'


def test_link_e_obrigatorio_quando_o_material_e_formulario():
    form = AtividadeForm(data=dados(tipo_material='formulario'))
    assert not form.is_valid()
    assert form.errors['link_formulario'] == ['Cole o link do Google Forms.']


def test_link_que_nao_e_do_google_forms_e_recusado():
    form = AtividadeForm(data=dados(tipo_material='formulario', link_formulario='https://golpe.example/forms'))
    assert not form.is_valid()
    assert 'Use um link do Google Forms' in form.errors['link_formulario'][0]


def test_material_formulario_apaga_o_pdf_antigo():
    form = AtividadeForm(data=dados(tipo_material='formulario', link_formulario='https://forms.gle/AbC'),
                         files={'arquivo_pdf': pdf()})
    assert form.is_valid()
    assert form.cleaned_data['arquivo_pdf'] is False  # False apaga o arquivo do registro


# Campos obrigatórios ---------------------------------------------------------------------------------------

def test_tipo_de_material_e_obrigatorio_e_sem_opcao_vazia():
    form = AtividadeForm(data=dados())
    assert not form.is_valid()
    assert 'tipo_material' in form.errors
    assert [valor for valor, _ in form.fields['tipo_material'].choices] == ['pdf', 'formulario']


@pytest.mark.parametrize('campo', ['title', 'category'])
def test_titulo_e_categoria_sao_obrigatorios(campo):
    form = AtividadeForm(data=dados(tipo_material='formulario', link_formulario='https://forms.gle/AbC',
                                    **{campo: ''}))
    assert not form.is_valid()
    assert campo in form.errors


def test_atividade_aparece_pelo_titulo():
    assert str(Atividade(title='Aula 1: Começar uma conversa')) == 'Aula 1: Começar uma conversa'
