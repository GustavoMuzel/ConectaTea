# Reconciliação: Monografia PFC × código ConectaTEA

Auditoria somente leitura, feita em 27/10/2026. Compara:
- **Documento:** `E:\Downloads_Archive\Monografia_PFC.docx`
- **Código:** `E:\Projetos\Estudos\Faculdade\ConectTea`, commit `a336652`

Nenhum arquivo do projeto foi alterado. O `git status` continua com só `README.md` e `docs/Fluxo.md` modificados, como já estava antes da auditoria.

---

## 1. Resumo executivo

O documento está **aderente ao código no essencial**. Tudo o que a monografia marca como Implementado existe e está coberto por testes. Tudo o que ela marca como Planejado ou «a implementar» está de fato ausente:
- as 26 classes «a implementar»;
- 10 das 15 tabelas;
- recuperação de senha, Jitsi e OpenAPI.

A alegação de **102 testes está confirmada**: 102 coletados, 102 passando, flake8 sem avisos, `check` limpo e nenhuma migração pendente.

As maiores divergências não estão no que falta. Estão em afirmações do texto que o código ou a infraestrutura contradizem:
1. **Política de Privacidade:** afirma que os dados "não são repassados a outras empresas", mas os e-mails do usuário e do responsável vão para o Brevo.
2. **RNF04:** usa "bloqueio após 5 tentativas" como critério, e não existe limite algum de tentativas de login, nem na web nem na API.
3. **CI:** §2.7 diz que o CI roda a cada push na ramificação principal. O workflow só dispara na `main`, que não existe mais no GitHub; a branch padrão é `Entrega28/09`. O último run é de 30/09.
4. **"Exclusão protegida":** RNF08 e §4.2 falam em exclusão protegida, mas `Atividade.profissional` usa `CASCADE`, e há um teste que garante esse comportamento.
5. **Quadros 1 e 3 se contradizem** no status de RF08, RF10 e RF14.
6. **BPMN:** as Figuras 19 e 20 são apresentadas como fluxos "já desenvolvidos", mas incluem etapas planejadas (refazer, registrar o acesso, anotação).
7. **Resumo e Abstract** descrevem no presente funcionalidades planejadas: distribuição, refazer, chat e videochamada.

---

## 2. Baseline e log de invocação

### Versões e checks
| Item | Valor real | Fonte |
|---|---|---|
| Python local | 3.14.4 (`.venv`) | `python --version` |
| Python no CI | 3.12 | `.github/workflows/ci.yml:20` |
| Django | 6.1.1 | `requirements.txt:7` e import |
| DRF / SimpleJWT | 3.18.1 / 5.5.1 | `requirements.txt:8-9` |
| drf-spectacular | 0.30.0, instalado e configurado, mas sem rota | `config/settings.py:47`, `:152` |
| pytest / pytest-django | 9.1.1 / 4.14.0 | `requirements.txt:27-28` |
| psycopg2 | 2.9.13, presente e sem uso | `requirements.txt:25` |
| HTMX / Celery / django-extensions | **não instalados** | `ModuleNotFoundError` |
| `manage.py check` | `System check identified no issues` | Fase 0 |
| `makemigrations --check --dry-run` | `No changes detected` | Fase 0 |
| `flake8` (`python -m flake8`) | 0 avisos, exit 0 | Fase 0 |
| `check --deploy` | 1 erro (`mail.E001`) e 5–6 avisos (W004, W008, W009, W012, W016, W018) | django-reviewer |
| `pytest --collect-only` | **102** | Fase 0 e django-test-runner |
| `pytest --create-db` | **102 passed**, 0 failed, 8 warnings, 171,7 s; ordem inversa também 102/102 | django-test-runner, saída bruta conferida |

**Ambiente usado:**
- Comandos rodados com as mesmas variáveis do CI (`SECRET_KEY=ci-dummy-key`, `DEBUG=True`, `BREVO_API_KEY=dummy-key`). O `.env` não foi lido, e a chave real do Brevo não foi usada.
- Os testes rodaram em banco de teste em memória, nunca no `db.sqlite3`.
- O `makemigrations --check` faz um SELECT de leitura na tabela `django_migrations` do banco de desenvolvimento para checar a consistência do histórico. Não grava nada.

### Extração do `.docx`
| Método | Resultado |
|---|---|
| a. `Read` no `.docx` | falhou: "cannot read binary files" |
| b. `pandoc` | não instalado |
| c. `python-docx` | não instalado; não instalei |
| **d. zip + `word/document.xml` com a stdlib** | **funcionou:** 804 parágrafos de texto |

As 22 figuras são PNG sem texto alternativo. Extraí as imagens do zip e conferi visualmente as Figuras 2–6, 9, 11–14, 16, 19 e 20. As Figuras 7, 8, 10, 15, 17, 18, 21 e 22 são inteiramente «a implementar»; para elas, verifiquei a ausência por grep dos nomes de classe.

