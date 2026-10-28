from django import forms
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import Aluno, PreferenciaAcessibilidade, Profissional, User


class BootstrapMixin:
    """Aplica as classes do Bootstrap aos widgets; o template fica só com o laço de campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.RadioSelect, forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                css = 'form-check-input'
            elif isinstance(widget, forms.Select):
                css = 'form-select'
            else:
                css = 'form-control'
            widget.attrs['class'] = css
            field.template_name = 'partials/_campo.html'


class LoginForm(BootstrapMixin, AuthenticationForm):
    pass


class CadastroForm(BootstrapMixin, BaseUserCreationForm):
    # Só perfis de cadastro público; "admin" nunca pode ser escolhido aqui.
    PERFIS = [(User.Role.ALUNO, 'Aluno'), (User.Role.PROFISSIONAL, 'Profissional')]
    CAMPOS_ALUNO = ['profissional', 'birth_date', 'guardian_name', 'guardian_phone', 'guardian_email']

    role = forms.ChoiceField(label='Perfil', choices=PERFIS, widget=forms.RadioSelect)

    # Perfil profissional
    especialidade = forms.CharField(label='Especialidade', max_length=100, required=False,
                                    help_text='Ex.: psicologia, terapia ocupacional, pedagogia.')
    registro_profissional = forms.CharField(label='Registro profissional (opcional)', max_length=50,
                                            required=False)

    # Perfil aluno
    profissional = forms.ModelChoiceField(
        label='Profissional responsável', required=False,
        queryset=(Profissional.objects.filter(is_approved=True, user__is_active=True)
                  .select_related('user').order_by('user__name')),
    )
    birth_date = forms.DateField(label='Data de nascimento', required=False,
                                 widget=forms.DateInput(attrs={'type': 'date'}))
    guardian_name = forms.CharField(label='Nome do responsável', max_length=150, required=False)
    guardian_phone = forms.CharField(label='Telefone do responsável', max_length=20, required=False)
    guardian_email = forms.EmailField(label='E-mail do responsável', required=False)
    # Grava o timestamp em Aluno.consentimento_data; só barra o cadastro sem a marcação (LGPD, dados de menor).
    consentimento_responsavel = forms.BooleanField(required=False)

    class Meta:
        model = User
        fields = ['name', 'email', 'role']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['consentimento_responsavel'].label = format_html(
            'O responsável legal pelo aluno autorizou este cadastro e o uso destes dados, '
            'conforme os <a href="{}" target="_blank" rel="noopener">Termos de Uso</a> e a '
            '<a href="{}" target="_blank" rel="noopener">Política de Privacidade</a>.',
            reverse('termos'), reverse('privacidade'),
        )

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('Já existe uma conta com este e-mail.')
        return email

    def clean_birth_date(self):
        data = self.cleaned_data.get('birth_date')
        if data and data >= timezone.localdate():
            raise forms.ValidationError('A data de nascimento precisa ser anterior a hoje.')
        return data

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        obrigatorios = {User.Role.ALUNO: self.CAMPOS_ALUNO, User.Role.PROFISSIONAL: ['especialidade']}.get(role, [])
        for campo in obrigatorios:
            if not cleaned.get(campo) and campo not in self.errors:
                self.add_error(campo, 'Preencha este campo.')
        if role == User.Role.ALUNO and not cleaned.get('consentimento_responsavel'):
            self.add_error('consentimento_responsavel', 'Marque esta caixa para continuar.')
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        # Sempre grava: User e perfil nascem juntos ou nenhum dos dois.
        user = super().save(commit=True)
        dados = self.cleaned_data
        if user.role == User.Role.PROFISSIONAL:
            Profissional.objects.create(
                user=user, especialidade=dados['especialidade'],
                registro_profissional=dados['registro_profissional'] or None,
            )
        else:
            Aluno.objects.create(
                user=user, consentimento_data=timezone.now(),
                **{c: dados[c] for c in self.CAMPOS_ALUNO},
            )
        return user


class PreferenciasForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = PreferenciaAcessibilidade
        fields = ['tamanho_fonte', 'alto_contraste', 'reduzir_estimulos']
        labels = {
            'tamanho_fonte': 'Tamanho da letra',
            'alto_contraste': 'Alto contraste (fundo preto e letras claras)',
            'reduzir_estimulos': 'Reduzir estímulos (sem sombras e sem enfeites)',
        }
        widgets = {'tamanho_fonte': forms.RadioSelect}
