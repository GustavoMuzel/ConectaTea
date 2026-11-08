from django import forms

from apps.atividades.forms import AtividadeForm
from apps.usuarios.forms import BootstrapMixin


class EntrarSalaForm(BootstrapMixin, forms.Form):
    senha = forms.CharField(label='Senha da sala', max_length=12,
                            help_text='Peça a senha ao profissional dono da sala. Ela tem 6 letras e números.')

    def clean_senha(self):
        return self.cleaned_data['senha'].strip().upper().replace(' ', '')


class PropostaAtividadeForm(AtividadeForm):
    """Mesmas regras de material (PDF ou Google Forms) da biblioteca."""


class RecusaAtividadeForm(BootstrapMixin, forms.Form):
    motivo = forms.CharField(label='Motivo da recusa (o autor vai ler)', required=False,
                             widget=forms.Textarea(attrs={'rows': 2}))
