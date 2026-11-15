# Deploy: Render (aplicação) + Neon (PostgreSQL)

Os dois têm plano gratuito. O passo a passo leva uns 20 minutos.

## 1. Banco no Neon

1. Crie a conta em <https://neon.com> e um projeto chamado `conectatea`, com **PostgreSQL 16** e região
   **AWS US East (N. Virginia)**, a mesma do Render (ver "Região" abaixo).
2. Em **Connect**, copie a *connection string*. Ela tem este formato:
   `postgresql://usuario:senha@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`

## 2. Aplicação no Render

1. Crie a conta em <https://render.com> entrando com o GitHub.
2. **New > Blueprint**, escolha o repositório `ConectaTea` e a branch que vai ao ar. O Render lê o `render.yaml`.
3. Preencha as variáveis que ficaram em branco:

   | Variável | Valor |
   |---|---|
   | `DATABASE_URL` | a connection string do Neon |
   | `CONTATO_EMAIL` | e-mail de contato e do encarregado de dados (LGPD) |
   | `BREVO_API_KEY` e `BREVO_SENDER_EMAIL` | chave e remetente do Brevo (sem eles, os e-mails não saem, e o resto funciona) |
   | `DJANGO_SUPERUSER_EMAIL`, `DJANGO_SUPERUSER_NAME`, `DJANGO_SUPERUSER_PASSWORD` | o primeiro administrador |

4. Clique em **Apply**. O build (`build.sh`) instala as dependências, junta os arquivos estáticos, aplica as
   migrações no Neon e cria o administrador. No fim, o site fica em `https://conectatea.onrender.com`
   (ou parecido).

## O que muda em produção (`PRODUCAO=True`)

- HTTPS obrigatório, cookies só por HTTPS e HSTS.
- Arquivos estáticos servidos pelo **WhiteNoise**, comprimidos e com hash no nome.
- **PDFs das atividades guardados no banco** (`ARMAZENAMENTO_ARQUIVOS=banco`, tabela `arquivos_armazenados`):
  o disco do plano gratuito do Render é apagado a cada reinício.
- Conferência: `python manage.py check --deploy` sem avisos.

## Limitações do plano gratuito (para a banca)

- O Render **desliga a aplicação depois de 15 minutos sem acesso**; o primeiro acesso depois disso demora cerca
  de 1 minuto. Antes de apresentar, abra o site uma vez.
- O Neon também "dorme" sem uso e acorda no primeiro acesso, em poucos segundos.

## Região e LGPD

Render e Neon na **mesma região** deixam as páginas rápidas (cada página faz várias consultas ao banco, e cada
ida e volta entre EUA e Brasil custa cerca de 0,1 s). O Render não tem servidores no Brasil, então os dois ficam
na Virgínia (EUA). Isso é uma **transferência internacional de dados** (LGPD, art. 33), informada na Política de
Privacidade. Para uso real com dados de alunos, o ideal é hospedar tudo no Brasil (o Neon tem região São Paulo,
mas aí a aplicação também precisaria ficar no Brasil).

## Dados de demonstração (para a apresentação)

O comando `popular_demo` cria um cenário fictício "em uso": 1 gestor, 5 profissionais (um esperando aprovação),
9 alunos (um com pedido de vínculo esperando aceite e um sem profissional), atividades com PDF, 6 semanas de
histórico (conclusões, correções, uma atividade refeita, prazos vencidos), pedidos de ajuda, salas com equipe,
videochamadas passadas e a próxima já marcada, e a auditoria correspondente. Todas as contas usam e-mails
`@example.com` (domínio reservado, RFC 2606) e nenhum e-mail é enviado. As datas são relativas ao dia em que o
comando roda, então rode perto da apresentação.

No PowerShell, na pasta do projeto, com a `DATABASE_URL` do Neon (copie do Render, aba *Environment*):

```powershell
$env:DATABASE_URL = "cole-aqui-a-DATABASE_URL"
$env:ARMAZENAMENTO_ARQUIVOS = "banco"
python manage.py popular_demo
Remove-Item Env:DATABASE_URL, Env:ARMAZENAMENTO_ARQUIVOS
```

Depois da banca: `python manage.py popular_demo --apagar` (com as mesmas variáveis) remove só esses dados.
O comando se recusa a rodar se o banco tiver migrações pendentes ou se os PDFs não forem para o banco.
