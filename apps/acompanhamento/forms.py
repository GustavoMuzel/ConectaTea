from django import forms
from django.utils import timezone

from apps.atividades.models import Atividade
from apps.usuarios.forms import BootstrapMixin
from apps.usuarios.models import Aluno


class DistribuicaoAtividadeForm(BootstrapMixin, forms.Form):
    atividade = forms.ModelChoiceField(Atividade.objects.none(), label='Atividade')
    alunos = forms.ModelMultipleChoiceField(
        Aluno.objects.none(), label='Alunos', widget=forms.CheckboxSelectMultiple,
    )
    prazo = forms.DateField(
        required=False, label='Prazo (opcional)', widget=forms.DateInput(attrs={'type': 'date'}),
    )

    def __init__(self, *args, profissional, **kwargs):
        super().__init__(*args, **kwargs)
        # RN01 e RN02: só atividades ativas do próprio profissional e alunos vinculados a ele.
        self.fields['atividade'].queryset = profissional.atividades.filter(arquivada=False)
        self.fields['alunos'].queryset = profissional.alunos.filter(user__is_active=True).select_related('user')

    def clean_prazo(self):
        prazo = self.cleaned_data['prazo']
        if prazo and prazo < timezone.localdate():
            raise forms.ValidationError('O prazo não pode ser anterior a hoje.')
        return prazo
