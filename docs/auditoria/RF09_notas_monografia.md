# RF09 — notas para a próxima rodada do `.docx`

Data: 28/10/2026. O `.docx`, o `README.md` e o `docs/Fluxo.md` não foram tocados.
Migração nova: `acompanhamento/0006_rf09_refazer_atividade` (só troca uma constraint; nenhuma coluna nova).

## Mudança no banco (constraint de `RegistroEvolucao`)

| Antes (`0004`) | Depois (`0006`) |
|---|---|
| `uma_conclusao_por_aluno_atividade`: no máximo **um** registro `concluida` por (aluno, atividade) | removida |
| — | `uma_em_andamento_por_aluno_atividade`: no máximo **um** registro `em_andamento` por (aluno, atividade) |

- **Por quê:** refazer uma atividade gera uma nova conclusão da mesma atividade. A regra antiga impedia isso.
  A nova garante a RN03 (uma tentativa em andamento por vez).
- **O que se perdeu:** a trava do banco contra duas conclusões iguais por duplo clique ou duas abas. A
  proteção passou para a `ConcluirAtividadeView`, que trava a linha do aluno (`select_for_update`), fecha a
  tentativa em andamento se houver e só cria uma conclusão nova quando ainda não existe nenhuma. Em SQLite
  o `select_for_update` não faz nada; em PostgreSQL funciona.
- Os valores gravados continuam em minúsculas (`'em_andamento'`, `'concluida'`).

## O que mudou no sistema

- **Aluno:** tela "Meu histórico" (`aluno/historico/`): uma linha por atividade já concluída, com o total de
  conclusões e a data da última, e o botão "Fazer de novo". Link no menu do aluno.
- **Fazer de novo** (`RefazerAtividadeView`, POST em `aluno/atividades/<pk>/refazer/`): abre uma tentativa
  `em_andamento` e leva o aluno à tela de confirmação do RF08. Apertar de novo retoma a mesma tentativa. Só
  funciona para atividade que o aluno já concluiu (senão 404). Ao confirmar, a própria tentativa vira
  `concluida` com a data de agora.
- **Profissional:** a tela de evolução do aluno lista todas as conclusões, da mais recente para a mais
  antiga, com "tentativa N" e a observação de cada uma. A numeração é calculada (função de janela por
  atividade); **não existe campo `tentativa`** no banco.

## Onde o código difere do pedido ou da monografia

| # | Item | Observação |
|---|---|---|
| 1 | Sem campo `tentativa` | O pedido falava em "incrementar o número da tentativa". O número é derivado da ordem das conclusões, para não criar coluna. A "tentativa" é o próprio `RegistroEvolucao`. |
| 2 | "Tentativas" no histórico do aluno são só as concluídas | Uma tentativa em andamento não conta no total. |
| 3 | O dashboard (RF05) passa a contar conclusões, não atividades distintas | O card passou a se chamar "Conclusões de atividades" e o gráfico por aluno também soma tentativas; refazer uma atividade aumenta o número. Ajustar o texto do RF05 na monografia ou separar as métricas depois. |
| 4 | A `Atribuicao` não volta a "em andamento" ao refazer | Continua `CONCLUIDA`. O estado da tentativa vive no `RegistroEvolucao`. |
| 5 | A lista "Minhas atividades" do aluno continua escondendo o que ele já concluiu | Uma refeita em andamento não reaparece ali; o caminho de volta é "Meu histórico" > "Fazer de novo" (retoma a mesma tentativa). |
| 6 | Registros `pendente` antigos continuam no banco | Não são tocados; concluir cria uma conclusão nova ao lado deles. |
| 7 | Dois testes antigos mudaram de propósito | `test_banco_barra_segunda_conclusao` virou `test_banco_permite_refazer_varias_conclusoes`; no teste de registro não concluído, o caso `em_andamento` agora termina com 1 registro (a tentativa é fechada, não duplicada). |
| 8 | Profissional desativado ou reprovado | As atividades dele somem do histórico do aluno (mesma regra da lista "Minhas atividades"), para não oferecer um "Fazer de novo" que daria 404. O registro continua no banco e na tela de evolução. |
| 9 | `docs/Fluxo.md` ficou defasado | A linha que cita a constraint `uma_conclusao_por_aluno_atividade` e diz que reconfirmar não duplica não vale mais; faltam as rotas `historico/` e `refazer/` e o conceito de "tentativa". O arquivo não foi alterado por restrição da rodada; atualizar na próxima. |

## Pendências

- Cancelamento de atribuição (RN04) continua fora; seria o caminho para tirar uma atividade da tela do aluno.
- Sem limite de quantas vezes o aluno pode refazer.