### Skills e comandos
```
[skill: django-models] carregada — "Launching skill: django-models"
[skill: django-forms] carregada — "Launching skill: django-forms"
[skill: django-templates] carregada — "Launching skill: django-templates"
⚠️ htmx-patterns: não aplicável: projeto sem HTMX (sem pacote, sem hx-* nos templates)
⚠️ celery-patterns: não aplicável: projeto sem Celery
[skill: pytest-django-patterns] carregada — "Launching skill: pytest-django-patterns"
⚠️ django-extensions: não aplicável: pacote não instalado, show_urls indisponível; rotas mapeadas pelos urls.py
⚠️ systematic-debugging: não invocada: nenhuma divergência ficou sem explicação pela leitura do código
✅ ponytail ativo, nível full (hook SessionStart)
[/django-review] invocado — agente django-reviewer concluiu; 0 CRÍTICA, 2 ALTA, 6 MÉDIA, 6 BAIXA
[/django-test] invocado — agente django-test-runner concluiu; 102/102 passed
⚠️ /django-debug: não invocado: Fase 5 dispensada (nenhuma divergência inexplicada)
```

---

## 3. Matriz de reconciliação

**Legenda:**
- **C** = Confirmado
- **PC** = Parcial confirmado
- **D** = Divergente
- **A** = Ausente sem estar marcado como planejado
- **NV** = Não verificável

### 3.1 Requisitos funcionais (Quadro 1 e §3.1)

| ID | Alegação | Evidência no código | Status | Gap/ação |
|---|---|---|---|---|
| RF01 | Implementado: cadastro por perfil, consentimento com data e hora, e-mail ao responsável | `usuarios/views.py:34-52`, `forms.py:32-110`; consentimento em `forms.py:91-92` e `:107`; e-mails em `views.py:48-50` e `services/email.py:50-63` | **C** | RN01 `forms.py:72-76`; RN02 `forms.py:34`; RN03 `forms.py:48`; RN04 `models.py:66`; RN05 `email.py:17-37`. Todos os CA têm teste (§6). Ver também o risco R3 (e-mail case-insensitive só no formulário). |
| RF02 | Implementado: login web por sessão e API JWT | `EntrarView` `views.py:29-31`; rotas `config/urls.py:9-11`; logout por POST `base.html:25-28` | **C** | RN01 hash: `set_password` `models.py:10`. RN02 iexact `models.py:15`. RN03 inativo: ModelBackend e SimpleJWT. RN04 redirect seguro: `LoginView`. CA01–CA04 testados. |
| RF03 | Planejado | Não há `RecuperarSenhaView`, `CodigoVerificacao` nem rota de reset; `login.html:20-21` diz "Fale com o profissional" | **C** (ausente, como declarado) | — |
| RF04 | Implementado: perfil e vínculo, 403/404 | Mixins em `usuarios/mixins.py:4-25`; 404 por vínculo em `atividades/views.py:48-50`, `:64-66` e `acompanhamento/views.py:12-17`, `:51` | **C** | RN05: `atividades_do_aluno` filtra profissional aprovado e ativo. Ressalva: aluno desativado continua visível ao profissional (risco R4). |
| RF05 | Implementado: gestão, aprovação, soft delete | `AdminDashboardView` `views.py:79-93`; `AprovarProfissionalGestaoView` `:96-104`; `SoftDeleteAdminMixin` `admin.py:13-65`; registro de evolução não deletável em `acompanhamento/admin.py:11-12` | **C** | RN03 (não se autodesativar) `admin.py:20`, `:26`. Achado do reviewer: a action em massa de aprovação não exige permissão (R1). |
| RF06 | Parcial: criar sim; editar e arquivar não | Criação em `atividades/views.py:13-28`; dono vem da sessão (`:26`); lista própria (`:21`). Não há update, archive, `arquivada` nem `PassoAtividade` | **PC** | Falta exatamente o que o documento diz: editar, arquivar e passos. CA04 sem implementação. |
| RF07 | Planejado | Não há `Atribuicao` nem `DistribuirAtividadeView` | **C** (ausente) | — |
| RF08 | Parcial | Lista `acompanhamento/views.py:20-31`; confirmação em duas etapas `:34-42` + `confirmar_conclusao.html`; POST com CSRF e `get_or_create` `:45-59`; `UniqueConstraint` parcial `models.py:25-31` | **PC** | Falta o que depende de `Atribuicao`: o aluno vê todas as atividades do profissional, não as "atribuídas", e não há prazo. Coerente com §4.3. CA01 só vale no modelo atual. |
| RF09 | Planejado | Não há refazer nem histórico do aluno; a constraint `uma_conclusao_por_aluno_atividade` impede uma 2ª conclusão | **C** (ausente) | — |
| RF10 | Parcial | `AlunosDoProfissionalView` `atividades/views.py:31-38`; `EvolucaoAlunoView` `:41-57`, ordenada por `-data_realizacao`; `SalvarObservacaoView` `:60-74`, só para concluídas | **PC** | Falta RN03 (`LogAcesso`). Problema de terminologia: a interface chama a observação de "Anotações" e "Salvar anotação" (`atividades/forms.py:21`, `views.py:71`, `evolucao_aluno.html:13`), quando §4.5 diz que anotação é o RF11, planejado. |
| RF11 | Planejado | Não há `Anotacao` | **C** (ausente) | Ver o rótulo "Anotações" no RF10. |
| RF12 | Planejado | Não há `Conversa`, `Mensagem` nem polling JS | **C** (ausente) | — |
| RF13 | Planejado | Não há `SalaVideo` nem referência ao Jitsi | **C** (ausente) | — |
| RF14 | Planejado | Não há `PreferenciaAcessibilidade` nem `PreferenciasView` | **C** (ausente) | O Quadro 3 chama o mesmo módulo de "Parcial" (ver §5). |

