# Relatório de alterações da monografia (28/10/2026)

**Fonte:** `Sincronia_Monografia_Pos_Codigo.md` (Cérebro_IA), aplicado por `scripts/update_monografia.py` via Word (COM), com Controle de Alterações.
**Log da execução:** `scripts/update_monografia_log.json`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `E:\Downloads_Archive\Conectea Monografia\Monografia_PFC_conectea.docx` | Original, **intocado** (SHA-1 igual ao do backup; data 28/10 00:19) |
| `…\Monografia_PFC_conectea_backup.docx` | Cópia byte a byte do original |
| `…\Monografia_PFC_marcada.docx` | 185 revisões visíveis (Controle de Alterações) |
| `…\Monografia_PFC_atualizada.docx` | Revisões aceitas e Sumário regenerado |

## Integridade

| | Original | Marcada | Atualizada |
|---|---|---|---|
| Tabelas | 17 | 17 | 17 |
| Imagens inline | 22 | 22 | 22 |
| Arquivos de imagem (SHA-1) | 22 | 22 idênticos | 22 idênticos |

O original foi salvo por outro editor (imagens em `media/`, pasta `[trash]/`); o Word as reempacotou em `word/media/`, com o conteúdo idêntico byte a byte.

**Defeito do original corrigido:** os parágrafos com as imagens das Figuras 20, 21 e 22 estavam com estilo **Título 1**, e a atualização do Sumário (F9) copiava essas três imagens para dentro dele. O script troca o estilo desses parágrafos para o mesmo da Figura 19. Sem essa correção, um F9 manual no Word causa o mesmo problema.

## Aplicado (107 de 107 edições, nenhuma pulada)

Cada edição conferiu o texto antigo exato antes de trocar. O script pularia e registraria qualquer trecho não encontrado, mas nenhum foi pulado.

**Passo 1, Quadro 3:** Área do aluno e Painel do profissional (observações com RF06/RF08/RF09/RF10); Preferências → Implementado; Distribuição/tentativas/histórico → Implementado; Edição e arquivamento; passos → **Parcial** (passos seguem planejados); Anotações → Implementado ("Privadas"); gestão + dashboard do profissional (RF05); testes 102 → 140, com nota de CI suspenso; PostgreSQL e auditoria → **Parcial**.

**Passo 2, textos:**
- RF05: dashboard do profissional (descrição, atores, nova RN05); §4.1 com parágrafo novo (Big Numbers, Chart.js, acessibilidade, contagem por tentativa, limitações de CDN e filtros); Chart.js em §2.2 e nas Referências.
- RF06: passos marcados como não implementados; RN04 com arquivada visível, desarquivar só pelo admin e sem exclusão.
- RF07: RN01 (usuário ativo), RN03 (data local, hoje é válido), RN04 "previsto", nova RN05 (unicidade, 404).
- RF08: sem afirmar "apenas atribuídas"; nova RN06 (marca a `Atribuicao`, cria a atribuição já concluída se não houve distribuição); CA01 ajustado.
- RF09: pré-condição, fluxo (retoma tentativa), RN02/RN03 por aluno e atividade, número calculado, sem limite de repetições.
- RF10: RN03 (auditoria) marcada como prevista.
- RF11: anotação só sobre o aluno, tela por perfil, vínculo do momento da leitura, 404 para não-autor.
- RF14: §4.7 reescrito como implementado (120%/140%, alto contraste, redução de estímulos, depende de navegador atual).
- RNF04 e RNF05 previstos; RNF08 com `DB_ENGINE`, backup previsto e "FKs do histórico"; RNF12 com drf-spectacular configurado e rota pendente.
- Resumo/Abstract: estado atualizado, 140 testes, registro de acessos como previsto.
- §2.4 PostgreSQL via `DB_ENGINE` nos testes; §2.6 códigos como futuros; §2.7 140 testes + CI suspenso (texto do LEIAME B12.1); §2.8 backup "prevista"; §2.10 tabelas implementadas × planejadas.
- §4.3: "primeira versão" no passado + parágrafo novo com o que existe (Atribuição, constraint de tentativa em andamento, trava na view com `select_for_update`, atribuição criada na conclusão); §4.5 anotação implementada; §5 e §6 reescritos (implementado × próximas etapas).

