# ConectaTEA

O ConectaTEA é um aplicativo web que ajuda adolescentes autistas a desenvolver habilidades sociais e de comunicação. Profissionais de saúde e educação cadastram as atividades e acompanham o progresso de cada aluno.

Todo o projeto segue a ideia de **baixa carga sensorial**. Por isso o texto é grande, as cores são calmas e não há animações nem transições. O foco do teclado fica sempre visível, e as ações importantes pedem confirmação explícita, o que evita toques por engano.

As funcionalidades entregues estão detalhadas em [docs/funcionalidades.md](docs/funcionalidades.md).

## Stack Tecnológica

- **Python** + **Django**, com views baseadas em classe e autenticação por sessão
- **SQLite** no desenvolvimento local; a migração para **PostgreSQL** já está encaminhada (o `psycopg2` consta nas dependências)
- **Bootstrap 5** carregado por CDN, mais um CSS próprio e pequeno (`static/css/conectatea.css`) para controlar os estímulos visuais em detalhe. Não usamos framework de JavaScript: onde é preciso, o JS é puro
- **Django REST Framework** + **SimpleJWT** na API (`/api/auth/...`)
- **Brevo** (API REST) para os e-mails transacionais

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

```bash
pytest
```

## Qualidade de código

```bash
flake8
```

## Integração Contínua (CI)

O projeto usa GitHub Actions (`.github/workflows/ci.yml`) para rodar testes automatizados e
validação de código a cada novo commit e pull request para `main`.