### 3.2 Requisitos não funcionais (Quadro 2)

| ID | Critério de verificação | Evidência | Status | Gap/ação |
|---|---|---|---|---|
| RNF01 | No máximo 3 passos, medido em teste de usabilidade | O fluxo atual tem 3 passos: lista → "Concluir" → "Sim, terminei" | **NV** | O fluxo bate, mas o critério exige um teste de usabilidade que não existe. |
| RNF02 | WCAG AA (4,5:1) e nenhuma animação | `conectatea.css:13-17` zera `animation`/`transition`; foco visível `:38-42`; altura mínima `:35`. Contraste calculado: primário `#2f5d7c` sobre `#f7f7f4` ≈ 6,6:1; branco sobre o botão ≈ 7:1; erro `#8a1c1c` sobre branco ≈ 9:1 | **C** (parte estática) | Sem checklist WCAG formal nem axe. Revisão por leitura e cálculo. |
| RNF03 | No máximo 2 s em rede doméstica | — | **NV** | Não há medição de desempenho. |
| RNF04 | Testes de CSRF, acesso indevido e redirect externo; **bloqueio após 5 tentativas** | Hash, CSRF e redirect seguro OK. JWT com expiração pelos defaults do SimpleJWT, pois não há `SIMPLE_JWT` no `settings.py`. **Não há throttle, lockout nem `axes`**: o reviewer fez 30 POSTs errados e recebeu 401 em todos, nunca 429. Só há **um** teste de CSRF real (`test_aluno.py::test_concluir_exige_csrf`) | **D** | O critério "bloqueio após 5 tentativas" não está implementado, e o Quadro 2 não marca isso como planejado. Só a §4.8 diz "previstos". |
| RNF05 | Consentimento com data; consultas registradas; Termos e Privacidade atualizados | Consentimento com data OK (`forms.py:107`); soft delete OK; isolamento por vínculo OK. Não há `LogAcesso`. `privacidade.html` item 4 diz "não são repassados a outras empresas", mas `email.py:24` e `:63` enviam o e-mail do usuário e do responsável ao Brevo | **D** | Duas lacunas: o log de acesso (declarado como planejado só no Quadro 3) e o texto da Política, que contradiz o código. |
| RNF06 | Testes manuais em 3 navegadores e em 360 px | Meta viewport `base.html:5`; grid do Bootstrap; nenhum `@media` próprio | **NV** | Depende de teste manual. |
| RNF07 | flake8 sem avisos, pytest sem falhas, migrações no CI | `.flake8`, `ci.yml:25-35`; localmente flake8 0, pytest 102/102, sem migração pendente | **PC** | Os passos de qualidade existem e passam localmente. Mas o CI **não dispara** hoje: `on: push: [main]`, e o remoto só tem `Entrega28/09`, sem nenhum run nela. |
| RNF08 | SQLite em dev, PostgreSQL em produção; backup; FKs com exclusão protegida | Só SQLite (`settings.py:89-95`, com o comentário "voltar ao PostgreSQL"). PROTECT em `Aluno.profissional`, `RegistroEvolucao.aluno` e `.atividade`. **CASCADE** em `Atividade.profissional` (`atividades/models.py:8`), `Profissional.user` e `Aluno.user` | **D** (parcial) | "FKs com exclusão protegida" não vale para todas. O teste `atividades/tests.py::test_atividade_pertence_ao_profissional_e_cascateia` garante o CASCADE. Backup e PostgreSQL: NV e planejado. |
| RNF09 | Interface em pt-BR | `LANGUAGE_CODE='pt-br'` (`settings.py:125`); `lang="pt-br"` (`base.html:2`) | **C** | — |
| RNF10 | Falha simulada; timeout de 3 s e 5 s | `timeout=(3, 5)` (`email.py:30`); nunca levanta exceção; `on_commit(robust=True)`; 6 testes | **C** | Ressalva do reviewer (R5): o `on_commit` roda síncrono, dentro da requisição, com até cerca de 16 s se o Brevo estiver lento. Não interrompe o cadastro, mas atrasa. |
| RNF11 | Mensagem em até 10 s | Chat inexistente | **C** (planejado, ausente) | O Quadro 2 não marca a situação. |
| RNF12 | OpenAPI em rota própria | `drf_spectacular` instalado e `DEFAULT_SCHEMA_CLASS` configurado, mas sem `SpectacularAPIView` nas URLs | **PC** | Falta só a rota. O documento não menciona que a dependência já está lá. |

