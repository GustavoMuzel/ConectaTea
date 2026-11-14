from django import forms
from django.utils import timezone

from apps.atividades.forms import AtividadeForm
from apps.usuarios.forms import BootstrapMixin

from .models import Sala


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


class AgendaChamadaForm(BootstrapMixin, forms.ModelForm):
    """O dono combina a próxima chamada: o aluno vê dia, hora e o que vai acontecer."""

    class Meta:
        model = Sala
        fields = ['proxima_chamada', 'pauta_chamada']
        labels = {'proxima_chamada': 'Dia e hora da videochamada', 'pauta_chamada': 'O que vamos fazer (opcional)'}
        widgets = {'proxima_chamada': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')}
        help_texts = {'pauta_chamada': 'Ex.: conversar sobre a atividade de cumprimentos. Avisar antes ajuda o aluno.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['proxima_chamada'].input_formats = ['%Y-%m-%dT%H:%M']

    def clean_proxima_chamada(self):
        quando = self.cleaned_data.get('proxima_chamada')
        if quando and quando < timezone.now():
            raise forms.ValidationError('Escolha um dia e hora que ainda não passaram.')
        return quando
