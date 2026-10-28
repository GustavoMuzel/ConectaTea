# RF06 e RF10 — notas para a próxima rodada do `.docx`

Data: 28/10/2026. O `.docx`, o `README.md` e o `docs/Fluxo.md` não foram tocados. Nenhuma migração nova
(o campo `Atividade.arquivada` veio com o RF07, migração `atividades/0002`).

## O que mudou

### RF06 — editar e arquivar atividades
- **Editar:** `AtividadeUpdateView` (`atividades/<pk>/editar/`, nome `editar_atividade`). Usa o mesmo
  `AtividadeForm` do cadastro (título, descrição, categoria). Só atividades do próprio profissional; de outro
  profissional dá 404. O campo `arquivada` não faz parte do formulário.
- **Arquivar:** `ArquivarAtividadeView` (POST em `atividades/<pk>/arquivar/`, nome `arquivar_atividade`).
  Marca `arquivada = True`. A atividade arquivada continua no painel do profissional (com a marca
  "Arquivada") e no histórico de evolução dos alunos; sai da distribuição (RN02 do RF07): o formulário de
  distribuição não a oferece e a tela de distribuição devolve 404.
- **Painel de atividades:** botões "Editar" e "Arquivar" em cada atividade; "Distribuir" e "Arquivar" só
  aparecem para atividades ativas.
- Todas as rotas exigem profissional aprovado (aluno 403, visitante vai ao login).

### RF08 — conclusão atualiza a atribuição (correção apontada na revisão do RF05)
- `ConcluirAtividadeView` agora, na mesma transação do registro de evolução, marca a `Atribuicao` do aluno
  como `CONCLUIDA`. Se a atividade nunca foi distribuída ao aluno (ele a viu pela lista do profissional),
  é criada uma `Atribuicao` já `CONCLUIDA`, com o profissional dono da atividade. A unicidade
  `(atividade, aluno)` impede duplicata; concluir duas vezes não cria nada novo.

### RF10 — evolução e observações
- `EvolucaoAlunoView` e `SalvarObservacaoView` já estavam implementadas e corretas; nenhuma alteração de
  código. A observação salva volta preenchida na própria tela de evolução (o textarea carrega o valor).
  Foi só acrescentado teste: a observação aparece na evolução; aluno não acessa a evolução de outro aluno
  (403) nem salva observação.

## Onde o texto da monografia e o código divergem

| # | Item | Observação |
|---|---|---|
| 1 | Numeração das regras | No pedido, "RN04" foi usada para "arquivada some da distribuição". Na monografia (§3.1.7) isso é a **RN02**; a RN04 é o cancelamento de atribuição, ainda não implementado. O `.docx` não precisa mudar, só vale cuidar da citação. |
| 2 | Atribuição criada na conclusão | A monografia descreve a `Atribuicao` como resultado da distribuição (RF07). Agora ela também pode nascer na conclusão, quando não houve distribuição. Registrar como decisão de compatibilidade até o RF08 passar a exigir distribuição. |
| 3 | Conclusão reativa atribuição cancelada | Se existir `Atribuicao` `CANCELADA` e o aluno concluir a atividade, ela vira `CONCLUIDA`. Hoje não existe cancelamento (RN04), então não ocorre; definir a regra quando o RN04 for feito. |
| 4 | Arquivada continua visível ao aluno (**decisão tomada em 28/10/2026**) | `atividades_do_aluno` não filtra `arquivada`, de propósito. Arquivar tira a atividade da biblioteca e impede novas distribuições (RN02); não a esconde de quem já a recebeu, que continua podendo concluí-la, o que preserva o histórico. Retirar uma atividade da tela do aluno é papel do cancelamento de atribuição (RN04), previsto para etapa futura. Ao descrever o RF06 no `.docx`, deixar claro que "arquivar" não afeta o que o aluno já recebeu. |
| 5 | Desarquivar | Não existe. Arquivar é de mão única na interface (só pelo admin do Django). |
| 6 | Exclusão de atividade | Não existe; arquivar é a forma de retirar uma atividade de uso, preservando o histórico (as FKs são `PROTECT`). |
| 7 | Dashboard (RF05) | O filtro do dashboard que exclui "pendentes" de quem já concluiu ficou redundante para conclusões novas. Foi mantido porque cobre registros antigos criados antes desta correção. |

## Pendências

- RN04 (cancelar atribuição ainda não iniciada): sem implementação.
- Atribuições antigas (anteriores a esta correção) continuam `PENDENTE` no banco mesmo com a atividade já
  concluída; o dashboard as ignora, mas o dado não foi migrado.
- Tela do aluno ainda lista todas as atividades do profissional, não só as distribuídas a ele (RF08 completo).