### 3.3 Modelo de dados (§2.9, Figuras 2–4)

| Tabela | Doc | Código | Status | Campos / observação |
|---|---|---|---|---|
| users | implementada | `usuarios/models.py:22-58` | **C** | Todos os campos da Fig. 2 existem. `is_active` é gravado na coluna `active` (`db_column`, `:34`), enquanto a figura diz `is_active`. `PermissionsMixin` cria ainda `users_groups` e `users_user_permissions`, que a figura não mostra. |
| profissionais | implementada | `models.py:61-74` | **C** | Bate campo a campo. |
| alunos | implementada | `models.py:77-95` | **C** | Bate campo a campo. FK `profissional` com PROTECT. |
| atividades | implementada | `atividades/models.py:6-20` | **PC** | Faltam `arquivada` e `updated_at`, ambos com `*` na Fig. 6. A Fig. 3 não marca esses campos como pendentes. |
| registros_evolucao | implementada | `acompanhamento/models.py:8-34` | **PC** | Segue o modelo antigo: `aluno_id` e `atividade_id`, sem `atribuicao_id`, `tentativa` e `iniciado_em`. A Fig. 3 mostra o modelo novo sem marcação; a §3.3.1 e a §4.3 explicam a diferença. |
| passos_atividade, atribuicoes | planejadas | ausentes | **C** | — |
| codigos_verificacao, preferencias_acessibilidade, logs_acesso | planejadas | ausentes | **C** | — |
| anotacoes, conversas, mensagens, salas_video, participacoes_sala | planejadas | ausentes | **C** | — |

**Contagem:** existem 5 models próprios contra as 15 tabelas da monografia. Os 5 que existem são exatamente os que a §2.9 declara implementados.

### 3.4 Classes (Figuras 5–15)

**Implementadas: todas existem com o mesmo nome e os mesmos métodos.**
- Domínio: `User`, `Profissional` e `Aluno`, com `is_profissional` e `is_aluno` (`usuarios/models.py:51-58`); `Atividade`; `RegistroEvolucao`.
- Views de acesso e cadastro: `EntrarView` (a monografia diz que estende `LoginView`), `CadastroView`, `HomeView`, `TermosView`, `PrivacidadeView`.
- Gestão: `AdminDashboardView`, `AprovarProfissionalGestaoView`.
- API: `UserMeView`, `UserSerializer`, `UserMeSerializer`.
- Área do aluno: `AtividadesAlunoView`, `ConfirmarConclusaoView`, `ConcluirAtividadeView`.
- Área do profissional: `PainelView`, `AlunosDoProfissionalView`, `EvolucaoAlunoView`, `SalvarObservacaoView`.
- Formulários: `LoginForm`, `CadastroForm`, `AtividadeForm`, `ObservacaoForm`, `BootstrapMixin`.
- Mixins: os três de perfil.

| Classe | Status | Observação |
|---|---|---|
| `EmailService` (Fig. 9) | **D** (baixa) | Não existe como classe. É o módulo `apps/usuarios/services/email.py`, com as três funções da figura. |
| Enum `StatusRegistro` (Fig. 6) | **C** | No código chama-se `RegistroEvolucao.Status`, com os mesmos 3 valores. |
| Seta "lista → Atribuicao" de `AtividadesAlunoView` (Fig. 12) | **PC** | Hoje a view lista `Atividade`. A seta representa o estado futuro. |
| As 26 classes «a implementar» (Figs. 6–15) | **C** (ausentes) | Grep sem nenhuma ocorrência: `Atribuicao`, `PassoAtividade`, `Anotacao`, `Conversa`, `Mensagem`, `SalaVideo`, `ParticipacaoSala`, `CodigoVerificacao`, `PreferenciaAcessibilidade`, `LogAcesso`, `RecuperarSenhaView`, `RedefinirSenhaView`, `PreferenciasView`, `RefazerAtividadeView`, `HistoricoAlunoView`, `AnotacaoAlunoCreateView`, `AtividadeUpdateView`, `ArquivarAtividadeView`, `DistribuirAtividadeView`, `AnotacaoProfissionalCreateView`, `ConversaView`, `MensagensRecentesView`, `EnviarMensagemView`, `SalaVideoView`, `VideoService`, `ParParticipanteMixin`. |

### 3.5 BPMN (Figuras 16–22, §3.4)

| Figura | Doc | Código | Status |
|---|---|---|---|
| 16 Cadastro e aprovação | desenvolvido | `CadastroView` + `CadastroForm` + painel de gestão e admin | **C** |
| 17 Recuperação de senha | previsto | ausente | **C** |
| 18 Distribuição | previsto | ausente | **C** |
| 19 Realização e repetição | "desenvolvido" (§3.4) | O login, a lista e a confirmação em 2 etapas existem. O laço "Refazer? Sim" **não existe**, e a lista não é de atividades "atribuídas" | **D** (parcial) |
| 20 Acompanhamento | "desenvolvido" | O perfil, o vínculo, o histórico e a observação existem. "Registrar o acesso" (`LogAcesso`) e a "anotação" **não existem** | **D** (parcial) |
| 21 Chat | previsto | ausente | **C** |
| 22 Videochamada | previsto | ausente | **C** |

