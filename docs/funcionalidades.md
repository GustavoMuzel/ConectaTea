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
- **Aceite dos termos (todos os perfis)**: o cadastro só é concluído com a caixa "Li e aceito os Termos de Uso e a Política de Privacidade, e autorizo o tratamento dos meus dados". A data e a hora ficam em `User.termos_aceitos_em`. Para alunos, continua valendo também a autorização do responsável.
- **Avisos no login**: mensagens claras para e-mail/senha incorretos e para conta desativada (esta só aparece para quem acertou a senha, para não revelar quais e-mails existem). Ao entrar e ao sair, o sistema confirma com uma mensagem.
- **Esqueci minha senha (`/senha/recuperar/`, RF03)**: o usuário informa o e-mail e recebe, pelo Brevo, um código de 6 números. Em `/senha/recuperar/codigo/` ele digita o código e a senha nova. O código vale 10 minutos, é de uso único, admite no máximo 5 tentativas erradas e só o hash fica guardado (`codigos_verificacao`). Um pedido novo invalida os códigos anteriores. A resposta é a mesma exista ou não a conta, e contas desativadas não recebem código.
- **Perfil Aluno**: guarda a data de nascimento e os contatos do responsável legal. O aluno **não escolhe o profissional no cadastro**: a conta nasce sem vínculo e, ao entrar, o aluno vê só o aviso de que ainda não está ligado a um profissional (as telas de atividades, histórico e anotações voltam para o início).
- **Vincular alunos (`/painel/alunos/vincular/`)**: o profissional **aprovado** vê a lista de alunos ativos ainda sem profissional (nome, e-mail parcial, como `m***@ex.com`, e data de cadastro) e clica em "Enviar pedido". O vínculo **só vale depois que o aluno aceita**: o pedido aparece na tela inicial do aluno com os botões "Aceitar" e "Recusar". Ao aceitar, os outros pedidos pendentes são cancelados e o aceite fica em `LogAcesso`.

## Salas e equipe do aluno

- **Sala do aluno (`/salas/<id>/`)**: nasce quando o aluno aceita o vínculo; o profissional do pedido é o **dono**. A sala tem uma **senha de 6 caracteres** (sem 0/O e 1/I/L), que só o dono vê e pode trocar.
- **Entrar em uma sala (`/salas/`)**: outro profissional aprovado digita a senha e o pedido fica "aguardando o dono". O dono aprova, recusa ou remove membros; cada aprovação fica em `LogAcesso`.
- **O que os membros fazem**: veem a evolução do aluno, **corrigem** (escrevem observações nas tentativas) e **propõem atividades**. A atividade proposta fica "aguardando análise" e só chega ao aluno quando o dono aprova; o dono também pode corrigi-la antes ou recusá-la com um motivo. Atividade postada pelo dono na sala é publicada na hora, só para aquele aluno. As anotações privadas (RF11) continuam só entre o aluno e o dono.
- **Videochamada (RF13)**: o botão "Entrar na videochamada" (sala e "Minha equipe") abre a chamada **dentro do ConectaTEA**, pela IFrame API do Jitsi (`JITSI_DOMINIO`, padrão `meet.jit.si`), com só os botões essenciais e sem sons de notificação. Se o navegador não carregar a chamada, há o botão "Abrir em outra aba". O acesso é conferido a cada entrada: aluno, dono e membros aprovados, **com a sala ativa** (o dono continua sendo o profissional do aluno e está aprovado e ativo) e o profissional ainda aprovado pela administração. Revogar a aprovação corta também a chamada; remover um membro troca o endereço da sala no Jitsi. O sistema registra o **acionamento** (abriu a chamada) e, na chamada embutida, a **entrada e a saída confirmadas pelos eventos do Jitsi** (`videoConferenceJoined`/`videoConferenceLeft`), com a duração. Na outra aba, só o acionamento. Áudio e vídeo nunca são gravados.
- **Videochamada só com horário marcado**: quem marca a chamada é o **profissional responsável** (dono da sala), com dia, hora e "o que vamos fazer". O aluno vê o horário no Início e em "Minha equipe", e **só consegue entrar de 15 minutos antes até 2 horas depois** do horário marcado; fora disso, o botão não aparece e o acesso direto volta para "Minha equipe" com o aviso de quando a chamada abre. Os profissionais da sala entram a qualquer momento. A sala mostra quem está na chamada agora e o histórico das chamadas.
- **Minha equipe (`/salas/minha-equipe/`)**: o aluno vê todos os profissionais que participam da sala dele.
- **Profissão e conselho**: no cadastro, o profissional escolhe a profissão: **Pedagogia** (sem conselho), **Psicologia** (CRP), **Terapia ocupacional** (CREFITO) ou **Fonoaudiologia** (CRFa). Para as três com conselho, informa o **estado (UF)** e o **número do registro** (validado e normalizado; o mesmo registro não serve para duas contas) e, se quiser, a área de atuação (ex.: ABA). No Painel de Gestão, o gestor vê o registro formatado (ex.: `CRP-SP 06/123456`) com o link para o site oficial do conselho e aprova com "Conferi e aprovo", que grava **quem aprovou e quando**. A lista de profissionais aprovados tem o botão **Revogar**, que corta na hora o acesso aos alunos, às salas e à videochamada.
- **Perfil Profissional**: toda conta nova começa com `is_approved=False`. O formulário de cadastro, o e-mail de boas-vindas e a tela inicial avisam que a conta precisa ser aprovada. Enquanto um administrador ou gestor não aprova, o profissional não cadastra atividades nem vê alunos; se tentar abrir o painel, volta à tela inicial com o aviso de que a conta aguarda aprovação.
- Os parâmetros sensíveis estão marcados de forma explícita, então login e senha nunca aparecem nos relatórios de erro. Na autenticação, o e-mail é comparado sem distinguir maiúsculas de minúsculas.
- Contas desativadas (soft delete) não entram no sistema.

