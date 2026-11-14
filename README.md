# ConectaTEA

O ConectaTEA é um aplicativo web que ajuda adolescentes autistas a desenvolver habilidades sociais e de comunicação. Profissionais de saúde e educação cadastram as atividades e acompanham o progresso de cada aluno.

Todo o projeto segue a ideia de **baixa carga sensorial**. Por isso o texto é grande, as cores são calmas e não há animações nem transições. O foco do teclado fica sempre visível, e as ações importantes pedem confirmação explícita, o que evita toques por engano.

As funcionalidades entregues estão detalhadas em [docs/funcionalidades.md](docs/funcionalidades.md).

## Stack Tecnológica

- **Python** + **Django**, com views baseadas em classe e autenticação por sessão
- **Banco de Dados:** PostgreSQL 16 (banco oficial de desenvolvimento e testes, configurado via variáveis de ambiente no `.env`). O sistema também possui fallback para SQLite caso o PostgreSQL não esteja disponível no ambiente local.
- **Bootstrap 5** carregado por CDN, mais um CSS próprio e pequeno (`static/css/conectatea.css`) para controlar os estímulos visuais em detalhe. Não usamos framework de JavaScript: onde é preciso, o JS é puro
- **Django REST Framework** + **SimpleJWT** na API (`/api/auth/...`)
- **Brevo** (API REST) para os e-mails transacionais

## Arquitetura do Sistema

O ConectaTEA foi desenvolvido utilizando uma arquitetura **Monolítica** com o framework **Django** (Python). A escolha do monolito se deu pela simplicidade de implantação, coesão do domínio e agilidade no desenvolvimento, características ideais para o escopo do projeto.

A aplicação é dividida internamente em "Apps" do Django para separação de responsabilidades:

- `apps/usuarios`: Autenticação, perfis de acesso (Aluno, Profissional, Gestor) e preferências de acessibilidade.
- `apps/atividades`: Biblioteca de atividades, edição, arquivamento e distribuição.
- `apps/acompanhamento`: Registros de evolução, tentativas, anotações e dashboards com gráficos.

**Integrações:**

- **Banco de Dados:** PostgreSQL 16 (banco oficial, configurado via `.env`) com fallback para SQLite.
- **API:** Django REST Framework (DRF) para rotas de API assíncronas e autenticação JWT.
- **Serviços Externos:** Integração com a API do Brevo para envio de e-mails transacionais.

**Interface (Front-end):**

O front-end é renderizado no servidor (SSR) utilizando os templates nativos do Django, estilizados com Bootstrap 5 e Chart.js (para os gráficos do dashboard). O sistema adota o princípio de "baixa carga sensorial", com regras de CSS próprias para acessibilidade.

## Pré-requisitos

- Python 3.13+
- Git

## Instalação

1. Clone o repositório:

   ```bash
   git clone <url-do-repositorio>
   cd ConectTea
   ```

2. Crie o ambiente virtual e ative-o:

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

   Se preferir o [uv](https://docs.astral.sh/uv/):

   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente. Copie o arquivo de modelo e preencha os valores:

   ```bash
   cp .env.example .env
   ```

   O `.env` usa estas variáveis:

   | Variável | Descrição |
   |---|---|
   | `SECRET_KEY` | Chave secreta do Django. Para gerar uma, rode `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
   | `DEBUG` | `True` no desenvolvimento e `False` em produção |
   | `ALLOWED_HOSTS` | Hosts permitidos, separados por vírgula |
   | `BREVO_API_KEY` | Chave da API do Brevo, usada nos e-mails transacionais. Quando fica vazia, o sistema não envia nada e só anota o fato no log; o cadastro continua funcionando normalmente |
   | `BREVO_SENDER_EMAIL` | Endereço do remetente, configurado no Brevo |
   | `BREVO_SENDER_NAME` | Nome do remetente que aparece nos e-mails |

5. Rode as migrações:

   ```bash
   python manage.py migrate
   ```

6. (Opcional) Para entrar no `/admin/` e no `/painel-gestao/`, crie um superusuário:

   ```bash
   python manage.py createsuperuser
   ```

7. Suba o servidor de desenvolvimento:

   ```bash
   python manage.py runserver
   ```

   Depois disso, a aplicação responde em `http://localhost:8000/`.

## Testes

Os testes ficam separados em dois grupos, pelos marcadores do pytest registrados no `pytest.ini`:

```bash
pytest -m unit          # testes unitários: regras de negócio, sem banco e sem rede (segundos)
pytest -m integration   # testes de integração: views, API, services e banco de teste
pytest                  # os dois grupos
```

- **Unitários** (`apps/*/test_unitario.py`, marcados com `pytestmark = pytest.mark.unit`): usam objetos em memória,
  sem `.save()`, e simulam a API do Brevo. O pytest-django recusa qualquer acesso ao banco, e o `conftest.py`
  recusa qualquer conexão de rede.
- **Integração** (os demais arquivos de teste, marcados com `pytestmark = pytest.mark.integration`): passam pelas
  URLs, views, formulários e banco. O pytest-django cria um banco de teste separado e o apaga no fim.
- O `conftest.py` também confere a separação: teste sem marcador, com os dois marcadores, ou unitário que pede o
  banco, interrompe a execução com erro.

## Qualidade de código

```bash
flake8
```

As regras ficam no `.flake8`: pycodestyle (estilo), pyflakes (import ou variável sem uso, nome indefinido) e
mccabe (complexidade máxima 10).

## Integração Contínua (CI)

A cada Pull Request para a `main`, e depois do merge, o GitHub Actions (`.github/workflows/ci.yml`) roda três
checagens em paralelo, cada uma em um ambiente limpo (`ubuntu-latest`, Python 3.13):

| Check | Comando | O que valida |
|---|---|---|
| **Testes unitários** | `pytest -m unit` | Regras de negócio, sem banco e sem rede |
| **Testes de integração** | `manage.py check`, `makemigrations --check` e `pytest -m integration` | Views, API, services e banco, num PostgreSQL 16 criado só para o job |
| **Linter** | `flake8` | Estilo e erros estáticos, com as regras do `.flake8` |

Se qualquer checagem falhar, o PR mostra um X vermelho antes da revisão.