### 3.6 Quadro 3 (módulos)

| Módulo | Situação no doc | Verificado | Evidência / gap |
|---|---|---|---|
| Cadastro com consentimento | Implementado | **C** | Ver RF01. |
| Aprovação e painel de gestão | Implementado | **C** | Indicadores em `views.py:88-92`; ação em massa em `admin.py:95-98` (mas sem permissão, R1); exclusão só desativa. |
| Autenticação web e JWT | Implementado | **C** | `config/urls.py:9-11`. |
| Área do aluno | Implementado | **C** no módulo, mas o Quadro 1 diz RF08 **Parcial** | Ver §5. |
| Painel do profissional | Implementado | **C** no módulo, mas o Quadro 1 diz RF06 e RF10 **Parciais** | O isolamento com 404 está confirmado. |
| E-mail Brevo | Implementado | **C** | `email.py:17-37`. |
| Testes e CI | Implementado: "102 testes, análise estática e migrações" | **PC** | Localmente, 102/102 e lint limpo. O CI está parado: o gatilho é a `main`, que não existe no remoto. |
| Preferências e front-end ampliado | Parcial | **PC** | O CSS existe; preferências não. O Quadro 1 diz RF14 **Planejado**. |
| Recuperação de senha | Planejado | **C** | — |
| Distribuição, tentativas e histórico | Planejado | **C** | — |
| Edição e arquivamento; passos | Planejado: "hoje só é possível criar" | **C** | `atividades/urls.py` só tem o painel de criação. |
| Anotações | Planejado | **C** | Ver o rótulo "Anotações" no RF10. |
| Chat | Planejado | **C** | — |
| Videochamada | Planejado | **C** | — |
| PostgreSQL e auditoria de acessos | Planejado: "driver já consta" | **C** | `requirements.txt:25`. O driver está lá, mas sem uso. |

### 3.7 Arquitetura, API e testes (§2.2–2.9, §5)

| Alegação | Evidência | Status |
|---|---|---|
| Monolito Django; DRF + SimpleJWT | `INSTALLED_APPS` em `settings.py:38-51`; `REST_FRAMEWORK` `:151-159` | **C** |
| Bootstrap 5 via CDN; JS puro só no cadastro | `base.html:7` (com SRI); `cadastro.html:37-55` | **C** |
| "sem frameworks JavaScript" | Não há HTMX nem nenhum framework | **C** |
| Rotas `/api/auth/login/`, `/refresh/` e `/me/`, com perfil aninhado | `config/urls.py:9-11`; `serializers.py:31-38` | **C** |
| SQLite em dev; migração para PostgreSQL na homologação | `settings.py:89-95` | **C** (planejado) |
| Vídeo externo (Jitsi) | ausente | **C** (planejado) |
| "102 testes automatizados" | 102 coletados e 102 passaram | **C** |
| CI com Flake8, check, migrações e pytest "a cada alteração na ramificação principal" | Os passos existem em `ci.yml:25-35`, mas o gatilho é só a `main` (`ci.yml:3-7`). O remoto não tem `main`: a branch padrão é `Entrega28/09`, sem nenhum run. O último run com sucesso é de 2026-09-30 | **D** |
| Testes de segurança: CSRF, isolamento, redirect externo, escalada | Isolamento: 9 testes. Redirect: 1. Escalada: 6. **CSRF: só 1 teste real** | **C**, com a ressalva do CSRF |

---

## 4. Divergências priorizadas

A decisão de cada item é sua. "Doc" significa corrigir a monografia; "Código" significa implementar ou corrigir o código.

### Alta

**D1. Política de Privacidade × Brevo**
- **O documento diz:** RNF05 (Quadro 2) e §4.8 exigem informar os serviços de terceiros que recebem dados. Na §4.8, isso aparece como "deverá ainda informar".
- **O código tem:** `templates/usuarios/privacidade.html` item 4 diz "Esses dados não são repassados a outras empresas". Mas `services/email.py:24` e `:63` enviam o e-mail do usuário e o `guardian_email` ao Brevo.
- **Recomendação:** corrigir o texto da Política (código), declarando o Brevo. Ou, no mínimo, registrar na monografia que a Política ainda não cita terceiros. É LGPD com dados de menores.

**D2. Limite de tentativas de login (RNF04)**
- **O documento diz:** o critério do Quadro 2 é "bloqueio após 5 tentativas inválidas seguidas", sem marcar como planejado. A §4.8 diz "Também estão previstos limites".
- **O código tem:** nenhum throttle no DRF, nada no `EntrarView`, nenhum `axes`. Confirmado por sonda: 30 POSTs errados, 401 em todos.
- **Recomendação:** marcar RNF04 como parcial no Quadro 2 (doc), ou implementar o throttle (código).

