import re

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm, BaseUserCreationForm
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import UFS, Aluno, PreferenciaAcessibilidade, Profissional, User
from .services import limites


# Número do registro: 1-2 dígitos da região, separador opcional, 3-7 dígitos e sufixo opcional
# (cobre 06/123456 do CRP, 12345-TO do CREFITO, 2-12345 do CRFa e números só com dígitos).
REGISTRO_RE = re.compile(r'^[0-9]{1,2}[/.-]?[0-9]{3,7}(-?[A-Z]{1,2})?$')


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
    error_messages = {
        'invalid_login': 'E-mail ou senha incorretos. Confira os dados e tente de novo.',
        'inactive': 'Esta conta está desativada. Fale com a administração da instituição para reativá-la.',
        'bloqueado': 'Muitas tentativas erradas com este e-mail. Por segurança, espere 15 minutos e tente de '
                     'novo, ou use "Esqueci minha senha".',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'E-mail'
        self.fields['username'].widget.attrs.update({'autocomplete': 'email', 'inputmode': 'email'})
        self.fields['password'].label = 'Senha'

    def clean(self):
        email = self.cleaned_data.get('username')
        # RNF04: depois de 5 erros seguidos, nem confere a senha (vale também para a senha certa).
        if email and limites.login_bloqueado(email):
            from apps.acompanhamento.auditoria import Categoria, registrar  # import local: evita ciclo entre apps

            registrar(self.request, 'Login bloqueado: 5 tentativas erradas seguidas', Categoria.AUTENTICACAO,
                      user=User.objects.filter(email__iexact=email).first())
            raise forms.ValidationError(self.error_messages['bloqueado'], code='bloqueado')
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            limites.registrar_falha_login(email)
            # O ModelBackend recusa conta inativa como se a senha estivesse errada; aqui damos o motivo
            # real, mas só a quem acertou a senha (não revela se um e-mail existe).
            email, senha = self.cleaned_data.get('username'), self.cleaned_data.get('password')
            usuario = User.objects.filter(email__iexact=email or '', is_active=False).first()
            if usuario and senha and usuario.check_password(senha):
                raise forms.ValidationError(self.error_messages['inactive'], code='inactive')
            raise
        limites.limpar_falhas_login(email)
        return cleaned


class RecuperarSenhaForm(BootstrapMixin, forms.Form):
    email = forms.EmailField(label='E-mail da conta', max_length=254,
                             widget=forms.EmailInput(attrs={'autocomplete': 'email'}))


class CodigoNovaSenhaForm(BootstrapMixin, forms.Form):
    """Código recebido por e-mail + senha nova (RF03, CA03). A conferência do código fica na view."""

    codigo = forms.RegexField(
        label='Código de 6 números', regex=r'^\d{6}$', max_length=6,
        error_messages={'invalid': 'O código tem 6 números.'},
        widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code'}),
    )
    nova_senha1 = forms.CharField(label='Senha nova', strip=False,
                                  widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
                                  help_text=password_validation.password_validators_help_text_html())
    nova_senha2 = forms.CharField(label='Repita a senha nova', strip=False,
                                  widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))

    def clean_codigo(self):
        return self.cleaned_data['codigo'].strip()

    def clean(self):
        cleaned = super().clean()
        senha1, senha2 = cleaned.get('nova_senha1'), cleaned.get('nova_senha2')
        if senha1 and senha2 and senha1 != senha2:
            self.add_error('nova_senha2', 'As duas senhas não são iguais.')
        return cleaned

    def validar_senha_para(self, user):
        """RN04: mesmos validadores do cadastro. Só roda depois que o código conferiu."""
        try:
            password_validation.validate_password(self.cleaned_data['nova_senha1'], user)
        except forms.ValidationError as erro:
            self.add_error('nova_senha1', erro)
            return False
        return True