## Área do Aluno (UX Inclusiva)

- **Início do aluno (`/aluno/`)**: primeira tela depois do login. Mostra um **alerta** em uma frase (atividades que passaram do prazo, atividades para fazer e o prazo mais próximo, ou "Tudo em dia!"), os números (para fazer, passaram do prazo, feitas nos últimos 7 dias e no total, sem comparar com colegas), as próximas 3 atividades com o botão "Fazer" e a próxima videochamada. No menu, "Minhas atividades" mostra um **contador** das atividades em aberto.
- **Listagem de atividades (`/aluno/atividades/`)**: o aluno vê apenas as atividades do profissional a quem está vinculado e apenas as que ainda não concluiu. Se esse profissional for revogado ou desativado, as atividades dele saem da lista sozinhas.
- **Conclusão em duas etapas**: para evitar toques acidentais e excesso de estímulos, o botão "Concluir atividade" da listagem não finaliza nada por conta própria. Ele abre uma tela que pergunta de forma literal "Você já terminou a atividade [Nome]?" e oferece dois botões bem claros. "Sim, terminei" grava a conclusão; "Não, voltar" retorna à lista sem mudar coisa alguma.
- Concluir a mesma atividade duas vezes não cria registro repetido, porque o banco tem uma `UniqueConstraint`. Já a tentativa de concluir uma atividade de outro profissional devolve 404.

- **Preciso de ajuda**: na tela da atividade, o aluno clica em "Preciso de ajuda" (texto opcional: "O que está difícil?"). O profissional responsável recebe um e-mail e vê o pedido em "Meus alunos", com um contador no menu, e marca como respondido. Um pedido aberto por atividade.
- **Resposta à videochamada**: com uma chamada marcada, o aluno responde "Vou participar" ou "Não vou conseguir" no Início ou em "Minha equipe"; o dono vê a resposta na sala. Remarcar o horário apaga a resposta anterior.

## Avisos por e-mail ao responsável

- Quando o profissional **marca uma videochamada** (para o responsável e para o aluno) e quando **distribui uma atividade** (com o prazo, se houver).
- **Atividades com prazo vencido**: comando `python manage.py avisar_atrasadas` (com `--simular` para só contar), para rodar uma vez por dia num agendador (Agendador de Tarefas do Windows, cron ou Cron Job do Render).
- Os e-mails não levam o nome do aluno nem o conteúdo das atividades: só o essencial e o convite para entrar no sistema.

## Painel do Profissional

- **Cadastro de atividades (`/painel/`)**: depois de aprovado, o profissional cria atividades (título, categoria, instruções) e escolhe **um** material: **arquivo PDF** (só PDF de verdade, até 10 MB) ou **link do Google Forms** (`https://forms.gle/...` ou `https://docs.google.com/forms/...`). O PDF não fica público: é entregue por `/painel/atividades/<id>/material/`, que confere quem pode ver.
- **Distribuição individual (RF07)**: o aluno só recebe as atividades da biblioteca que foram **distribuídas a ele** (mais as atividades exclusivas da sala dele, já publicadas). Atividade não distribuída, de outro aluno, arquivada ou com distribuição cancelada não aparece nem pode ser aberta ou concluída (404). A lista mostra o **prazo** e avisa quando passou; as com prazo vêm primeiro.
- **Fazer a atividade (aluno)**: na tela da atividade, o aluno abre o material (o sistema registra na sessão), escreve a resposta e clica em "Concluir atividade". Sem abrir o material ou sem resposta, a conclusão é recusada com aviso. A resposta fica em `RegistroEvolucao.resposta` e aparece para o profissional na tela de evolução, junto do campo de correção.
- **Meus alunos (`/painel/alunos/`)**: mostra os alunos ligados ao profissional que está logado.
- **Evolução do aluno (`/painel/alunos/<id>/`)**: traz todo o histórico de atividades concluídas pelo aluno, das mais novas para as mais antigas. Em cada registro, o profissional pode escrever e salvar uma observação qualitativa (campo `observacoes`).
- **Isolamento estrito**: a tela de evolução e a ação de salvar observações conferem se o aluno pertence ao profissional autenticado. Quando alguém tenta ver ou anotar o histórico de um aluno de outro profissional, a resposta é 404. Não usamos 403 nem redirecionamento, para não revelar se o registro existe.

