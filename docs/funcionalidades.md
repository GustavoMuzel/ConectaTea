# Funcionalidades do ConectaTEA

Aqui estão as funcionalidades entregues no projeto, com o comportamento esperado de cada uma e as regras de negócio que se aplicam.

## Páginas Públicas e LGPD

- **Landing page (`/`)**: página de entrada aberta a qualquer visitante, sem login. Explica em poucas palavras o que é o ConectaTEA e traz dois botões diretos, "Entrar" e "Criar conta". Quem já está autenticado vai direto para a área do seu perfil (o painel do profissional ou as atividades do aluno).
- **Termos de Uso (`/termos/`) e Política de Privacidade (`/privacidade/`)**: páginas estáticas e públicas, também com baixa carga sensorial (texto grande, alto contraste, nenhuma animação). As duas explicam como o sistema trata dados de menores de idade, de acordo com a LGPD (Lei nº 13.709/2018).
- **Consentimento do responsável**: para cadastrar um aluno, o responsável legal precisa marcar uma caixa de consentimento. O texto dessa caixa tem links clicáveis para os Termos de Uso e para a Política de Privacidade. Quando o cadastro é confirmado:
  - o campo `Aluno.consentimento_data` guarda a data e a hora do consentimento;
  - o sistema envia um e-mail ao `guardian_email` pela API REST do Brevo, avisando que a conta foi criada e que o consentimento ficou registrado;
  - se a caixa não estiver marcada, o cadastro é recusado e nada é gravado no banco;
  - o e-mail nunca trava nem derruba o cadastro. Se a API do Brevo falhar (timeout, chave ausente, erro HTTP), a falha vai para o log e o fluxo segue.

## Autenticação e Perfis

- **Cadastro (`/cadastro/`) e login (`/entrar/`)**: usam a sessão do Django. Há um único formulário para cada tela, e ele muda conforme o perfil marcado no botão de opção (`Aluno` ou `Profissional`). Os campos do perfil que não foi escolhido ficam escondidos por JavaScript puro, e o backend refaz a validação corretamente de qualquer forma.
- **Perfil Aluno**: fica ligado a um `Profissional` responsável e guarda a data de nascimento e os contatos do responsável legal.
- **Perfil Profissional**: toda conta nova começa com `is_approved=False`. Enquanto um administrador ou gestor não aprova, o profissional não cadastra atividades nem vê alunos; se tentar abrir o painel, recebe o aviso de que a conta aguarda aprovação.
- Os parâmetros sensíveis estão marcados de forma explícita, então login e senha nunca aparecem nos relatórios de erro. Na autenticação, o e-mail é comparado sem distinguir maiúsculas de minúsculas.
- Contas desativadas (soft delete) não entram no sistema.

## Área do Aluno (UX Inclusiva)

- **Listagem de atividades (`/aluno/atividades/`)**: o aluno vê apenas as atividades do profissional a quem está vinculado e apenas as que ainda não concluiu. Se esse profissional for revogado ou desativado, as atividades dele saem da lista sozinhas.
- **Conclusão em duas etapas**: para evitar toques acidentais e excesso de estímulos, o botão "Concluir atividade" da listagem não finaliza nada por conta própria. Ele abre uma tela que pergunta de forma literal "Você já terminou a atividade [Nome]?" e oferece dois botões bem claros. "Sim, terminei" grava a conclusão; "Não, voltar" retorna à lista sem mudar coisa alguma.
- Concluir a mesma atividade duas vezes não cria registro repetido, porque o banco tem uma `UniqueConstraint`. Já a tentativa de concluir uma atividade de outro profissional devolve 404.

## Painel do Profissional

- **Cadastro de atividades (`/painel/`)**: depois de aprovado, o profissional cria atividades (título, categoria, descrição), que passam a aparecer para os alunos vinculados a ele.
- **Meus alunos (`/painel/alunos/`)**: mostra os alunos ligados ao profissional que está logado.
- **Evolução do aluno (`/painel/alunos/<id>/`)**: traz todo o histórico de atividades concluídas pelo aluno, das mais novas para as mais antigas. Em cada registro, o profissional pode escrever e salvar uma observação qualitativa (campo `observacoes`).
- **Isolamento estrito**: a tela de evolução e a ação de salvar observações conferem se o aluno pertence ao profissional autenticado. Quando alguém tenta ver ou anotar o histórico de um aluno de outro profissional, a resposta é 404. Não usamos 403 nem redirecionamento, para não revelar se o registro existe.

## Gestão e Administração

- **Painel de Gestão (`/painel-gestao/`)**: um dashboard feito no front-end com Bootstrap, pensado como opção mais simples que o admin técnico do Django. O acesso é restrito a `is_superuser` ou a `is_staff` que tenha a permissão `usuarios.change_profissional`. A tela mostra os KPIs (alunos ativos, profissionais aprovados, profissionais aguardando aprovação e total de atividades) e a lista de profissionais pendentes. Cada um tem um botão "Aprovar conta", que aprova com um clique só (POST) e volta ao painel com uma mensagem de sucesso. Para edições mais detalhadas, a seção "Acesso completo" leva às telas nativas do Django Admin.
- **Admin nativo do Django (`/admin/`)**: recebeu alguns ajustes:
  - ação em massa que aprova os profissionais selecionados;
  - busca de alunos pelo nome do aluno ou do responsável, filtro pelo profissional vinculado e data de consentimento visível na listagem, o que agiliza a auditoria de LGPD;
  - lista de atividades com filtro por categoria e por profissional, além de busca por título ou descrição.
- **Soft delete**: quando um `User`, `Aluno` ou `Profissional` é excluído pelo admin, a linha continua no banco e o usuário só é desativado (`is_active=False`). O histórico de atividades e de evolução nunca se perde, já que as chaves estrangeiras usam `PROTECT`. Ninguém consegue desativar a própria conta, e desativar um registro exige a permissão explícita de alteração sobre o usuário em questão.