class CadastroForm(BootstrapMixin, BaseUserCreationForm):
    # Só perfis de cadastro público; "admin" nunca pode ser escolhido aqui.
    PERFIS = [(User.Role.ALUNO, 'Aluno'), (User.Role.PROFISSIONAL, 'Profissional')]
    CAMPOS_ALUNO = ['birth_date', 'guardian_name', 'guardian_phone', 'guardian_email']

    role = forms.ChoiceField(label='Perfil', choices=PERFIS, widget=forms.RadioSelect)

    # Perfil profissional: profissão e registro no conselho, conferidos pelo gestor antes da aprovação.
    profissao = forms.ChoiceField(label='Profissão', required=False,
                                  choices=[('', 'Escolha a sua profissão')] + Profissional.Profissao.choices)
    uf_registro = forms.ChoiceField(label='Estado (UF) do registro', required=False,
                                    choices=[('', 'Escolha o estado')] + UFS)
    numero_registro = forms.CharField(
        label='Número do registro no conselho', max_length=20, required=False,
        help_text='Como aparece na sua carteira. Ex.: 06/123456 (CRP), 12345-TO (CREFITO), 2-12345 (CRFa).',
    )
    area_atuacao = forms.CharField(label='Área de atuação (opcional)', max_length=60, required=False,
                                   help_text='Ex.: ABA, alfabetização, comunicação alternativa.')

    # Perfil aluno (o profissional responsável é vinculado depois, pelo próprio profissional aprovado)
    birth_date = forms.DateField(label='Data de nascimento', required=False,
                                 widget=forms.DateInput(attrs={'type': 'date'}))
    guardian_name = forms.CharField(label='Nome do responsável', max_length=150, required=False)
    guardian_phone = forms.CharField(label='Telefone do responsável', max_length=20, required=False)
    guardian_email = forms.EmailField(label='E-mail do responsável', required=False)
    # Grava o timestamp em Aluno.consentimento_data; só barra o cadastro sem a marcação (LGPD, dados de menor).
    consentimento_responsavel = forms.BooleanField(required=False)
    # Todos os perfis: aceite dos documentos e autorização do tratamento dos próprios dados.
    aceite_termos = forms.BooleanField(
        required=True, error_messages={'required': 'Para criar a conta, é preciso ler e aceitar os termos.'},
    )

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
        self.fields['aceite_termos'].label = format_html(
            'Li e aceito os <a href="{}" target="_blank" rel="noopener">Termos de Uso</a> e a '
            '<a href="{}" target="_blank" rel="noopener">Política de Privacidade</a>, e autorizo o '
            'tratamento dos meus dados pessoais para o uso do ConectaTEA.',
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

    def clean_numero_registro(self):
        numero = ''.join(self.cleaned_data.get('numero_registro', '').split()).upper()
        if numero and not REGISTRO_RE.match(numero):
            raise forms.ValidationError('Confira o número: use só números, com "/" ou "-" se a carteira tiver '
                                        '(ex.: 06/123456 ou 12345-TO).')
        return numero

    def _campos_profissional(self, cleaned):
        profissao = cleaned.get('profissao')
        campos = ['profissao']
        if profissao in Profissional.CONSELHOS:
            campos += ['uf_registro', 'numero_registro']
            ja_existe = Profissional.objects.filter(
                profissao=profissao, uf_registro=cleaned.get('uf_registro'),
                numero_registro=cleaned.get('numero_registro'),
            ).exists()
            if cleaned.get('numero_registro') and ja_existe:
                self.add_error('numero_registro', 'Este registro já está cadastrado em outra conta.')
        return campos

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        obrigatorios = self.CAMPOS_ALUNO if role == User.Role.ALUNO else []
        if role == User.Role.PROFISSIONAL:
            obrigatorios = self._campos_profissional(cleaned)
        for campo in obrigatorios:
            if not cleaned.get(campo) and campo not in self.errors:
                self.add_error(campo, 'Preencha este campo.')
        if role == User.Role.ALUNO and not cleaned.get('consentimento_responsavel'):
            self.add_error('consentimento_responsavel', 'Marque esta caixa para continuar.')
        return cleaned

    @transaction.atomic
    def save(self, commit=True):
        # Sempre grava: User e perfil nascem juntos ou nenhum dos dois.
        user = super().save(commit=False)
        user.termos_aceitos_em = timezone.now()
        user.save()
        dados = self.cleaned_data
        if user.role == User.Role.PROFISSIONAL:
            profissao = dados['profissao']
            rotulo = Profissional.Profissao(profissao).label
            profissional = Profissional(
                user=user, profissao=profissao,
                especialidade=f"{rotulo} · {dados['area_atuacao']}" if dados['area_atuacao'] else rotulo,
            )
            if profissao in Profissional.CONSELHOS:
                profissional.uf_registro, profissional.numero_registro = dados['uf_registro'], dados['numero_registro']
                profissional.registro_profissional = profissional.registro_formatado
            profissional.save()
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