**D3. CI parado**
- **O documento diz:** §2.7 e Quadro 3 afirmam que o CI roda a cada alteração enviada à ramificação principal.
- **O código e a infraestrutura têm:** `ci.yml:3-7` dispara só em `main`. O remoto tem só `Entrega28/09`, a default, sem runs. A `main` local aparece como `[gone]`.
- **Recomendação:** incluir `Entrega28/09` no gatilho, ou recriar a `main`. Ou ajustar a frase no documento.

### Média

**D4. FKs "com exclusão protegida" (RNF08, §4.2)**
- **O documento diz:** que as chaves estrangeiras usam exclusão protegida.
- **O código tem:** `Atividade.profissional` com CASCADE (`atividades/models.py:8`, e o teste que garante isso); `Profissional.user` e `Aluno.user` também com CASCADE.
- **Na prática:** o PROTECT de `RegistroEvolucao` e de `Aluno.profissional` bloqueia a cascata quando já existe histórico, e o admin só faz soft delete.
- **Recomendação:** ajustar a frase para "FKs do histórico" (doc), ou trocar para PROTECT (código).

**D5. Quadro 1 × Quadro 3**
- **O documento diz:**
  - RF08 aparece como Parcial no Quadro 1 e como "Área do aluno: Implementado" no Quadro 3.
  - RF06 e RF10 aparecem como Parciais no Quadro 1 e como "Painel do profissional: Implementado" no Quadro 3.
  - RF14 aparece como Planejado no Quadro 1 e como "Preferências... Parcial" no Quadro 3.
- **Recomendação:** harmonizar os dois quadros (doc).

**D6. BPMN 19 e 20 rotulados como "já desenvolvidos" (§3.4)**
- **O documento diz:** que os fluxos das Figuras 19 e 20 estão desenvolvidos.
- **O código tem:** não há "Refazer", "registrar o acesso" nem "anotação".
- **Recomendação:** descrever esses dois fluxos como parcialmente desenvolvidos (doc).

**D7. Observação × Anotação na interface (§4.5)**
- **O documento diz:** que a observação (RF10) está implementada e a anotação (RF11) é planejada.
- **O código tem:** a interface usa "Anotações", "Salvar anotação" e "Anotação salva." para a observação (`atividades/forms.py:21`, `views.py:71-73`, `evolucao_aluno.html:13`).
- **Recomendação:** trocar os rótulos para "Observação" (código), para não confundir quem avaliar o sistema.

**D8. Tempo verbal do Resumo, Abstract e §2.8**
- **O documento diz:**
  - "permite que profissionais... distribuam... refazê-las"
  - "Todas as tentativas são registradas"
  - "também contempla... chat e videochamadas"
  - §2.8: "rotina de backups garante"
  - §2.6: e-mail de "códigos de verificação"
- **O código tem:** nada disso existe ainda.
- **Recomendação:** passar para o futuro ou para "prevê" (doc).

**D9. Sem log de acesso a dados de alunos**
- **O documento diz:** RF10 RN03 e RNF05 exigem registrar cada consulta ao histórico de um aluno. A pendência só aparece no Quadro 3, como "auditoria de acessos: Planejado".
- **O código tem:** nenhum `LogAcesso`.
- **Recomendação:** citar a pendência no próprio RF10 e no RNF05 (doc).

### Baixa

**D10. Coluna `active` × `is_active`**
- **O documento diz:** a Figura 2 nomeia a coluna `users.is_active`.
- **O código tem:** a coluna é `active` (`models.py:34`).
- **Recomendação:** ajustar a figura (doc).

**D11. `EmailService` não é uma classe**
- **O documento diz:** a Figura 9 mostra uma classe `EmailService`.
- **O código tem:** um módulo de funções.
- **Recomendação:** anotar na figura que se trata de um módulo de serviço (doc).

**D12. RNF12 e drf-spectacular**
- **O documento diz:** RNF12 está Planejado, sem mencionar que a dependência já existe.
- **O código tem:** drf-spectacular instalado e configurado; falta só a rota.
- **Recomendação:** registrar isso (doc), ou expor a rota (código).

**D13. Versão do Python e driver sem uso**
- **O documento diz:** "Python 3", sem versão.
- **O código tem:** CI em 3.12 e ambiente local em 3.14. O `psycopg2` é compilado a partir do código-fonte e não é usado.
- **Recomendação:** fixar a versão em um só lugar (código ou doc).

---

## 5. Inconsistências internas do documento

**Sumário desatualizado:**
- Lista 2.3 "Banco de Dados", 2.4 "Git", 2.5 "Arquitetura", 2.6 "Modelagem", 3 "Estágio atual", 4 "Considerações" e um "Apêndice A".
- O corpo tem: 2.1 a 2.9, 3 Análise, 4 Funcionalidades, 5 Estágio, 6 Considerações. Não há Apêndice A.
- Todas as páginas aparecem como "1", então o sumário não foi atualizado.

