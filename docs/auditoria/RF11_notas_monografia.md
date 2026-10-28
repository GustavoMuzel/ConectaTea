# RF11 — notas para a próxima rodada do `.docx`

Data: 28/10/2026. O `.docx`, o `README.md` e o `docs/Fluxo.md` não foram tocados.
Migração nova: `acompanhamento/0007_anotacao` (cria a tabela `anotacoes`).

## O que foi implementado

- **Modelo `Anotacao`** (app `acompanhamento`): `autor` (usuário), `aluno`, `texto`, `visibilidade`
  (`privada` por padrão, ou `compartilhada`), `criado_em`, `atualizado_em`.
- **Regra de leitura:** sobre um aluno, cada participante lê (a) as anotações que ele mesmo escreveu, privadas ou
  não, e (b) só as **compartilhadas** pelo outro participante do vínculo **atual** (aluno ↔ profissional dele).
  Ninguém lê a privada do outro.
- **Quem escreve:** o aluno (sobre si) e o profissional vinculado a ele. O autor vem da sessão e o aluno, da
  URL validada; nenhum dos dois é aceito do formulário.
- **Editar e excluir:** só o autor. Para qualquer outra pessoa, inclusive quem lê a anotação compartilhada, a
  resposta é 404. A exclusão pede confirmação numa tela própria.
- **Telas:** `painel/alunos/<id>/anotacoes/` (profissional; botão "Anotações" na tela de evolução do aluno) e
  `aluno/anotacoes/` (aluno; botão "Minhas anotações" em "Meu histórico"). Editar e excluir ficam em
  `aluno/anotacoes/<id>/editar|excluir/`, para os dois perfis.
- Texto vazio (ou só espaços) é recusado.

## Onde o código difere do pedido ou da monografia

| # | Item | Observação |
|---|---|---|
| 1 | Uma tela de lista + criação por perfil, em vez de duas views (criar e listar) | A criação e a lista ficam na mesma página, como no cadastro de atividades. |
| 2 | Troca de profissional | O vínculo vale o do momento da leitura. Se o aluno passa a outro profissional, o novo não lê o que o antigo compartilhou, e o aluno também deixa de ver as compartilhadas pelo antigo. As anotações continuam no banco, e o autor ainda pode editá-las e excluí-las (depois de salvar, o ex-profissional volta para a lista de alunos). Decidir se a monografia quer outra regra (por exemplo, o aluno manter o histórico). |
| 2a | **Limitação conhecida (decidida em 28/10/2026):** o profissional novo lê o que o aluno já compartilhou antes | `Aluno` não guarda a data do vínculo, então não há como separar o que o aluno compartilhou "para o profissional antigo" do que é para o novo. O novo profissional lê todas as compartilhadas do aluno. Mantido assim; mudar exigiria um campo de data do vínculo. |
| 3 | `on_delete=PROTECT` em autor e aluno (decidido em 28/10/2026) | O pedido original falava em `CASCADE`; trocou-se para `PROTECT`, como `RegistroEvolucao` e `Atribuicao`, porque o sistema nunca perde histórico. Excluir definitivamente um usuário ou aluno que tenha anotações levanta `ProtectedError` (coberto por teste); a remoção segue sendo lógica (`is_active=False`). |
| 4 | Edição não muda o autor nem o aluno | Só `texto` e `visibilidade` são editáveis. |
| 5 | Profissional não aprovado ou desativado | Perde o acesso às telas de anotação (403). As anotações dele ficam no banco. |
| 6 | Sem busca, filtro ou paginação | A lista mostra tudo, da mais recente para a mais antiga. |
| 7 | Rota do profissional declarada em `apps/atividades/urls.py` | Para ficar em `painel/alunos/...`. A view mora em `acompanhamento`, como pedido; as demais rotas de anotação ficam sob o prefixo `aluno/` do app. |
| 8 | Visibilidade para o responsável legal | A monografia não cita o responsável; ele não tem acesso ao sistema, então não lê anotações. |

## Pendências

- Não há aviso de que o texto compartilhado fica visível para a outra pessoa antes de salvar além do texto de
  ajuda do campo "Quem pode ler".
- Anotações não aparecem na tela de evolução nem no dashboard; só na tela própria.
- Para commitar o RF11 sozinho: `historico_aluno.html` (que leva o link "Minhas anotações") e
  `evolucao_aluno.html` (que mistura o "tentativa N" do RF09 com o link "Anotações") ainda têm alterações do
  RF09 sem commit; incluir os dois arquivos inteiros ou separar os trechos com `git add -p`.