**Passo 3, Quadro 1:** RF06, RF07, RF08, RF09, RF11 e RF14 → Implementado; RF05 atores + Profissional. **RF10 ficou Parcial** (ver abaixo).

**Passo 4, texto dos diagramas (só a prosa):** Fig. 6 (Atribuição/arquivada implementadas, `StatusRegistro` = `RegistroEvolucao.Status`); Anotacao e PreferenciaAcessibilidade "já implementadas"; Anotacao→RegistroEvolucao como relação prevista; `EmailService` é módulo; PreferenciasView, views do aluno e do profissional implementadas (nomes reais), DashboardProfissionalView fora dos diagramas; §3.4 e §3.4.5 sem afirmar o registro de acesso.

**Passo 5:** Sumário regenerado (2.10, 3.4.4, "DECISÕES DE PROJETO", páginas reais).

**Passo 6:** todos os typos da lista; 2.4 duplicada renumerada (2.5–2.10); títulos 2.2 e 2.3 separados do parágrafo (estilo Título 2 / corpo); **nova §3.4.4** para a Figura 19; §1.3 sem "Capítulo 7"; parêntese da Fonte da Figura 2; `0..1` e `0..*`.

## Decisões tomadas no lugar dos 🔎 (conferidas no código em 28/10)

- **`LogAcesso` não existe** (`grep` vazio). Por isso o RF10 ficou **Parcial** no Quadro 1, e não Implementado. A conta fica em 10 Implementados + 1 Parcial de 14, e não "11 de 14 = 78,6%". Para seguir o Inventário ("Implementado"), basta trocar a célula RF10 no Quadro 1.
- **RF09 da monografia estava errado:** dizia que atividade arquivada não pode ser refeita (RN05, CA04), mas `RefazerAtividadeView` permite. O texto agora segue o código e a decisão de 28/10 (arquivar não afeta o aluno).
- `Atribuicao.Status` **tem** `EM_ANDAMENTO` no código, então o texto da Fig. 6 foi mantido.
- Linha "Edição e arquivamento; passos" do Quadro 3: virou **Parcial**, em vez de ser separada em duas linhas.

## Não feito (exige edição manual ou decisão sua)

1. **Figuras (imagens):** Figs. 2–4 (tabelas novas, `active` × `is_active`), 6–15 (classes/views novas, retirar «a implementar»), BPMN 19/20. São PNGs; o texto ao redor já foi ajustado.
2. **§3.4.4:** o texto novo descreve o fluxo do código (RF08/RF09). **Conferir contra o desenho da Figura 19.**
3. **Lista de Figuras / Lista de Quadros:** são texto digitado, não campo, então não atualizam com F9. O "(a implementar)" das Figs. 7, 8, 10 e 15 continua lá.
4. **"Fonte:" nas Figuras 4 e 5–22:** não incluída.
5. **Quadro 2 sem coluna Situação:** mudança estrutural; as pendências estão escritas nos critérios (RNF04, RNF05, RNF08, RNF12).
6. **§2.2 não apresenta o Django em si:** o título foi separado, mas o parágrafo de apresentação precisa ser escrito por você.
7. **RNF01 (≤ 3 passos)** com o fluxo novo de refazer: não reavaliado.
8. **CA03 do RF14 (contraste 7:1)** e WCAG AA: não conferidos no navegador.
9. **RNF05 / Política × Brevo** (pendência de 16/11) e "apagar" × soft delete na Política: fora do `.docx`.
10. **CI "Implementado" no Quadro 3** foi mantido, com nota de suspensão (como o checklist pede).
11. **Código (D7):** a interface ainda chama a observação de "Anotações" (`apps/atividades/forms.py:21`, `templates/atividades/evolucao_aluno.html:16` "Salvar anotação"). A monografia usa "Observação" × "Anotação", então o código diverge do texto.
12. `Atividade.profissional` continua `CASCADE`. A RNF08 agora fala só das "FKs do histórico", o que fica correto.