**Numeração e estrutura:**
- **2.4 duplicada:** "2.4 Banco de Dados: PostgreSQL" e "2.4 Controle de Versão".
- **Títulos 2.2 e 2.3 fundidos ao primeiro parágrafo:** "2.2 Framework DjangoAs páginas…" e "2.3 API REST e Autenticação JWTAlém das telas…". Além disso, a 2.2 nunca apresenta o Django em si.
- **Falta a 3.4.4:** a numeração pula de 3.4.3 para 3.4.5, e a Figura 19 fica sem subseção descritiva.
- **§1.3:** fala em um "Capítulo 7 – referências", mas as Referências não são numeradas no corpo.
- **Quadro 2:** não tem coluna de Situação, embora RNF04 (parte), RNF05 (log), RNF11 e RNF12 sejam planejados.
- **Figuras sem "Fonte":** as Figuras 4 e 5–22 não têm a linha de fonte. Na Figura 2, a fonte não fecha o parêntese: "Fonte: … (2026".
- **Lista de Figuras:** a Lista marca "(a implementar)" nas Figuras 7, 8, 10 e 15, mas as legendas no corpo não trazem essa marcação.

**Erros de digitação e concordância:**
- "apoio à ao desenvolvimento" (título)
- "adolescentes autista" (título e §1.1.1)
- "DESCISÕES DE PROJETOS"
- "notações" em vez de "anotações" (§1.1.2)
- "teste autorizados" em vez de "testes automatizados" (§1.1.2)
- "diferencial do projeto está simplicidade" (§1.2)
- "estereótipo a implementarem" (§3)
- "Figura 5 apresenta" (falta o artigo)
- "1 para 0.1" e "1 para 0." (deveriam ser 0..1 e 0..*)
- "A classe conversa" (minúscula)
- "o sistema a válida"
- "o destinatário a ver"
- "Privados ou compartilhadas" (Quadro 3)
- "usuário/ou"

---

## 6. Cobertura de testes por requisito

Fonte: o mapa do django-test-runner, com os critérios de aceite conferidos por grep.

| Requisito | CA01 | CA02 | CA03 | CA04 |
|---|---|---|---|---|
| RF01 | ✅ `test_web.py::test_cadastro_aluno_cria_perfil_vinculado` (consentimento: `test_web.py:74`) | ✅ `test_cadastro_aluno_sem_consentimento_mostra_erro_e_nao_cria`, `test_cadastro_invalido_nao_cria_nada[...consentimento]` | ✅ `test_cadastro_rejeita_email_repetido_sem_diferenciar_maiusculas` | ✅ `test_cadastro_profissional_cria_perfil_loga_e_envia_boas_vindas` (painel 403) |
| RF02 | ✅ `test_login_e_logout_por_sessao` | ✅ `test_login_invalido_e_usuario_inativo`, `test_auth::test_login_com_senha_errada_retorna_401` | ✅ idem + `test_login_de_usuario_inativo_retorna_401` | ✅ `test_auth::test_login_retorna_tokens_e_refresh_funciona` |
| RF04 | ✅ 4 testes de redirect | ✅ `test_painel_bloqueia_aluno_...` | ✅ `test_evolucao_de_aluno_de_outro_profissional_da_404` | ✅ `test_painel_bloqueia_..._nao_aprovado` |
| RF05 | ✅ `test_aprovar_profissional_via_post`, `test_aprovar_profissionais_em_massa` | ✅ `test_aluno_e_profissional_comum_recebem_403` | ✅ `test_excluir_um_registro_so_inativa[3]` | ✅ `test_admin_nao_desativa_a_si_mesmo` |
| RF06 | ✅ `test_cadastrar_atividade_usa_o_profissional_da_sessao` | ✅ `test_cadastrar_atividade_invalida_mostra_erros` | ✅ `test_painel_lista_so_atividades_do_profissional` | ⛔ não implementado |
| RF08 | ✅ `test_lista_so_atividades_do_proprio_profissional_com_botao` (no modelo atual) | ✅ `test_tela_de_confirmacao_mostra_o_nome_e_nao_conclui_sozinha` | ✅ `test_concluir_registra_evolucao_e_some_da_lista` (mensagem: `test_aluno.py:111`) | ✅ `test_concluir_duas_vezes_nao_duplica`, `test_banco_barra_segunda_conclusao` |
| RF10 | ✅ `test_lista_mostra_so_os_alunos_do_proprio_profissional` | ✅ `test_evolucao_lista_concluidas_da_mais_recente_para_a_mais_antiga` | ✅ `test_salvar_observacao_atualiza_o_registro` | ✅ `test_evolucao_de_aluno_de_outro_profissional_da_404` |
| RF03, RF07, RF09, RF11–14 | ⛔ não implementados, sem teste (coerente) | | | |

**RNFs:**
- **RNF10:** coberto por 6 testes (`test_email.py` ×5 e `test_falha_inesperada_no_email_nao_quebra_cadastro`).
- **RNF04:**
  - CSRF real: 1 teste.
  - Redirect: 1 teste.
  - Acesso indevido: muitos testes.
  - Lockout: **nenhum**, porque não está implementado.
