# Fluxo de Uso e Testes — ConectaTEA

Guia prático para rodar o sistema, testá-lo e entender o caminho que Profissional e Aluno
percorrem na aplicação.

## 1. Como testar

### Suíte automatizada

```bash
pytest
```

Roda toda a suíte (models, forms, views e integração) com `pytest-django`, usando
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

O superusuário criado por `createsuperuser` acessa `/admin/` com acesso total — é o caminho
mais rápido para aprovar o primeiro Profissional (ver seção 2) sem depender de outro gestor já
aprovado.

## 2. Fluxo do Profissional

1. **Cadastro** — em `/cadastro/`, escolhe o perfil "Profissional" e preenche especialidade
   (obrigatória) e registro profissional (opcional). O cadastro cria `User` + `Profissional`
   na mesma transação ([forms.py](../apps/usuarios/forms.py)) e já autentica o usuário.
2. **Aprovação** — todo Profissional nasce com `is_approved=False`. Sem aprovação, ele não
   aparece como opção de "profissional responsável" no cadastro de Alunos. Um gestor aprova de
   duas formas:
   - **Painel Admin** (`/admin/`): em `Profissionais`, editar o registro e marcar
     "aprovado" (requer permissão `usuarios.change_profissional`);
   - **Painel de gestão** (`/painel-gestao/`): lista os profissionais pendentes e aprova com um
     clique (`AprovarProfissionalGestaoView`).
3. **Acesso ao painel web** — após aprovado, o Profissional loga em `/entrar/` e é
   redirecionado para `/painel/` (rota `painel`), onde vê a lista de atividades que já cadastrou.
4. **Criação de atividades** — no próprio `/painel/`, o formulário cria uma nova `Atividade`
   vinculada automaticamente ao Profissional logado (nunca a partir do POST, por segurança).
5. **Alunos e evolução** — em `/painel/alunos/` vê os Alunos vinculados a ele; ao abrir um
   Aluno (`/painel/alunos/<id>/`) acessa o histórico de atividades concluídas e pode registrar
   uma observação qualitativa por atividade concluída (`SalvarObservacaoView`).

## 3. Fluxo do Aluno

1. **Cadastro** — em `/cadastro/`, escolhe o perfil "Aluno", seleciona o Profissional
   responsável (só aparecem os aprovados e ativos) e preenche data de nascimento e dados do
   responsável legal.
2. **Consentimento do responsável (obrigatório)** — a caixa "o responsável legal autorizou
   este cadastro..." é validada em `CadastroForm.clean()`: sem marcá-la, o cadastro é
   bloqueado. Ao salvar, o timestamp vai para `Aluno.consentimento_data` — é o registro formal
   de consentimento (LGPD, dado de menor de idade).
3. **Área exclusiva** — após login, o Aluno é redirecionado para `/aluno/atividades/` (rota
   `aluno_atividades`), protegida por `AlunoRequiredMixin`.
4. **Atividades pendentes** — a lista mostra apenas atividades do Profissional do Aluno que
   ainda não foram concluídas (um Profissional reprovado ou desativado some da lista
   automaticamente, ver `atividades_do_aluno()`).
5. **Execução com confirmação em duas etapas (UX inclusiva)** — clicar numa atividade não a
   conclui direto: abre `/aluno/atividades/<id>/confirmar/`, uma tela intermediária que só
   registra a conclusão depois de um segundo clique explícito
   (`POST /aluno/atividades/<id>/concluir/`). Isso evita que um toque acidental marque uma
   atividade como feita. Confirmar de novo uma atividade já concluída não duplica o registro
   (constraint `uma_conclusao_por_aluno_atividade`).

## 4. Acompanhamento de evolução

- O Profissional acessa o histórico de um Aluno em `/painel/alunos/<id>/` — restrito aos
  próprios Alunos (`EvolucaoAlunoView.get_queryset`), então o id de um Aluno de outro
  Profissional retorna 404.
- A tela lista cada `RegistroEvolucao` com status `concluida`, mais recente primeiro
  (`data_realizacao` decrescente).
- Cada registro tem um campo de observação qualitativa (`ObservacaoForm`), salvo via
  `POST /painel/alunos/<aluno_id>/registros/<id>/observacoes/` — é onde o Profissional
  documenta como o Aluno se saiu na atividade.
