from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from datetime import timedelta

from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError('O e-mail é obrigatório.')
        user = self.model(email=email.strip().lower(), name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def get_by_natural_key(self, username):
        return self.get(email__iexact=username)  # login não diferencia maiúsculas

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.update(role=User.Role.ADMIN, is_staff=True, is_superuser=True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Tabela `users`. A coluna `password` guarda o hash (password_hash do diagrama)."""

    class Role(models.TextChoices):
        ALUNO = 'aluno', 'Aluno'
        PROFISSIONAL = 'profissional', 'Profissional'
        ADMIN = 'admin', 'Administrador'

    id = models.BigAutoField(primary_key=True, db_column='user_id')
    name = models.CharField('nome', max_length=150)
    email = models.EmailField('e-mail', unique=True)
    role = models.CharField('perfil', max_length=20, choices=Role.choices)
    is_active = models.BooleanField('ativo', default=True, db_column='active')
    is_staff = models.BooleanField('acesso ao admin', default=False)
    created_at = models.DateTimeField('criado em', auto_now_add=True)
    # Aceite dos Termos de Uso e da Política de Privacidade no cadastro (LGPD, art. 8º).
    termos_aceitos_em = models.DateTimeField('termos aceitos em', null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    class Meta:
        db_table = 'users'
        verbose_name = 'usuário'
        verbose_name_plural = 'usuários'

    def __str__(self):
        return f'{self.name} <{self.email}>'

    @property
    def email_parcial(self):
        """'maria@ex.com' -> 'm***@ex.com': identifica sem expor o e-mail inteiro (LGPD, aluno menor)."""
        local, _, dominio = self.email.partition('@')
        return f'{local[:1]}***@{dominio}'

    @property
    def is_profissional(self):
        # Profissional só atua depois de aprovado pelo admin.
        return self.role == self.Role.PROFISSIONAL and hasattr(self, 'profissional') and self.profissional.is_approved

    @property
    def is_profissional_pendente(self):
        return (self.role == self.Role.PROFISSIONAL and hasattr(self, 'profissional')
                and not self.profissional.is_approved)

    @property
    def is_aluno(self):
        return self.role == self.Role.ALUNO and hasattr(self, 'aluno')

    @property
    def is_aluno_sem_vinculo(self):
        return self.is_aluno and self.aluno.profissional_id is None


UFS = [(uf, uf) for uf in (
    'AC', 'AL', 'AM', 'AP', 'BA', 'CE', 'DF', 'ES', 'GO', 'MA', 'MG', 'MS', 'MT', 'PA', 'PB', 'PE', 'PI', 'PR',
    'RJ', 'RN', 'RO', 'RR', 'RS', 'SC', 'SE', 'SP', 'TO',
)]


class Profissional(models.Model):
    class Profissao(models.TextChoices):
        PEDAGOGIA = 'pedagogia', 'Pedagogia'
        PSICOLOGIA = 'psicologia', 'Psicologia'
        TERAPIA_OCUPACIONAL = 'terapia_ocupacional', 'Terapia ocupacional'
        FONOAUDIOLOGIA = 'fonoaudiologia', 'Fonoaudiologia'

    # Conselho de classe de cada profissão: (sigla, nome, site oficial onde o gestor confere o registro).
    # Pedagogia não tem conselho profissional: a conferência é feita por outro documento (ex.: da instituição).
    CONSELHOS = {
        Profissao.PSICOLOGIA: ('CRP', 'Conselho Regional de Psicologia', 'https://cadastro.cfp.org.br/'),
        Profissao.TERAPIA_OCUPACIONAL: ('CREFITO', 'Conselho Regional de Fisioterapia e Terapia Ocupacional',
                                        'https://www.coffito.gov.br/'),
        Profissao.FONOAUDIOLOGIA: ('CRFa', 'Conselho Regional de Fonoaudiologia',
                                   'https://www.fonoaudiologia.org.br/'),
    }

    id = models.BigAutoField(primary_key=True, db_column='profissional_id')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profissional')
    # Rótulo exibido nas telas: profissão e, se informada, a área de atuação (ex.: "Psicologia · ABA").
    especialidade = models.CharField(max_length=100)
    profissao = models.CharField('profissão', max_length=30, choices=Profissao.choices, blank=True)
    uf_registro = models.CharField('UF do registro', max_length=2, choices=UFS, blank=True)
    numero_registro = models.CharField('número do registro', max_length=20, blank=True)
    # Campo antigo, de texto livre; contas novas preenchem com o registro formatado.
    registro_profissional = models.CharField('registro profissional', max_length=50, null=True, blank=True)
    is_approved = models.BooleanField('aprovado', default=False)
    # Quem aprovou e quando: a aprovação vale como conferência do registro no site do conselho.
    aprovado_em = models.DateTimeField('aprovado em', null=True, blank=True)
    aprovado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
                                     verbose_name='aprovado por')

    class Meta:
        db_table = 'profissionais'
        verbose_name = 'profissional'
        verbose_name_plural = 'profissionais'
        constraints = [
            # O mesmo registro não pode servir para duas contas.
            models.UniqueConstraint(fields=['profissao', 'uf_registro', 'numero_registro'],
                                    condition=~models.Q(numero_registro=''), name='registro_unico_por_conselho'),
        ]

    def __str__(self):
        return f'{self.user.name} ({self.especialidade})'

    @property
    def conselho(self):
        """(sigla, nome, site) do conselho da profissão, ou None (pedagogia e contas antigas)."""
        return self.CONSELHOS.get(self.profissao)

    @property
    def registro_formatado(self):
        if self.conselho and self.numero_registro:
            return f'{self.conselho[0]}-{self.uf_registro} {self.numero_registro}'
        return self.registro_profissional or ''


class Aluno(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='aluno_id')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='aluno')
    # PROTECT: excluir um profissional não pode apagar os alunos vinculados a ele.
    # Remoção de usuários é só por soft delete (User.is_active=False); o histórico nunca é apagado.
    # Vazio até um profissional aprovado vincular o aluno a ele (o aluno não escolhe no cadastro).
    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='alunos',
                                     null=True, blank=True)
    birth_date = models.DateField('data de nascimento')
    guardian_name = models.CharField('nome do responsável', max_length=150)
    guardian_phone = models.CharField('telefone do responsável', max_length=20)
    guardian_email = models.EmailField('e-mail do responsável')
    consentimento_data = models.DateTimeField('consentimento do responsável em', null=True, blank=True)

    class Meta:
        db_table = 'alunos'
        verbose_name = 'aluno'
        verbose_name_plural = 'alunos'

    def __str__(self):
        return self.user.name


class PreferenciaAcessibilidade(models.Model):
    """Ajustes visuais do usuário, aplicados em todas as telas (RF14)."""

    class TamanhoFonte(models.TextChoices):
        NORMAL = 'normal', 'Normal'
        GRANDE = 'grande', 'Grande'
        MUITO_GRANDE = 'muito_grande', 'Muito grande'

    id = models.BigAutoField(primary_key=True, db_column='preferencia_id')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferencias')
    tamanho_fonte = models.CharField('tamanho da letra', max_length=20, choices=TamanhoFonte.choices,
                                     default=TamanhoFonte.NORMAL)
    alto_contraste = models.BooleanField('alto contraste', default=False)
    reduzir_estimulos = models.BooleanField('reduzir estímulos', default=False)

    class Meta:
        db_table = 'preferencias_acessibilidade'
        verbose_name = 'preferência de acessibilidade'
        verbose_name_plural = 'preferências de acessibilidade'

    def __str__(self):
        return f'Preferências de {self.user.name}'


class CodigoVerificacao(models.Model):
    """Código de 6 dígitos da recuperação de senha (RF03). Só o hash é guardado."""

    VALIDADE = timedelta(minutes=10)
    MAX_TENTATIVAS = 5

    id = models.BigAutoField(primary_key=True, db_column='codigo_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='codigos_verificacao')
    codigo_hash = models.CharField('hash do código', max_length=128)
    criado_em = models.DateTimeField('criado em', auto_now_add=True)
    expira_em = models.DateTimeField('expira em')
    tentativas = models.PositiveSmallIntegerField('tentativas erradas', default=0)
    usado_em = models.DateTimeField('usado em', null=True, blank=True)

    class Meta:
        db_table = 'codigos_verificacao'
        verbose_name = 'código de verificação'
        verbose_name_plural = 'códigos de verificação'
        ordering = ['-criado_em', '-pk']

    def __str__(self):
        return f'Código de {self.user.email} ({self.criado_em:%d/%m/%Y %H:%M})'

    @property
    def valido(self):
        return self.usado_em is None and self.tentativas < self.MAX_TENTATIVAS and timezone.now() < self.expira_em