- **RNF02:** nenhum teste automatizado verifica a ausência de animação; a garantia existe só no CSS.

**Sem teste no que está implementado:**
- CSRF nos demais POSTs: cadastro, login, aprovar, observação, criar atividade.
- A regra RF10 RN02 ("só em concluídas") é coberta só de forma indireta, por `..._incompativeis_da_404`.
- Nenhum teste cobre a permissão da action em massa de aprovação (R1).

---

## 7. Riscos não documentados (django-reviewer)

A monografia não menciona nenhum destes riscos.

| # | Sev. | Risco | Onde |
|---|---|---|---|
| R1 | ALTA | A action em massa `aprovar_profissionais` não exige permissão. Um staff só com leitura aprova profissionais (confirmado por sonda), e um profissional aprovado passa a receber alunos menores | `usuarios/admin.py:95-98` |
| R2 | ALTA | Não há limite de tentativas no login web nem na API (é o D2) | `config/urls.py:9`, `views.py:29-31` |
| R3 | MÉDIA | `unique` do e-mail diferencia maiúsculas no banco. O formulário de criação do admin permite `Ana@` ao lado de `ana@`, e o login dos dois passa a dar 500 (`MultipleObjectsReturned`) | `usuarios/models.py:15`, `:32` |
| R4 | MÉDIA | Um aluno desativado (soft delete) continua visível e editável para o profissional | `atividades/views.py:38`, `:50`, `:64` |
| R5 | MÉDIA | O `on_commit` roda síncrono depois do `save()` atômico. Os dois POSTs ao Brevo seguram a resposta do cadastro (até cerca de 16 s) | `usuarios/views.py:48-50` |
| R6 | MÉDIA | O cadastro público vira canal de e-mail: dispara mensagens para `guardian_email` arbitrário, sem limite. O vínculo aluno–profissional é autodeclarado, sem aceite do profissional | `usuarios/forms.py:46-57` |
| R7 | MÉDIA | `check --deploy` falha: faltam as flags `SECURE_*` (cookies seguros, HSTS, redirect para SSL), e há o erro `mail.E001` | `config/settings.py` |
| R8 | MÉDIA | `UserSerializer` latente: `role` gravável e sem `validate_password`, um risco se for ligado a um endpoint | `usuarios/serializers.py:6-16` |
| R9–R14 | BAIXA | N+1 no `list_filter` do admin; `LogEntry` de desativação registra até quem foi poupado; aprovação sem trilha de auditoria; mensagens de erro com `role="status"`; link de gestão visível para staff sem permissão; CI sem `permissions:` | ver o relatório do reviewer |

**Achados dos agentes:**
- **Do test-runner:** o JWT assina com a `SECRET_KEY`. Em produção ela precisa ter 32 bytes ou mais; o PyJWT avisa sobre chaves curtas.
- **Do test-runner:** a suíte leva cerca de 3 min porque não há `PASSWORD_HASHERS` rápido nos testes.
- **Do reviewer:** a Política (item 5) promete que os dados podem ser apagados, mas o sistema só faz soft delete.

---

## 8. Pendências para você

1. **Política de Privacidade × Brevo (D1):** corrigir o template ou registrar a pendência no documento? É o item com maior risco de questionamento na banca, por envolver LGPD e dados de menores.
2. **RNF04 (D2/R2):** implementar o throttle e o bloqueio, ou rebaixar o critério no Quadro 2 para "previsto"?
3. **CI (D3):** ajustar o gatilho para a branch real (`Entrega28/09`) ou recriar a `main`? Hoje a afirmação "a cada alteração" não é verdadeira.
4. **R1 (aprovação sem permissão):** é uma correção de uma linha (`permissions=['change']`). Decidir se entra antes da entrega.
5. **Rótulo "Anotações" na tela de observação (D7):** renomear para alinhar com a §4.5?
6. **Harmonizar Quadros 1 e 3, BPMN 19 e 20, e o tempo verbal do Resumo e Abstract (D5, D6, D8):** só revisão de texto.
7. **"Exclusão protegida" (D4):** ajustar a frase ou trocar o CASCADE de `Atividade.profissional`?
8. **Revisão editorial (§5):** regenerar o Sumário e corrigir a numeração e os erros de digitação.
9. **Estado do repositório:** a `main` local rastreia um `origin/main` que não existe mais, e há `README.md` e `docs/Fluxo.md` modificados sem commit. Não mexi em nada.

---

### Como validar à mão

```bash
SECRET_KEY=ci-dummy-key DEBUG=True BREVO_API_KEY=dummy-key .venv/Scripts/python.exe manage.py check
SECRET_KEY=ci-dummy-key DEBUG=True BREVO_API_KEY=dummy-key .venv/Scripts/python.exe manage.py makemigrations --check --dry-run
SECRET_KEY=ci-dummy-key DEBUG=True BREVO_API_KEY=dummy-key .venv/Scripts/python.exe -m pytest --create-db -q -p no:cacheprovider
```
