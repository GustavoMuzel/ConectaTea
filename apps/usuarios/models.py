from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


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
    def is_profissional(self):
        # Profissional só atua depois de aprovado pelo admin.
        return self.role == self.Role.PROFISSIONAL and hasattr(self, 'profissional') and self.profissional.is_approved

    @property
    def is_aluno(self):
        return self.role == self.Role.ALUNO and hasattr(self, 'aluno')


class Profissional(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='profissional_id')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profissional')
    especialidade = models.CharField(max_length=100)
    registro_profissional = models.CharField('registro profissional', max_length=50, null=True, blank=True)
    is_approved = models.BooleanField('aprovado', default=False)

    class Meta:
        db_table = 'profissionais'
        verbose_name = 'profissional'
        verbose_name_plural = 'profissionais'

    def __str__(self):
        return f'{self.user.name} ({self.especialidade})'


class Aluno(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='aluno_id')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='aluno')
    # PROTECT: excluir um profissional não pode apagar os alunos vinculados a ele.
    # Remoção de usuários é só por soft delete (User.is_active=False); o histórico nunca é apagado.
    profissional = models.ForeignKey(Profissional, on_delete=models.PROTECT, related_name='alunos')
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
