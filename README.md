# ConectaTEA

Aplicativo web para o desenvolvimento de habilidades sociais e de comunicação em adolescentes autistas, com atividades cadastradas e acompanhadas por profissionais de saúde e educação.

O projeto foi desenhado com foco em **baixa carga sensorial**: texto grande, cores calmas, sem animações ou transições, foco sempre visível e fluxos de confirmação explícitos para evitar toques acidentais.

Para o detalhamento de cada funcionalidade entregue, veja [docs/funcionalidades.md](docs/funcionalidades.md).

## Stack Tecnológica

- **Python** + **Django** (views baseadas em classe, autenticação por sessão)
- **SQLite** para desenvolvimento local, já preparado para migrar para **PostgreSQL** (`psycopg2` incluso nas dependências)
- **Bootstrap 5** via CDN, com um CSS próprio enxuto (`static/css/conectatea.css`) para controle fino de estímulos visuais — sem framework de JavaScript, só JS puro onde necessário
- **Django REST Framework** + **SimpleJWT** para a API (`/api/auth/...`)
- **Brevo** (API REST) para envio de e-mails transacionais

## Pré-requisitos

- Python 3.13+
- Git

## Instalação

1. Clone o repositório:

   ```bash
   git clone <url-do-repositorio>
   cd ConectTea
   ```

2. Crie e ative um ambiente virtual:

   ```bash
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # Linux/macOS
   source .venv/bin/activate
   ```

   Ou, com [uv](https://docs.astral.sh/uv/):

   ```bash
   uv venv
   uv pip install -r requirements.txt
   ```

3. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

4. Configure as variáveis de ambiente — copie o modelo e preencha os valores:

   ```bash
   cp .env.example .env
   ```

   Variáveis do `.env`:

   | Variável | Descrição |
   |---|---|
   | `SECRET_KEY` | Chave secreta do Django. Gere uma com `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
   | `DEBUG` | `True` em desenvolvimento, `False` em produção |
   | `ALLOWED_HOSTS` | Lista de hosts permitidos, separados por vírgula |
   | `BREVO_API_KEY` | Chave da API do Brevo para envio de e-mail transacional. Se vazia, o envio é ignorado e apenas registrado em log — o cadastro nunca falha por causa disso |
   | `BREVO_SENDER_EMAIL` | E-mail remetente configurado no Brevo |
   | `BREVO_SENDER_NAME` | Nome do remetente exibido nos e-mails |

5. Aplique as migrações:

   ```bash
   python manage.py migrate
   ```

6. (Opcional) Crie um superusuário para acessar o `/admin/` e o `/painel-gestao/`:

   ```bash
   python manage.py createsuperuser
   ```

7. Inicie o servidor de desenvolvimento:

   ```bash
   python manage.py runserver
   ```

   A aplicação fica disponível em `http://localhost:8000/`.

## Testes

```bash
pytest
```

## Qualidade de código

```bash
flake8
```
