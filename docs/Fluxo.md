# Fluxo de Uso e Testes: ConectaTEA

Guia prático para rodar o sistema, testá-lo e entender o caminho que Profissional e Aluno
percorrem na aplicação.

## 1. Como testar

### Suíte automatizada

```bash
pytest
```

Esse comando roda toda a suíte (models, forms, views e integração) com `pytest-django`, usando
`config.settings` (configurado em [pytest.ini](../pytest.ini)). Os arquivos reconhecidos como
teste seguem o padrão `tests.py` e `test_*.py` dentro de cada app em `apps/`.

Para checar cobertura de um app específico:

```bash
pytest apps/acompanhamento -v
```

### Ambiente local e superusuário

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

O superusuário criado por `createsuperuser` tem acesso total a `/admin/`. É o caminho mais
rápido para aprovar o primeiro Profissional (ver seção 2), sem depender de outro gestor já
aprovado.

## 2. Fluxo do Profissional

1. **Cadastro**: em `/cadastro/`, escolhe o perfil "Profissional" e preenche especialidade
   (obrigatória) e registro profissional (opcional). O cadastro cria `User` + `Profissional`
   na mesma transação ([forms.py](../apps/usuarios/forms.py)) e já autentica o usuário.
2. **Aprovação**: todo Profissional nasce com `is_approved=False`. Sem aprovação, ele não
   aparece como opção de "profissional responsável" no cadastro de Alunos. Um gestor aprova por
   duas vias:
   - **Painel Admin** (`/admin/`): em `Profissionais`, editar o registro e marcar
     "aprovado" (requer a permissão `usuarios.change_profissional`);
   - **Painel de gestão** (`/painel-gestao/`): lista os profissionais pendentes e permite
     aprovar com um clique (`AprovarProfissionalGestaoView`).
3. **Acesso ao painel web**: uma vez aprovado, o Profissional loga em `/entrar/` e cai direto
   em `/painel/` (rota `painel`), com a lista de atividades que já cadastrou.
4. **Criação de atividades**: no próprio `/painel/`, o formulário cria uma nova `Atividade`
   já vinculada ao Profissional logado (nunca a partir do POST, por segurança).
5. **Alunos e evolução**: `/painel/alunos/` traz os Alunos vinculados a ele; abrindo um Aluno
   (`/painel/alunos/<id>/`), o Profissional vê o histórico de atividades concluídas e pode
   registrar uma observação qualitativa em cada uma (`SalvarObservacaoView`).

## 3. Fluxo do Aluno

1. **Cadastro**: em `/cadastro/`, escolhe o perfil "Aluno", seleciona o Profissional
   responsável (só entram os aprovados e ativos) e informa data de nascimento e dados do
   responsável legal.
2. **Consentimento do responsável (obrigatório)**: a caixa "o responsável legal autorizou
   este cadastro..." é validada em `CadastroForm.clean()`; sem marcá-la, o cadastro não passa.
   Ao salvar, o timestamp vai para `Aluno.consentimento_data`, que serve como registro formal
   do consentimento (LGPD, por se tratar de dado de menor de idade).
3. **Área exclusiva**: logado, o Aluno cai em `/aluno/atividades/` (rota `aluno_atividades`),
   protegida por `AlunoRequiredMixin`.
4. **Atividades pendentes**: a lista traz só as atividades do Profissional do Aluno que ele
   ainda não concluiu (um Profissional reprovado ou desativado some dela automaticamente, ver
   `atividades_do_aluno()`).
5. **Execução com confirmação em duas etapas (UX inclusiva)**: um toque na atividade não a
   conclui na hora; ele abre `/aluno/atividades/<id>/confirmar/`, uma tela intermediária que só
   registra a conclusão após um segundo clique explícito
   (`POST /aluno/atividades/<id>/concluir/`). Isso evita que um toque acidental na lista marque
   algo como feito. Confirmar de novo uma atividade já concluída não gera um segundo registro
   (constraint `uma_conclusao_por_aluno_atividade`).

## 4. Acompanhamento de evolução

- O Profissional acessa o histórico de um Aluno em `/painel/alunos/<id>/`, restrito aos
  próprios Alunos (`EvolucaoAlunoView.get_queryset`); o id de um Aluno de outro Profissional
  retorna 404.
- A tela lista cada `RegistroEvolucao` com status `concluida`, do mais recente ao mais antigo
  (`data_realizacao` decrescente).
- Cada registro tem um campo de observação qualitativa (`ObservacaoForm`), salvo via
  `POST /painel/alunos/<aluno_id>/registros/<id>/observacoes/`; é ali que o Profissional
  documenta como o Aluno se saiu na atividade.
