# Relatório de acompanhamento do PFC: 16/11/2026

**Projeto:** ConectaTEA, aplicativo web de apoio ao desenvolvimento de adolescentes autistas.
**Aluno:** Gustavo Muzel de Carvalho.

## 1. Versão apresentada

| Item | Onde |
|---|---|
| Repositório (público) | https://github.com/GustavoMuzel/ConectaTea |
| Branch | `entrega-16-11` |
| Commit | O último da branch em 16/11, informado na mensagem do Teams |
| Integração contínua | Pull request #4 ("Entrega 16 11"), da `entrega-16-11` para a `main`, com as 3 checagens verdes |
| Sistema publicado | https://conectatea-j0az.onrender.com |
| Instruções e evidências | [execucao.md](execucao.md) |
| Monografia | Arquivo enviado no Teams junto com este relatório |

## 2. O que foi desenvolvido desde a última versão avaliada

A última versão avaliada foi a branch `entrega0911-atualizado` (commit `75addf9`, de 13/11). Depois dela:

| Data | Commit | O que entrou |
|---|---|---|
| 14/11 | `f5f59ed` | Distribuição individual: o aluno vê somente as atividades distribuídas a ele, com o prazo. Tela inicial do aluno com alertas de atividades para fazer e atrasadas. Pedido de ajuda na atividade, com avisos por e-mail. Profissão e registro no conselho (CRP, CREFITO, CRFa), com conferência pelo gestor e revogação da aprovação. Videochamada com horário marcado pelo profissional, resposta do aluno, abertura dentro do sistema e registro de entrada e saída; permissão conferida a cada acesso. Limite de 5 tentativas de login. Rotas novas da API e documentação OpenAPI. Publicação no Render, com banco PostgreSQL no Neon |
| 15/11 | `0c77a41` | Auditoria de todas as ações, com IP, filtros e exportação em CSV. Diagnóstico do envio de e-mail no painel de gestão. Comando de dados fictícios para demonstração |
| 15/11 | `c2a54e6` | Teste de desempenho (RNF03): consultas por tela, teste de carga e carregamento no navegador ([desempenho.md](desempenho.md)) |
| 15/11 | `8ab1e19` | Celular do responsável com exatamente 11 números e botão "Mostrar" nos campos de senha |
| 16/11 | (este envio) | Cobertura de testes medida na CI (mínimo de 50% nos unitários), instruções e evidências de execução, este relatório |

Situação atual: 413 testes automatizados passando, cobertura de 52% só com os testes unitários e de 97% com todos,
flake8 sem avisos.

## 3. Apontamentos do parecer anterior

| Apontamento | Situação | Como verificar |
|---|---|---|
| Distribuição individualizada: a lista do aluno mostrava atividades não distribuídas a ele | Corrigido em 14/11 (`f5f59ed`) | Roteiro RF07 em [execucao.md](execucao.md); teste `test_atividade_distribuida_so_para_um_aluno_nao_aparece_para_o_colega` |
| Revogação da aprovação não cortava a videochamada | Corrigido em 14/11 (`f5f59ed`): a permissão é conferida a cada acesso | Roteiro RF05 e RF13; testes `test_revogar_aprovacao_do_dono_bloqueia_a_videochamada` e `test_membro_revogado_pela_administracao_perde_a_videochamada` |
| Videochamada registrava só o acionamento ("acionamento" tratado como entrada) | Corrigido em 14/11 (`f5f59ed`): acionamento, entrada e saída registrados separadamente, os dois últimos pelos eventos do Jitsi | Teste `test_entrada_e_saida_vem_dos_eventos_do_jitsi`; histórico das chamadas na sala |
| Inconsistências entre a documentação e o sistema; chat não implementado | Monografia revisada em 16/11: o chat foi retirado de todo o texto, e o RF12 passou a ser o pedido de ajuda, que está implementado. Requisitos, regras de negócio e Capítulos 2, 5 e 6 foram atualizados | Monografia enviada no Teams, com as alterações marcadas |
| Vídeo mostrando melhor o sistema | Pendente: o roteiro está pronto, e a gravação será feita no sistema publicado | — |

## 4. Itens exigidos na etapa de 09/11

| Item | Situação em 16/11 | Observação |
|---|---|---|
| Diagrama de classes e BPMN completos | Parcial | Os diagramas existem e cobrem todos os requisitos. As Figuras 3, 4, 7, 15 e 21 ainda mostram elementos do chat ou nomes antigos e estão sendo redesenhadas; o texto da monografia já foi corrigido |
| Integração ou consumo de API | Atendido | Consumo das APIs do Brevo (e-mail) e do Jitsi (IFrame API); API REST própria com JWT e documentação OpenAPI |
| Formulários com validação | Atendido | Cadastro (conselho, celular, termos), login com bloqueio, atividades (PDF verificado e link do Forms), distribuição (prazo), recuperação de senha |
| Pelo menos 75% dos casos de uso, com frontend e backend integrados | Atendido | 16 requisitos funcionais: 15 implementados e 1 parcial (RF06, cujos passos das atividades ficaram como trabalho futuro) |
| Documentação das regras de negócio | Atendido | Regras de negócio (RN) e critérios de aceite em cada requisito da monografia |
| Validação pelo orientador | A registrar | Seção 7 deste relatório |

Os itens do parecer da seção 3 foram corrigidos depois de 09/11, nas datas indicadas.

## 5. O que permanece pendente

- Redesenhar as Figuras 3, 4, 7, 15 e 21 da monografia, que ainda não mostram as mudanças.
- Gravar o vídeo de demonstração.
- Para 23/11: o manual do sistema e a ampliação dos testes unitários das principais classes. A cobertura já é medida
  na CI, hoje com 52%.
- Trabalhos futuros, registrados na monografia:
  - passos das atividades (RF06);
  - associar as tentativas às atribuições;
  - cancelar uma atribuição (RF07, RN04);
  - testes de usabilidade com o público-alvo, que dependem de aprovação ética.

## 6. Dúvidas para a orientação

1. O chat foi retirado e o RF12 passou a ser "Pedir ajuda na atividade", que está implementado e testado. A troca
   está de acordo, ou o RF12 deve ser apenas excluído?
2. A cobertura mínima de 50% deve ser medida só com os testes unitários (hoje 52%) ou com todos os testes (97%)?
3. Há um modelo ou formato esperado para o manual do sistema de 23/11?
4. O plano gratuito de hospedagem desliga o site depois de 15 minutos sem uso, e o primeiro acesso leva cerca de 1
   minuto. Isso é aceitável para a avaliação, ou o sistema deve ser apresentado rodando localmente?
5. Os diagramas atualizados podem ser gerados a partir do código (por exemplo, o modelo de dados), ou devem seguir
   o mesmo estilo dos diagramas atuais?

## 7. Validação do orientador

| Data | Itens conferidos | Observações | Orientador |
|---|---|---|---|
| 16/11/2026 | | | |
