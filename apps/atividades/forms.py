from urllib.parse import urlparse

from django import forms

from apps.acompanhamento.models import RegistroEvolucao
from apps.usuarios.forms import BootstrapMixin

from .models import Atividade


PDF_MAX_MB = 10


def link_e_google_forms(url):
    partes = urlparse(url)
    if partes.scheme != 'https':
        return False
    return partes.netloc == 'forms.gle' or (partes.netloc == 'docs.google.com' and partes.path.startswith('/forms/'))


class AtividadeForm(BootstrapMixin, forms.ModelForm):
    """Atividade com material obrigatório: um PDF enviado ou um link do Google Forms, nunca os dois."""

    class Meta:
        model = Atividade
        fields = ['title', 'description', 'category', 'tipo_material', 'arquivo_pdf', 'link_formulario']
        labels = {'description': 'Instruções para o aluno', 'tipo_material': 'Material da atividade'}
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'tipo_material': forms.RadioSelect,
            'arquivo_pdf': forms.ClearableFileInput(attrs={'accept': 'application/pdf,.pdf'}),
            'link_formulario': forms.URLInput(attrs={'placeholder': 'https://forms.gle/...'}),
        }
        help_texts = {
            'category': 'Ex.: reconhecimento de emoções, scripts de conversa, rotinas.',
            'arquivo_pdf': f'Só arquivos PDF, de até {PDF_MAX_MB} MB.',
            'link_formulario': 'Cole o link de compartilhamento do formulário (forms.gle ou docs.google.com/forms).',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_material'].required = True
        self.fields['tipo_material'].choices = Atividade.TipoMaterial.choices  # sem a opção vazia

    def clean_arquivo_pdf(self):
        arquivo = self.cleaned_data.get('arquivo_pdf')
        if not arquivo or not hasattr(arquivo, 'content_type'):  # vazio ou o arquivo que já estava salvo
            return arquivo
        if not arquivo.name.lower().endswith('.pdf'):
            raise forms.ValidationError('Envie um arquivo PDF.')
        if arquivo.size > PDF_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f'O PDF passa de {PDF_MAX_MB} MB. Envie um arquivo menor.')
        inicio = arquivo.read(5)
        arquivo.seek(0)
        if inicio != b'%PDF-':  # nome .pdf não basta: confere o conteúdo
            raise forms.ValidationError('Este arquivo não é um PDF válido.')
        return arquivo

    def clean_link_formulario(self):
        link = self.cleaned_data.get('link_formulario', '').strip()
        if link and not link_e_google_forms(link):
            raise forms.ValidationError('Use um link do Google Forms (https://forms.gle/... ou '
                                        'https://docs.google.com/forms/...).')
        return link

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo_material')
        if tipo == Atividade.TipoMaterial.PDF:
            if not cleaned.get('arquivo_pdf') and 'arquivo_pdf' not in self.errors:
                self.add_error('arquivo_pdf', 'Escolha o arquivo PDF da atividade.')
            cleaned['link_formulario'] = ''
        elif tipo == Atividade.TipoMaterial.FORMULARIO:
            if not cleaned.get('link_formulario') and 'link_formulario' not in self.errors:
                self.add_error('link_formulario', 'Cole o link do Google Forms.')
            cleaned['arquivo_pdf'] = False  # False apaga o arquivo do registro; None manteria o antigo
        return cleaned


class ObservacaoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = RegistroEvolucao
        fields = ['observacoes']
        labels = {'observacoes': 'Anotações'}
        widgets = {'observacoes': forms.Textarea(attrs={'rows': 3})}
