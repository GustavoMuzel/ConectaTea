# RF07 — notas para a próxima rodada do `.docx`

Data: 28/10/2026. O `.docx`, o `README.md` e o `docs/Fluxo.md` não foram tocados.

O que o código faz e a monografia (§3.1.7, Figura 6) não descreve ou descreve diferente:

| # | Item no código | Situação na monografia | Sugestão |
|---|---|---|---|
| 1 | Restrição de unicidade `(atividade, aluno)` em `Atribuicao` (`uma_atribuicao_por_aluno_atividade`) | Não descrita | Documentar. Reenviar o formulário ou usar duas abas não duplica a atribuição; o aluno repetido é ignorado e a mensagem informa quantos foram criados. |
| 2 | `Atividade.arquivada` (BooleanField, default `False`), migração `atividades/0002_atividade_arquivada` | Figura 6 já marca o campo com `*` (a implementar) | Marcar como implementado. Só o campo existe: arquivar/editar continua pendente do RF06. |
| 3 | Só alunos com usuário ativo (`user.is_active`) aparecem na distribuição | Não descrito (RN01 fala só de vínculo) | Acrescentar à RN01 ou deixar como detalhe de implementação. |
| 4 | Atividade de outro profissional: a tela devolve 404 | Não descrito | Detalhe de implementação, mesmo padrão das demais telas do profissional. |
| 5 | URL `aluno/distribuir-atividade/<pk>/`: a rota mora no `urls.py` do app `acompanhamento`, montado sob o prefixo `aluno/` | Não descrito | Funciona (a view exige profissional), mas o prefixo engana. Avaliar mover para `painel/` quando houver o RF08. |
| 6 | Prazo é `DateField` (sem hora) e a comparação usa a data local (`America/Sao_Paulo`); prazo igual a hoje é aceito | RN03 diz "não pode ser anterior a hoje" | Coerente com a RN03; vale explicitar que hoje é válido. |
| 7 | Alternância SQLite/PostgreSQL por `DB_ENGINE` (`config/settings.py`, `.env.example`) | §2.4 prevê SQLite em dev e PostgreSQL em homologação/produção | Documentar as variáveis `DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`. |

## Pendências (não implementadas hoje)

- **RN04 (cancelar atribuição ainda não iniciada):** não existe nenhum caminho de cancelamento no código.
  O status `CANCELADA` existe no modelo, mas nenhuma view o grava. Fica para o RF09 ou etapa futura.
  Atenção: com a unicidade `(atividade, aluno)`, uma atribuição cancelada impede redistribuir a mesma
  atividade ao mesmo aluno. Quando o cancelamento for implementado, decidir se reativa a atribuição
  existente ou se a constraint passa a ignorar as canceladas (`condition=~Q(status='cancelada')`).
- **RF08:** o aluno ainda enxerga todas as atividades do profissional (`atividades_do_aluno`), não só as
  atribuídas a ele. `Atribuicao` não alimenta a lista do aluno nem o `RegistroEvolucao`.
- **Arquivadas na visão do aluno:** `atividades_do_aluno` não filtra `arquivada=False`; uma atividade
  arquivada continua aparecendo ao aluno. Tratar junto com o RF08/RF06 (1 linha quando o arquivar existir).
- **Arquivar não tem interface:** `Atividade.arquivada` só muda via shell/admin; `AtividadeAdmin` não o expõe.
- **PostgreSQL:** os 110 testes rodaram só em SQLite. O serviço `postgresql-x64-16` está parado nesta máquina;
  validar com `DB_ENGINE=postgresql` antes da entrega.
- **Migrações de outra trilha:** a `atividades/0002` foi criada junto com a `acompanhamento/0005`, por
  decisão explícita de 28/10. A Trilha B deve fazer `git pull` antes de rodar `makemigrations`.
