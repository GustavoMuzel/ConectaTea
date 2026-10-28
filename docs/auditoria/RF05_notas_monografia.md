# RF05 — notas para a próxima rodada do `.docx`

Data: 28/10/2026. O `.docx`, o `README.md` e o `docs/Fluxo.md` não foram tocados. Nenhuma migração nova.

## O que mudou no RF05

- **Dashboard do Gestor:** inalterado. Continua em `/painel-gestao/` (`AdminDashboardView`,
  `templates/usuarios/painel_gestao.html`), só com Big Numbers.
- **Dashboard do Profissional (novo):** `DashboardProfissionalView` em `apps/acompanhamento/views.py`,
  rota `aluno/dashboard-profissional/` (nome `dashboard_profissional`), template
  `templates/acompanhamento/dashboard_profissional.html`. Link "Ver dashboard" no painel de atividades.
- **Big Numbers do profissional:** alunos vinculados; atividades distribuídas pendentes (`Atribuicao` com
  status `PENDENTE` do próprio profissional); atividades concluídas (`RegistroEvolucao` concluídos dos
  alunos dele).
- **Gráficos (Chart.js 4.5.0 via CDN, com SRI):** conclusões por semana (`TruncWeek` sobre
  `data_realizacao`) e conclusões por aluno. Barras, sem animação, cores suaves. Os dados chegam ao
  navegador por `json_script`; o JavaScript é puro, sem dependência Python nova.
- **Isolamento:** o profissional só vê dados de alunos vinculados a ele (`aluno__profissional`). Aluno recebe
  403 e visitante é redirecionado ao login (`ProfissionalRequiredMixin`). Testes em
  `apps/acompanhamento/test_dashboard.py`.

## Onde o código difere do pedido ou da monografia

| # | Item | Observação |
|---|---|---|
| 1 | `RegistroEvolucao` não tem FK para `Atribuicao` | O filtro `atribuicao__profissional` do pedido não existe. O isolamento usa `aluno__profissional`. Para a monografia: "conclusão" hoje é um registro por aluno e atividade, não por atribuição. |
| 2 | Status gravado em minúsculas (`'concluida'`) | O código usa `RegistroEvolucao.Status.CONCLUIDA`, não a string `'CONCLUIDA'`. |
| 3 | "Concluídas" vem de `RegistroEvolucao`, não de `Atribuicao` | Nada marca `Atribuicao` como concluída ainda (`ConcluirAtividadeView` só grava `RegistroEvolucao`; é Trilha A/RF08 e não foi tocada). Para o card "pendentes" não ficar parado, o dashboard conta só as `Atribuicao` PENDENTE cujo aluno ainda não concluiu aquela atividade. Quando o RF08 atualizar o status da `Atribuicao`, esse filtro vira redundante e pode sair. |
| 3a | Alunos homônimos | O gráfico agrupa por aluno (id), não por nome. Se dois alunos do profissional têm o mesmo nome, o rótulo ganha o id: `Maria (#12)`. |
| 4 | A rota mora no `urls.py` do app `acompanhamento`, sob o prefixo `aluno/` | Mesmo caso da rota do RF07: funciona (a view exige profissional), mas o prefixo engana. Avaliar mover para `painel/`. |
| 5 | Alunos com usuário inativo entram na contagem de "alunos vinculados" | Segue o mesmo critério da tela "Meus alunos". Decidir se o dashboard deve ignorá-los. |
| 6 | Sem conclusões, a tela mostra um aviso no lugar dos gráficos | Detalhe de implementação. |
| 7 | Os gráficos dependem do CDN jsDelivr | Sem internet, os números e as tabelas aparecem, mas os gráficos não (o script checa `window.Chart`). Acessibilidade: cada `canvas` tem `role="img"` e `aria-label`, e cada gráfico traz os mesmos dados numa tabela dentro de "Ver como tabela". |

## Pendências

- Gráficos são só de conclusões; não há gráfico por categoria de atividade nem por período configurável.
- Os gráficos não foram conferidos num navegador nesta rodada (só os dados e o HTML por teste).
- Sem teste para a borda de semana/fuso (domingo à noite em São Paulo já é segunda em UTC). `TruncWeek`
  usa o fuso corrente do Django, então deve estar certo, mas não está coberto.
- O histórico semanal é ilimitado e semanas sem conclusão não aparecem no eixo. Limitar às últimas ~12
  semanas se o volume crescer.
- Aviso do Django, fora do escopo do RF05: `apps/usuarios/admin.py:56` sobrescreve `get_actions()` sem o
  parâmetro `action_location` (`RemovedInDjango70Warning`, 50 ocorrências na suíte). Quebra no Django 7.0.
