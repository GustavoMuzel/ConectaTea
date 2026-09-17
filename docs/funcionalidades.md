# Funcionalidades do ConectaTEA

Este documento descreve as funcionalidades entregues no projeto, o comportamento esperado de cada uma e as regras de negócio envolvidas.

## Páginas Públicas e LGPD

- **Landing page (`/`)** — página inicial pública, sem exigir login, explicando de forma simples o que é o ConectaTEA e oferecendo botões diretos para "Entrar" e "Criar conta". Usuários já autenticados são redirecionados automaticamente para a área correspondente ao seu perfil (painel do profissional ou atividades do aluno).
- **Termos de Uso (`/termos/`) e Política de Privacidade (`/privacidade/`)** — páginas estáticas, públicas, com layout de baixa carga sensorial (texto grande, sem animações, alto contraste). Descrevem o tratamento de dados de menores de idade conforme a LGPD (Lei nº 13.709/2018).
- **Consentimento do responsável** — no cadastro de um aluno, o formulário exige que o responsável legal marque uma caixa de consentimento cujo texto contém links clicáveis para os Termos de Uso e a Política de Privacidade. Ao confirmar o cadastro:
  - a data e a hora do consentimento são gravadas no campo `Aluno.consentimento_data`;
  - um e-mail é disparado ao `guardian_email` pela API REST do Brevo, informando a criação da conta e o consentimento registrado;
  - o cadastro do aluno é rejeitado (sem gravar nada no banco) se a caixa não for marcada.
  - o envio de e-mail nunca bloqueia nem quebra o cadastro: falhas na API do Brevo (timeout, chave ausente, erro HTTP) são registradas em log e ignoradas.

## Autenticação e Perfis

- **Cadastro (`/cadastro/`) e login (`/entrar/`)** baseados em sessão do Django, com formulários únicos que se adaptam ao perfil escolhido (`Aluno` ou `Profissional`) via rádio button. O bloco de campos correspondente ao perfil não selecionado fica oculto (JavaScript puro, com fallback correto de validação no backend).
- **Perfil Aluno** — vinculado a um `Profissional` responsável, com dados de nascimento e de contato do responsável legal.
- **Perfil Profissional** — toda conta nova nasce com `is_approved=False` e só pode atuar (cadastrar atividades, ver alunos) depois de aprovada por um administrador ou gestor. Um profissional pendente que tenta acessar seu painel recebe uma mensagem de "aguardando aprovação".
- Login e senha nunca aparecem em relatórios de erro (parâmetros sensíveis marcados explicitamente); e-mail não diferencia maiúsculas/minúsculas na autenticação.
- Contas inativas (soft delete) não conseguem fazer login.

## Área do Aluno (UX Inclusiva)

- **Listagem de atividades (`/aluno/atividades/`)** — mostra somente as atividades cadastradas pelo profissional vinculado ao aluno, e somente as ainda não concluídas. Se o profissional for revogado ou desativado, suas atividades somem automaticamente da lista do aluno.
- **Conclusão em duas etapas** — para prevenir toques acidentais e sobrecarga sensorial, o botão "Concluir atividade" na listagem não conclui a atividade diretamente. Ele leva a uma tela de confirmação literal ("Você já terminou a atividade [Nome]?") com dois botões claros: "Sim, terminei" (que efetivamente registra a conclusão) e "Não, voltar" (que retorna à listagem sem nenhuma alteração).
- Tentar concluir a mesma atividade duas vezes não gera duplicidade (`UniqueConstraint` no banco); tentar concluir uma atividade de outro profissional retorna 404.

## Painel do Profissional

- **Cadastro de atividades (`/painel/`)** — o profissional aprovado cadastra atividades (título, categoria, descrição) que ficam disponíveis para os alunos vinculados a ele.
- **Meus alunos (`/painel/alunos/`)** — lista os alunos vinculados ao profissional logado.
- **Evolução do aluno (`/painel/alunos/<id>/`)** — histórico completo das atividades concluídas por aquele aluno, da mais recente para a mais antiga. Para cada registro, o profissional pode escrever e salvar uma anotação qualitativa (campo `observacoes`).
- **Isolamento estrito** — tanto a tela de evolução quanto a ação de salvar observações validam que o aluno pertence ao profissional autenticado; tentar acessar ou anotar o histórico de um aluno de outro profissional retorna 404 (nunca 403 ou redirecionamento, para não revelar se o registro existe).

## Gestão e Administração

- **Painel de Gestão (`/painel-gestao/`)** — dashboard no front-end (Bootstrap), alternativa mais simples ao admin técnico do Django, restrito a `is_superuser` ou a `is_staff` com a permissão `usuarios.change_profissional`. Exibe KPIs (total de alunos ativos, profissionais aprovados, profissionais aguardando aprovação, total de atividades) e uma lista de profissionais pendentes com um botão "Aprovar conta" que aprova a conta com um único clique (POST), redirecionando de volta ao painel com mensagem de sucesso. Uma seção "Acesso completo" linka para as telas nativas do Django Admin quando o gestor precisa de edições mais detalhadas.
- **Admin nativo do Django (`/admin/`)** — refinado com:
  - ação em massa para aprovar profissionais selecionados;
  - busca de alunos por nome do aluno ou do responsável, filtro por profissional vinculado, e exibição da data de consentimento na listagem (auditoria rápida de LGPD);
  - listagem de atividades com filtro por categoria e profissional, e busca por título/descrição.
- **Soft delete** — excluir um `User`, `Aluno` ou `Profissional` pelo admin nunca apaga a linha do banco: apenas desativa o usuário (`is_active=False`). O histórico de atividades e evoluções nunca é apagado (chaves estrangeiras protegidas com `PROTECT`). Um usuário não consegue desativar a si mesmo, e desativar um registro exige a permissão explícita de alteração do usuário correspondente.
