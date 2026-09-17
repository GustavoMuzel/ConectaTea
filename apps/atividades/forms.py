from django import forms

from apps.acompanhamento.models import RegistroEvolucao
from apps.usuarios.forms import BootstrapMixin

from .models import Atividade


class AtividadeForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Atividade
        fields = ['title', 'description', 'category']
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}
        help_texts = {'category': 'Ex.: reconhecimento de emoções, scripts de conversa, rotinas.'}


class ObservacaoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = RegistroEvolucao
        fields = ['observacoes']
        labels = {'observacoes': 'Anotações'}
        widgets = {'observacoes': forms.Textarea(attrs={'rows': 3})}