## Gestão e Administração

- **Auditoria (`/painel-gestao/auditoria/`)**: aba do Painel de Gestão, só para gestor. Lista os registros de acesso a dados de alunos (`LogAcesso`) e as videochamadas, com filtro por pessoa, aluno e período, paginação e exportação em CSV. Só leitura; no admin, os registros também não podem ser criados, editados nem apagados.
- **Painel de Gestão (`/painel-gestao/`)**: um dashboard feito no front-end com Bootstrap, pensado como opção mais simples que o admin técnico do Django. O acesso é restrito a `is_superuser` ou a `is_staff` que tenha a permissão `usuarios.change_profissional`. A tela mostra os KPIs (alunos ativos, profissionais aprovados, profissionais aguardando aprovação e total de atividades) e a lista de profissionais pendentes. Cada um tem um botão "Aprovar conta", que aprova com um clique só (POST) e volta ao painel com uma mensagem de sucesso. Para edições mais detalhadas, a seção "Acesso completo" leva às telas nativas do Django Admin.
- **Admin nativo do Django (`/admin/`)**: recebeu alguns ajustes:
  - ação em massa que aprova os profissionais selecionados;
  - busca de alunos pelo nome do aluno ou do responsável, filtro pelo profissional vinculado e data de consentimento visível na listagem, o que agiliza a auditoria de LGPD;
  - lista de atividades com filtro por categoria e por profissional, além de busca por título ou descrição.
- **Soft delete**: quando um `User`, `Aluno` ou `Profissional` é excluído pelo admin, a linha continua no banco e o usuário só é desativado (`is_active=False`). O histórico de atividades e de evolução nunca se perde, já que as chaves estrangeiras usam `PROTECT`. Ninguém consegue desativar a própria conta, e desativar um registro exige a permissão explícita de alteração sobre o usuário em questão.

## Identidade visual

- O logo do ConectaTEA (quadrado azul com dois círculos ligados) continua o mesmo.
- O **laço da conscientização do autismo**, com peças de quebra-cabeça em tons suaves (azul, amarelo, vermelho e verde, sem cores saturadas, RNF02), aparece na página inicial, no rodapé (com o 2 de abril, Dia Mundial de Conscientização do Autismo) e na página "Sobre o TEA". Uma faixa fina com as mesmas cores fica no topo. Com "reduzir estímulos" ou "alto contraste", o laço fica de uma cor só e a faixa some.
- A página "Sobre o TEA" explica o laço e também o símbolo do infinito (neurodiversidade), preferido por parte da comunidade autista.

## Deploy

- Render (aplicação, `render.yaml` e `build.sh`) + Neon (PostgreSQL), passo a passo em [docs/deploy.md](deploy.md).

## Segurança do login (RNF04)

- Depois de **5 tentativas erradas** com o mesmo e-mail, o login fica bloqueado por **15 minutos**, na tela e na API (resposta 429). Acertar antes do limite zera a contagem.
- Os limites (login e pedidos de código do RF03) usam o **cache no banco** (`DatabaseCache`, tabela `cache_conectatea`, criada pela migração `usuarios.0008`). Assim valem para todos os processos da aplicação, e não só para o processo que recebeu o pedido.

## API REST

- Documentação interativa (OpenAPI/Swagger, RNF12): **`/api/docs/`**; esquema em `/api/schema/`.
- `POST /api/auth/login/` (com limite de tentativas), `POST /api/auth/refresh/`, `GET /api/auth/me/`.
- `GET /api/aluno/atividades/`: atividades distribuídas ao aluno, com prazo e se já concluiu.
- `GET /api/profissional/alunos/`: alunos acompanhados (como responsável ou na equipe), com total de conclusões.
- `GET /api/saude/`: situação da API, para monitoramento.
