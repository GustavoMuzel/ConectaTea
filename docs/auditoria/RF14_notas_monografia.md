# RF14 — notas para a próxima rodada do `.docx`

Data: 28/10/2026. O `.docx` não foi tocado. O `README.md` e o `docs/Fluxo.md` já estavam modificados no working
tree antes desta rodada e não foram alterados por ela.
Migração nova: `usuarios/0004_preferencia_acessibilidade` (tabela `preferencias_acessibilidade`).

## O que foi implementado

- **Modelo `PreferenciaAcessibilidade`** (app `usuarios`), uma por usuário: `tamanho_fonte` (normal, grande,
  muito grande), `alto_contraste` e `reduzir_estimulos` (ambos desligados por padrão).
- **Tela "Preferências"** (`/preferencias/`), para qualquer usuário logado (aluno, profissional e gestor).
  Cada um altera só as próprias; não há id na URL. O registro é criado no primeiro acesso à tela.
- **Aplicação em todo o sistema:** um context processor entrega as preferências do usuário logado a todos os
  templates, e o `base.html` põe as classes no `<body>`: `font-lg`, `font-xlg`, `high-contrast`,
  `reduce-stimuli`. Visitante e quem nunca abriu a tela ficam com o visual padrão.
- **Link "Preferências"** no menu de navegação, para quem está logado.
- **CSS** (`static/css/conectatea.css`):
  - Fonte grande e muito grande: ampliam todo o texto em 120% e 140% (a base do sistema já é 1,125 rem).
  - Alto contraste: fundo preto, texto branco, links, botões e bordas em amarelo/branco, foco amarelo.
  - Reduzir estímulos: sem animações, transições e sombras, e esconde o que tiver a classe `decorativo`.

## Onde o código difere do pedido ou da monografia

| # | Item | Observação |
|---|---|---|
| 1 | Valores gravados em minúsculas (`normal`, `grande`, `muito_grande`) | O pedido citava `NORMAL`/`GRANDE`/`MUITO_GRANDE`. Segui o padrão do projeto (`pendente`, `concluida`, ...). Só os nomes das constantes ficam em maiúsculas. |
| 2 | Fonte pela escala do `html`, não por `1.2rem`/`1.4rem` na base | Com o tamanho fixo, os títulos e botões do Bootstrap não cresceriam. A escala de 120% e 140% vale para tudo. Usa `html:has(body.font-lg)`, que exige navegador recente. |
| 3 | "Sem animações" já era regra global | O CSS do sistema já desligava animações e transições para todos. "Reduzir estímulos" acrescenta a retirada de sombras e o esconder de enfeites. |
| 4 | Ainda não há elemento decorativo no sistema | A classe `decorativo` existe como gancho; hoje nenhum template a usa, então a opção só remove sombras. |
| 5 | Gráficos do dashboard no alto contraste | O Chart.js desenha num `canvas`: o texto dos eixos passou a seguir a cor e o tamanho da página (lidos do `<body>` ao desenhar), mas as barras mantêm o azul suave (contraste suficiente sobre preto). A tabela "Ver como tabela" acompanha o tema. O gráfico é desenhado uma vez; a troca de preferência recarrega a página. |
| 6 | Uma consulta a mais por página para usuário logado | O context processor lê as preferências a cada requisição. |
| 7 | Abrir a tela de preferências grava um registro (com os valores padrão) | Mesmo sem salvar nada. |
| 8 | `on_delete=CASCADE` | Como pedido: preferência não é histórico. Excluir o usuário apaga as dele. |
| 9 | Preferências não afetam e-mails nem a API | Só as telas do sistema. |

## Pendências

- Falta conferir o visual no navegador (contraste de cada componente em alto contraste e a escala da fonte).
- Alto contraste e fonte maior não são aplicados antes do login, porque ainda não há preferência para o visitante.
