"""Aplica o checklist de sincronia na monografia via Word (COM), sem tocar no original.

Gera, na pasta do original:
  Monografia_PFC_conectea_backup.docx  cópia byte a byte do original
  Monografia_PFC_marcada.docx          alterações com Controle de Alterações
  Monografia_PFC_atualizada.docx       revisões aceitas e Sumário atualizado

Cada edição confere o texto antigo antes de trocar; se não achar exatamente uma
ocorrência, pula e registra. Uso: py -3.14 scripts/update_monografia.py
"""
import json
import shutil
import sys
from pathlib import Path

import win32com.client

PASTA = Path(r"E:\Downloads_Archive\Conectea Monografia")
ORIGINAL = PASTA / "Monografia_PFC_conectea.docx"
BACKUP = PASTA / "Monografia_PFC_conectea_backup.docx"
MARCADA = PASTA / "Monografia_PFC_marcada.docx"
ATUALIZADA = PASTA / "Monografia_PFC_atualizada.docx"
LOG = Path(__file__).with_name("update_monografia_log.json")

WD_COLLAPSE_END = 0
WD_FORMAT_DOCX = 16

# ---------------------------------------------------------------- edições
# ("rep", id, antigo, novo, {opções})  opções: last=True pega a última ocorrência
#   (títulos repetidos no Sumário); followed_by="\r" exige esse caractere depois.
# ("cell", id, tabela, linha, coluna, antigo, novo)  índices do Word (base 1).
# ("after", id, âncora, texto, âncora_do_formato)  novo parágrafo após o da âncora.
# ("split", id, título, âncora_título_ref, âncora_corpo_ref)  separa título fundido.
EDITS = [
    # Passo 6: digitação e numeração
    ("rep", "T01 título", "apoio à ao desenvolvimento pessoal de adolescentes autista",
     "apoio ao desenvolvimento pessoal de adolescentes autistas", {}),
    ("rep", "T02 §1.1.1", "a adolescentes autista e acompanharem",
     "a adolescentes autistas e acompanharem", {}),
    ("rep", "T03 §1.1.2 notações", "as tentativas dos alunos, as notações e a comunicação",
     "as tentativas dos alunos, as anotações e a comunicação", {}),
    ("rep", "T04 §1.1.2 testes", "por meio de teste autorizados e de teste de usabilidade com usuário/ou profissionais",
     "por meio de testes automatizados e de testes de usabilidade com usuários e/ou profissionais", {}),
    ("rep", "T05 §1.2", "o diferencial do projeto está simplicidade",
     "o diferencial do projeto está na simplicidade", {}),
    ("rep", "T06 §1.3 Capítulo 7", "o Capítulo 6 traz as considerações finais e o Capítulo 7 reúne as referências bibliográficas.",
     "o Capítulo 6 traz as considerações finais e, ao final, são apresentadas as referências bibliográficas.", {}),
    ("rep", "T07 §3 estereótipo", "pelo estereótipo a implementarem,", "pelo estereótipo «a implementar»,", {}),
    ("rep", "T08 §3.3.1 artigo", "Figura 5 apresenta os usuários", "A Figura 5 apresenta os usuários", {}),
    ("rep", "T09 §3.3.1 0..1", "associação de 1 para 0.1.", "associação de 1 para 0..1.", {}),
    ("rep", "T10 §3.3.1 0..*", "associação de 1 para 0. A classe Aluno", "associação de 1 para 0..*. A classe Aluno", {}),
    ("rep", "T11 §3.3.1 Conversa", "A classe conversa representa", "A classe Conversa representa", {}),
    ("rep", "T12 §3.4.2 valida", "o sistema a válida.", "o sistema o valida.", {}),
    ("rep", "T13 §3.4.6 vê", "o destinatário a ver (a tela", "o destinatário a vê (a tela", {}),
    ("rep", "T14 título cap. 4", "DESCISÕES DE PROJETOS", "DECISÕES DE PROJETO", {"last": True}),
    ("rep", "T15 Fonte Fig. 2", "Fonte: elaborado pelo autor do projeto (2026",
     "Fonte: elaborado pelo autor do projeto (2026)", {"followed_by": "\r"}),
    ("split", "T16 título 2.2 fundido", "2.2 Framework Django",
     "2.1 Linguagem de Programação: Python 3", "A linguagem Python 3 foi escolhida"),
    ("split", "T17 título 2.3 fundido", "2.3 API REST e Autenticação JWT",
     "2.1 Linguagem de Programação: Python 3", "A linguagem Python 3 foi escolhida"),
    # renumeração da 2.4 duplicada, de trás para frente
    ("rep", "T18 2.9→2.10", "2.9 Modelagem do Banco de Dados", "2.10 Modelagem do Banco de Dados", {"last": True}),
    ("rep", "T19 2.8→2.9", "2.8 Arquitetura do Sistema", "2.9 Arquitetura do Sistema", {"last": True}),
    ("rep", "T20 2.7→2.8", "2.7 Qualidade, Teste e Versionamento", "2.8 Qualidade, Teste e Versionamento", {"last": True}),
    ("rep", "T21 2.6→2.7", "2.6 Serviços Externos", "2.7 Serviços Externos", {"last": True}),
    ("rep", "T22 2.5→2.6", "2.5 Front-end", "2.6 Front-end", {"last": True}),
    ("rep", "T23 2.4→2.5", "2.4 Controle de Versão: Git e GitHub", "2.5 Controle de Versão: Git e GitHub", {"last": True}),

    # Resumo / Abstract
    ("rep", "R01 Resumo LGPD", "entre profissionais e o registro de acessos.",
     "entre profissionais e, como etapa prevista, o registro de acessos.", {}),
    ("rep", "R02 Resumo estado",
     " e uma suíte composta por 102 testes automatizados. Como etapa final de implementação, estão previstas a recuperação de senha, a distribuição e repetição de atividades, o registro de anotações, o chat e as videochamadas.",
     ", a distribuição e a repetição de atividades com o histórico do aluno, o registro de anotações, as preferências de acessibilidade, o dashboard do profissional e uma suíte composta por 140 testes automatizados. Como etapa final de implementação, estão previstas a recuperação de senha, o registro de acessos, o chat e as videochamadas.", {}),
    ("rep", "R03 Abstract LGPD", "data isolation between professionals, and access logging.",
     "data isolation between professionals, and, as a planned step, access logging.", {}),
    ("rep", "R04 Abstract estado",
     " and a suite of 102 automated tests. The final implementation stage includes password recovery, activity assignment and repetition, note-taking, chat, and video calls.",
     " activity assignment and repetition with the student history, note-taking, accessibility preferences, a professional dashboard, and a suite of 140 automated tests. The final implementation stage includes password recovery, access logging, chat, and video calls.", {}),

    # Capítulo 2
    ("rep", "M01 §2.2 Chart.js",
     "selecionado durante o cadastro ou a atualização das mensagens do chat, é utilizado JavaScript puro.",
     "selecionado durante o cadastro ou a atualização das mensagens do chat, é utilizado JavaScript puro. Os gráficos do dashboard do profissional (RF05) utilizam a biblioteca Chart.js (CHART.JS, 2026), carregada por CDN com verificação de integridade (SRI); trata-se de uma biblioteca de gráficos, e não de um framework JavaScript.", {}),
    ("rep", "M02 §2.4 PostgreSQL",
     "a migração para o PostgreSQL ocorrerá na etapa de homologação, o que é facilitado pelo ORM, que abstrai as diferenças entre os dois bancos, e pelo fato de o driver psycopg2 já constar nas dependências do projeto.",
     "o PostgreSQL é selecionado pela variável de ambiente DB_ENGINE (com DB_NAME, DB_USER, DB_PASSWORD, DB_HOST e DB_PORT) e já é utilizado na execução da suíte de testes, o que é facilitado pelo ORM, que abstrai as diferenças entre os dois bancos, e pelo driver psycopg2, que consta nas dependências do projeto.", {}),
    ("rep", "M03 §2.5 front-end",
     "e, nas próximas etapas, a atualização das mensagens do chat, é utilizado JavaScript puro.",
     "e, nas próximas etapas, a atualização das mensagens do chat, é utilizado JavaScript puro. As preferências de acessibilidade de cada usuário (RF14) são aplicadas por classes CSS no elemento body de todas as páginas.", {}),
    ("rep", "M04 §2.6 códigos", "(boas-vindas, notificação ao responsável e códigos de verificação)",
     "(boas-vindas, notificação ao responsável e, com a recuperação de senha prevista, códigos de verificação)", {}),
    ("rep", "M05 §2.7 testes", "Atualmente, a suíte possui 102 testes automatizados,",
     "Atualmente, a suíte possui 140 testes automatizados, executados também com o PostgreSQL,", {}),
    ("rep", "M06 §2.7 CI",
     "Na data de elaboração deste documento, os testes automatizados e a análise estática são executados sem falhas.",
     "Na data de elaboração deste documento, os testes automatizados e a análise estática são executados sem falhas. Como a versão entregue está na ramificação entrega0911 e o fluxo do GitHub Actions é acionado pela ramificação main, a execução automática está suspensa; ela será restabelecida após a entrega, com o ajuste do gatilho do arquivo ci.yml para a ramificação correta.", {}),
    ("rep", "M07 §2.8 backup", "cuja rotina de backups garante a integridade das informações armazenadas.",
     "para o qual está prevista uma rotina de backups que garanta a integridade das informações armazenadas.", {}),
    ("rep", "M08 §2.9 tabelas",
     "As tabelas de usuários, perfis, atividades e registros de evolução já estão implementadas no código-fonte. A reestruturação das entidades relacionadas às atribuições e às tentativas, assim como a implementação das demais tabelas, faz parte do plano de evolução do banco de dados, conforme apresentado e justificado na Seção 4.3.",
     "As tabelas de usuários, perfis, atividades, registros de evolução, atribuições, anotações e preferências de acessibilidade já estão implementadas no código-fonte. As demais tabelas (passos_atividade, codigos_verificacao, logs_acesso, conversas, mensagens, salas_video e participacoes_sala) fazem parte do plano de evolução do banco de dados, assim como a associação dos registros de evolução à atribuição, conforme apresentado e justificado na Seção 4.3.", {}),

    # Quadro 1 (tabela 1): coluna Situação = 5, Atores = 3
    ("cell", "Q1 RF05 atores", 1, 6, 3, "Gestor", "Gestor, Profissional"),
    ("cell", "Q1 RF06", 1, 7, 5, "Parcial", "Implementado"),
    ("cell", "Q1 RF07", 1, 8, 5, "Planejado", "Implementado"),
    ("cell", "Q1 RF08", 1, 9, 5, "Parcial", "Implementado"),
    ("cell", "Q1 RF09", 1, 10, 5, "Planejado", "Implementado"),
    ("cell", "Q1 RF11", 1, 12, 5, "Planejado", "Implementado"),
    ("cell", "Q1 RF14", 1, 15, 5, "Planejado", "Implementado"),
    # RF10 fica Parcial: RN03 (LogAcesso) não existe no código.

    # §3.1 textos dos RFs
    ("rep", "F05 descrição",
     "consulte indicadores gerais e gerencie usuários, desativando-os em vez de excluí-los.",
     "consulte indicadores gerais e gerencie usuários, desativando-os em vez de excluí-los. O sistema também deverá oferecer ao profissional aprovado um dashboard com indicadores e gráficos sobre os seus alunos vinculados.", {}),
    ("cell", "F05 atores", 6, 4, 2, "Gestor", "Gestor, Profissional (dashboard)"),
    ("rep", "F05 RN05", "RN04 – Registros de evolução não podem ser apagados pelo administrador.",
     "RN04 – Registros de evolução não podem ser apagados pelo administrador.\rRN05 – O dashboard do profissional mostra apenas dados dos alunos vinculados a ele: alunos vinculados, atividades distribuídas pendentes, conclusões de atividades (cada tentativa conta) e gráficos de conclusões por semana e por aluno, também disponíveis em tabela; o aluno recebe 403.", {}),
    ("rep", "F06 descrição", "informando título, categoria, descrição e, opcionalmente, passos ordenados com texto e imagem.",
     "informando título, categoria e descrição. Os passos ordenados com texto e imagem estão previstos e ainda não foram implementados.", {}),
    ("rep", "F06 fluxo", "2. Informa título, categoria, descrição e, se desejar, os passos.",
     "2. Informa título, categoria e descrição.", {}),
    ("rep", "F06 RN04",
     "RN04 – Atividade com histórico não é apagada: é arquivada e deixa de poder ser atribuída, preservando os registros já feitos.",
     "RN04 – Atividade com histórico não é apagada: é arquivada e deixa de poder ser atribuída, preservando os registros já feitos. A atividade arquivada continua no painel do profissional, com a marca ‘Arquivada’, e permanece visível ao aluno que já a recebeu; o desarquivamento só é possível pelo administrador do Django e não há exclusão de atividades.", {}),
    ("rep", "F07 RN01", "RN01 – Só podem ser escolhidos alunos vinculados ao profissional.",
     "RN01 – Só podem ser escolhidos alunos vinculados ao profissional e com usuário ativo.", {}),
    ("rep", "F07 RN03", "RN03 – O prazo, quando informado, não pode ser anterior à data atual.",
     "RN03 – O prazo, quando informado, é uma data (sem hora) e não pode ser anterior à data atual, considerada no fuso de São Paulo; prazo igual à data atual é aceito.", {}),
    ("rep", "F07 RN04/RN05",
     "RN04 – O profissional pode cancelar uma atribuição ainda não iniciada; o cancelamento é registrado e não apaga o histórico.",
     "RN04 – O profissional pode cancelar uma atribuição ainda não iniciada; o cancelamento é registrado e não apaga o histórico (previsto; ainda não implementado).\rRN05 – Cada aluno recebe no máximo uma atribuição da mesma atividade: reenviar o formulário não cria duplicatas, e o sistema informa quantas atribuições foram criadas. Atividade de outro profissional resulta em 404.", {}),
    ("rep", "F08 descrição", "as atividades que lhe foram atribuídas e permitir",
     "as atividades disponibilizadas pelo seu profissional e permitir", {}),
    ("rep", "F08 RN06", "RN05 – Tentar concluir atividade de outro aluno ou profissional resulta em 404.",
     "RN05 – Tentar concluir atividade de outro aluno ou profissional resulta em 404.\rRN06 – Ao confirmar, o sistema marca como concluída a atribuição do aluno; se a atividade nunca foi distribuída a ele, cria a atribuição já concluída, em nome do profissional dono da atividade.", {}),
    ("rep", "F08 CA01", "CA01 – Dado um aluno com 2 atividades atribuídas, quando abrir a sua lista,",
     "CA01 – Dado um aluno cujo profissional tem 2 atividades que o aluno ainda não concluiu, quando abrir a sua lista,", {}),
    ("rep", "F09 pré-condição", "O aluno está autenticado e possui atribuição com ao menos uma tentativa concluída.",
     "O aluno está autenticado e já concluiu a atividade ao menos uma vez.", {}),
    ("rep", "F09 fluxo 3", "3. O sistema cria uma nova tentativa, com o número seguinte, em andamento.",
     "3. O sistema cria uma nova tentativa em andamento ou, se já houver uma aberta, a retoma.", {}),
    ("rep", "F09 RN02", "RN02 – O número da tentativa é sequencial dentro da atribuição.",
     "RN02 – O número da tentativa é sequencial por aluno e atividade e é calculado pela ordem das conclusões, sem campo próprio no banco.", {}),
    ("rep", "F09 RN03", "RN03 – Só pode haver uma tentativa em andamento por atribuição.",
     "RN03 – Só pode haver uma tentativa em andamento por aluno e atividade, o que é garantido por restrição no banco.", {}),
    ("rep", "F09 RN05", "RN05 – Atribuição cancelada ou atividade arquivada não pode ser refeita.",
     "RN05 – Só pode ser refeita atividade já concluída pelo aluno; a atividade arquivada continua podendo ser refeita, pois o arquivamento não afeta o que o aluno já recebeu (RF06). Não há limite para o número de repetições.", {}),
    ("rep", "F09 CA02", "quando o aluno tentar iniciar outra da mesma atribuição,",
     "quando o aluno tentar iniciar outra da mesma atividade,", {}),
    ("rep", "F09 CA04",
     "CA04 – Dado uma atividade arquivada, quando o aluno tentar refazê-la, então o sistema deverá recusar a operação.",
     "CA04 – Dado uma atividade que o aluno ainda não concluiu, quando ele tentar refazê-la, então o sistema deverá responder 404.", {}),
    ("rep", "F10 RN03", "RN03 – Cada consulta ao histórico de um aluno é registrada para auditoria (RNF05).",
     "RN03 – Cada consulta ao histórico de um aluno é registrada para auditoria (RNF05); previsto, ainda não implementado.", {}),
    ("rep", "F11 descrição", "registrem anotações textuais sobre o aluno ou sobre uma tentativa, escolhendo",
     "registrem anotações textuais sobre o aluno, escolhendo", {}),
    ("rep", "F11 fluxo 1", "1. O usuário abre o aluno ou a tentativa a que a anotação se refere.",
     "1. O usuário abre a tela de anotações do aluno (o aluno, a sua própria; o profissional, a de um aluno vinculado).", {}),
    ("rep", "F11 RN02",
     "RN02 – Anotação compartilhada é visível ao aluno e ao profissional vinculados, nunca a terceiros.",
     "RN02 – Anotação compartilhada é visível ao aluno e ao profissional vinculados, nunca a terceiros. Vale o vínculo do momento da leitura: se o aluno trocar de profissional, o novo profissional passa a ler as anotações compartilhadas anteriores.", {}),
    ("rep", "F11 CA03", "quando o usuário tentar editá-la, então o sistema deverá negar o acesso.",
     "quando o usuário tentar editá-la, então o sistema deverá responder 404.", {}),

    # Quadro 2 (RNFs)
    ("rep", "N04 limite", "bloqueio após 5 tentativas inválidas seguidas.",
     "bloqueio após 5 tentativas inválidas seguidas (previsto; ainda não implementado).", {}),
    ("rep", "N05 log", "consultas a dados de alunos registradas;",
     "registro das consultas a dados de alunos (previsto);", {}),
    ("rep", "N08 banco", "(SQLite em desenvolvimento; PostgreSQL em produção) com rotina periódica de backup;",
     "(SQLite em desenvolvimento; PostgreSQL nos testes e em produção, selecionado por DB_ENGINE) com rotina periódica de backup prevista;", {}),
    ("rep", "N08 FKs", "Restauração de um backup em ambiente de teste; chaves estrangeiras com exclusão protegida.",
     "Restauração de um backup em ambiente de teste; chaves estrangeiras do histórico (registros de evolução, atribuições e anotações) com exclusão protegida.", {}),
    ("rep", "N12 OpenAPI", "Esquema OpenAPI disponível em rota própria e coerente com as rotas existentes.",
     "Esquema OpenAPI disponível em rota própria e coerente com as rotas existentes. O drf-spectacular já está instalado e configurado; falta publicar a rota do esquema.", {}),

    # §3.3 diagramas de classe (texto)
    ("rep", "C01 §3.3.1 Fig. 6",
     "As classes Atribuição e PassoAtividade, assim como os atributos identificados com asterisco, correspondem a elementos previstos para implementação. Atualmente, RegistroEvolucao está relacionado diretamente ao aluno e à atividade, mas, conforme previsto na Seção 4.3, essa relação será alterada para que o registro esteja associado à Atribuição.",
     "A classe Atribuição e o atributo arquivada já foram implementados; a classe PassoAtividade e os demais atributos identificados com asterisco correspondem a elementos previstos para implementação. Atualmente, RegistroEvolucao está relacionado diretamente ao aluno e à atividade, e o número da tentativa é calculado pela ordem das conclusões; conforme a Seção 4.3, a associação do registro à Atribuição permanece prevista. No código, o enumerado StatusRegistro corresponde a RegistroEvolucao.Status, com os mesmos valores.", {}),
    ("rep", "C02 §3.3.1 Anotacao", "A classe Anotacao representa os registros",
     "A classe Anotacao, já implementada, representa os registros", {}),
    ("rep", "C03 §3.3.1 Anotacao-registro", "e, opcionalmente, relacionados a um RegistroEvolucao, podendo possuir",
     "e, opcionalmente, relacionados a um RegistroEvolucao (relação prevista; na implementação atual, a anotação se refere apenas ao aluno), podendo possuir", {}),
    ("rep", "C04 §3.3.1 Preferencia", "A classe PreferenciaAcessibilidade armazena",
     "A classe PreferenciaAcessibilidade, já implementada, armazena", {}),
    ("rep", "C05 §3.3.2 EmailService", "além do serviço de envio de e-mails.",
     "além do serviço de envio de e-mails, implementado como o módulo apps/usuarios/services/email.py, e não como uma classe.", {}),
    ("rep", "C06 §3.3.2 PreferenciasView", "e a PreferenciasView, ainda a implementar.",
     "e a PreferenciasView, implementada nesta etapa (RF14).", {}),
    ("rep", "C07 §3.3.2 aluno", "além das views previstas para refazer atividades, consultar o histórico e registrar anotações.",
     "além das views para refazer atividades, consultar o histórico e registrar anotações, implementadas nesta etapa (RefazerAtividadeView, HistoricoAlunoView e as telas de anotações).", {}),
    ("rep", "C08 §3.3.2 profissional",
     "Também são apresentadas as views previstas para edição, arquivamento e distribuição de atividades, além do registro de anotações.",
     "Também são apresentadas as views de edição, arquivamento e distribuição de atividades (AtividadeUpdateView, ArquivarAtividadeView e DistribuirAtividadeView) e de registro de anotações, implementadas nesta etapa; o DashboardProfissionalView (RF05), também implementado, ainda não consta nesses diagramas.", {}),
    ("rep", "C09 §3.3.2 base", "com base nos requisitos RF03, RF06, RF07, RF09, RF11, RF12, RF13 e RF14 e poderão",
     "com base nos requisitos RF03, RF06 (passos), RF10 (registro de acessos), RF12 e RF13 e poderão", {}),

    # §3.4 BPMN
    ("rep", "B01 §3.4 situação",
     "Os fluxos relacionados ao cadastro, à aprovação, à realização de atividades pelo aluno e ao acompanhamento pelo profissional representam funcionalidades já desenvolvidas no sistema. Já os processos de recuperação de senha, distribuição de atividades, chat e videochamada",
     "Os fluxos relacionados ao cadastro, à aprovação, à distribuição de atividades, à realização e repetição de atividades pelo aluno e ao acompanhamento pelo profissional representam funcionalidades já desenvolvidas no sistema, com exceção do registro de acesso no acompanhamento, ainda previsto. Já os processos de recuperação de senha, chat e videochamada", {}),
    ("after", "B02 §3.4.4 título", "Esse fluxo materializa o requisito RF07.",
     "3.4.4 Realização e Repetição de Atividade pelo Aluno", "3.4.3 Distribuição de Atividade pelo Profissional"),
    ("after", "B03 §3.4.4 texto", "3.4.4 Realização e Repetição de Atividade pelo Aluno",
     "O processo da Figura 19 começa quando o aluno abre a sua lista de atividades. Ele escolhe uma atividade, a executa e aciona ‘Concluir atividade’; o sistema pergunta ‘Você já terminou a atividade?’. Se o aluno escolher ‘Não, voltar’, nada é gravado. Se confirmar, o sistema registra a tentativa como concluída, com data e hora, e marca a atribuição como concluída. Para repetir, o aluno acessa ‘Meu histórico’ e aciona ‘Fazer de novo’: o sistema abre uma nova tentativa em andamento, ou retoma a que já estava aberta, e o aluno volta à confirmação. Esse fluxo materializa os requisitos RF08 e RF09.",
     "Esse fluxo materializa o requisito RF07."),
    ("rep", "B04 §3.4.5 acesso", "se sim, escreve o texto e o sistema a salva e registra o acesso, encerrando o processo.",
     "se sim, escreve o texto e o sistema o salva, encerrando o processo; o registro do acesso, representado no diagrama, ainda está previsto.", {}),

    # Capítulo 4
    ("after", "D01 §4.1 dashboard", "nenhuma das informações seja armazenada.",
     "Além do painel do gestor, o profissional aprovado dispõe de um dashboard próprio (RF05), acessado pelo link ‘Ver dashboard’ no painel de atividades. Ele apresenta o número de alunos vinculados, de atividades distribuídas pendentes e de conclusões de atividades, além de dois gráficos de barras, de conclusões por semana e por aluno, gerados pela biblioteca Chart.js, sem animação (RNF02). Cada gráfico possui descrição textual para leitores de tela e os mesmos dados podem ser consultados em tabela. Cada tentativa concluída conta como uma conclusão, de modo que refazer uma atividade aumenta o total. Como limitações, os gráficos dependem do carregamento da biblioteca por CDN, sem o qual apenas os números e as tabelas são exibidos, e não há filtros por categoria ou período.",
     "nenhuma das informações seja armazenada."),
    ("rep", "D02 §4.3 primeira versão", "Na versão atual do código, a atividade cadastrada",
     "Na primeira versão do código, a atividade cadastrada", {}),
    ("rep", "D03 §4.3 restrição", "Esse registro possui uma restrição que impede que",
     "Esse registro possuía uma restrição que impedia que", {}),
    ("after", "D04 §4.3 estado", "nenhum histórico será perdido.",
     "Na versão entregue, foram implementadas a Atribuição, com prazo, status e uma restrição que impede duas atribuições da mesma atividade ao mesmo aluno (RF07), e a repetição de atividades (RF09). A associação do registro de evolução à atribuição e a migração descrita acima ainda não foram aplicadas: o registro continua relacionado ao aluno e à atividade, cada tentativa é um registro próprio e o seu número é calculado pela ordem das conclusões. A restrição de uma conclusão por atividade foi substituída por outra que permite apenas uma tentativa em andamento por aluno e atividade; a proteção contra conclusão duplicada passou a ser feita na própria view, com bloqueio de linha que é efetivo no PostgreSQL. Ao concluir uma atividade, o sistema marca a atribuição correspondente como concluída ou, se a atividade nunca foi distribuída ao aluno, cria a atribuição já concluída.",
     "nenhum histórico será perdido."),
    ("rep", "D05 §4.5 anotação", "A anotação, prevista para implementação, consiste em um texto livre sobre o aluno ou sobre uma tentativa,",
     "A anotação, já implementada, consiste em um texto livre sobre o aluno,", {}),
    ("rep", "D06 §4.7 RF14",
     "Como evolução da aplicação, está prevista a possibilidade de cada usuário ajustar o tamanho da letra, o contraste e o nível de estímulos visuais (RF14), mantendo a baixa carga sensorial como configuração padrão.",
     "Foi implementada também a possibilidade de cada usuário ajustar o tamanho da letra (120% ou 140%), ativar o alto contraste e reduzir os estímulos visuais (RF14), na tela ‘Preferências’, mantendo a baixa carga sensorial como configuração padrão. As preferências são aplicadas a todas as páginas após o login, e o aumento da letra depende de navegadores atuais (RNF06).", {}),

    # Quadro 3 (tabela 17): Situação = 2, Observações = 3
    ("cell", "Q3 gestão obs", 17, 3, 3,
     "Painel com indicadores e ação em massa no Django Admin; exclusão apenas desativa.",
     "Painel com indicadores e ação em massa no Django Admin; exclusão apenas desativa. Dashboard do profissional com gráficos de conclusões (RF05)."),
    ("cell", "Q3 aluno obs", 17, 5, 3, "Confirmação em duas etapas; conclusão sem duplicidade.",
     "Confirmação em duas etapas; conclusão sem duplicidade e marcada na atribuição do aluno (RF08)."),
    ("cell", "Q3 profissional obs", 17, 6, 3, "Isolamento por vínculo (resposta 404 a dados de outro profissional).",
     "Isolamento por vínculo (resposta 404 a dados de outro profissional); edição e arquivamento de atividades (RF06); evolução com todas as tentativas e observações (RF10)."),
    ("cell", "Q3 testes obs", 17, 8, 3, "102 testes, análise estática e verificação de migrações.",
     "140 testes (validados no PostgreSQL), análise estática e verificação de migrações; a execução automática no GitHub Actions será restabelecida após a entrega."),
    ("cell", "Q3 preferências", 17, 9, 2, "Parcial", "Implementado"),
    ("cell", "Q3 preferências obs", 17, 9, 3, "CSS de baixa carga sensorial existe; faltam preferências e novas telas.",
     "Tela de preferências (tamanho da letra, alto contraste e redução de estímulos) aplicada a todas as páginas após o login (RF14)."),
    ("cell", "Q3 distribuição", 17, 11, 2, "Planejado", "Implementado"),
    ("cell", "Q3 distribuição obs", 17, 11, 3, "Exige reestruturar o banco (Atribuição e tentativas) com migração de dados.",
     "Atribuição com prazo e sem duplicidade por aluno e atividade (RF07); repetição e histórico do aluno (RF09). A associação da tentativa à atribuição segue prevista."),
    ("cell", "Q3 edição", 17, 12, 2, "Planejado", "Parcial"),
    ("cell", "Q3 edição obs", 17, 12, 3, "Hoje só é possível criar atividades pela interface.",
     "Edição e arquivamento implementados (RF06); passos das atividades ainda planejados."),
    ("cell", "Q3 anotações", 17, 13, 2, "Planejado", "Implementado"),
    ("cell", "Q3 anotações obs", 17, 13, 3, "Privados ou compartilhadas.",
     "Privadas ou compartilhadas; edição e exclusão apenas pelo autor (RF11)."),
    ("cell", "Q3 PostgreSQL", 17, 16, 2, "Planejado", "Parcial"),
    ("cell", "Q3 PostgreSQL obs", 17, 16, 3, "Driver já consta nas dependências.",
     "PostgreSQL selecionado por DB_ENGINE e usado nos testes; auditoria de acessos (LogAcesso) e rotina de backup ainda previstas."),

    # §5 e §6
    ("rep", "E01 §5 estágio",
     "O código implementado apresenta aprovação nos 102 testes automatizados, na análise estática e na verificação de migrações do banco de dados. As próximas etapas do desenvolvimento, organizadas por ordem de prioridade, são: reestruturar o banco de dados para utilizar as entidades de atribuições e tentativas, incluindo a migração dos dados existentes e a transição para o PostgreSQL; implementar a recuperação de senha por meio de código de verificação; implementar a distribuição e a repetição de atividades, bem como o histórico do aluno; implementar as anotações; ampliar o front-end e as opções de acessibilidade; implementar o chat; e, caso o prazo do projeto permita, integrar a funcionalidade de videochamada.",
     "O código implementado apresenta aprovação nos 140 testes automatizados, executados também no PostgreSQL, na análise estática e na verificação de migrações do banco de dados. Desde a versão anterior deste documento, foram implementados a distribuição de atividades com prazo, a edição e o arquivamento de atividades, a repetição de atividades com o histórico do aluno, as anotações, as preferências de acessibilidade e o dashboard do profissional. As próximas etapas do desenvolvimento, organizadas por ordem de prioridade, são: implementar a recuperação de senha por meio de código de verificação; implementar o registro de acessos aos dados dos alunos e o limite de tentativas de login; associar as tentativas às atribuições, com a migração dos dados existentes; implementar o chat; e, caso o prazo do projeto permita, implementar os passos das atividades e integrar a funcionalidade de videochamada.", {}),
    ("rep", "E02 §6 limitações",
     "a ausência das funcionalidades de recuperação de senha, distribuição e repetição de atividades, anotações, chat e videochamada,",
     "a ausência das funcionalidades de recuperação de senha, registro de acessos, chat e videochamada,", {}),

    # Referências
    ("after", "X01 ref. Chart.js", "BREVO. API reference: send a transactional email.",
     "CHART.JS. Chart.js documentation: version 4.5. [S. l.]: Chart.js, c2026. Disponível em: https://www.chartjs.org/docs/4.5.0/. Acesso em: 28 out. 2026.",
     "BREVO. API reference: send a transactional email."),
]


# ---------------------------------------------------------------- Word
def find_all(doc, text):
    """Posições de início de `text` no documento (Find aceita até 255 caracteres)."""
    head = text[:200]
    rng = doc.Content
    f = rng.Find
    f.ClearFormatting()
    hits = []
    while f.Execute(FindText=head, MatchCase=True, MatchWholeWord=False,
                    MatchWildcards=False, Forward=True, Wrap=0):
        s = rng.Start
        if doc.Range(s, s + len(text)).Text == text:
            hits.append(s)
        rng.Collapse(WD_COLLAPSE_END)
    return hits


def locate(doc, text, last=False, followed_by=None):
    hits = find_all(doc, text)
    if followed_by:
        hits = [s for s in hits if doc.Range(s + len(text), s + len(text) + 1).Text == followed_by]
    if not hits:
        raise LookupError("texto não encontrado")
    if len(hits) > 1 and not last:
        raise LookupError(f"{len(hits)} ocorrências (ambíguo)")
    return hits[-1]


def replace_at(doc, start, old, new):
    """Troca só o trecho que difere, para a marcação ficar enxuta."""
    p = 0
    while p < min(len(old), len(new)) and old[p] == new[p]:
        p += 1
    q = 0
    while q < min(len(old), len(new)) - p and old[-1 - q] == new[-1 - q]:
        q += 1
    doc.Range(start + p, start + len(old) - q).Text = new[p:len(new) - q]


def para_of(doc, anchor, last=False):
    return doc.Range(locate(doc, anchor, last), locate(doc, anchor, last)).Paragraphs(1)


def clone_format(target, ref):
    target.Style = ref.Style
    target.Format = ref.Format
    target.Range.Font = ref.Range.Characters(1).Font.Duplicate


def apply(doc, edit):
    kind = edit[0]
    if kind == "rep":
        _, _, old, new, opts = edit
        replace_at(doc, locate(doc, old, **opts), old, new)
    elif kind == "cell":
        _, _, t, r, c, old, new = edit
        cell = doc.Tables(t).Cell(r, c)
        atual = cell.Range.Text[:-2]  # tira o marcador de fim de célula
        if atual != old:
            raise LookupError(f"célula contém {atual!r}")
        replace_at(doc, cell.Range.Start, old, new)
    elif kind == "after":
        _, _, anchor, text, ref_anchor = edit
        para = para_of(doc, anchor, last=True)
        ref = para_of(doc, ref_anchor, last=True)
        para.Range.InsertParagraphAfter()
        novo = para.Next(1)
        novo.Range.InsertBefore(text)
        clone_format(novo, ref)
    elif kind == "split":
        _, _, title, title_ref, body_ref = edit
        s = locate(doc, title, last=True)
        e = s + len(title)
        if doc.Range(e, e + 1).Text != "\x0b":
            raise LookupError("título não é seguido de quebra de linha")
        hdr = para_of(doc, title_ref, last=True)
        body = para_of(doc, body_ref)
        doc.Range(e, e + 1).Text = "\r"
        p1 = doc.Range(s, s).Paragraphs(1)
        clone_format(p1, hdr)
        clone_format(p1.Next(1), body)
    else:
        raise ValueError(kind)


def desfaz_imagens_titulo(doc):
    """No original, as imagens das Figuras 20-22 estão em parágrafos 'Título 1', e o
    Sumário as copia como capítulos. Usa o formato de um parágrafo de imagem normal."""
    shapes = [doc.InlineShapes(i) for i in range(1, doc.InlineShapes.Count + 1)]
    ref = next(s.Range.Paragraphs(1) for s in shapes if s.Range.Paragraphs(1).OutlineLevel == 10)
    corrigidas = 0
    for s in shapes:
        p = s.Range.Paragraphs(1)
        if p.OutlineLevel != 10:  # 10 = corpo de texto
            clone_format(p, ref)
            corrigidas += 1
    return corrigidas


def contar(doc):
    return {"tabelas": doc.Tables.Count, "imagens_inline": doc.InlineShapes.Count,
            "formas": doc.Shapes.Count, "paragrafos": doc.Paragraphs.Count}


def main():
    if not ORIGINAL.exists():
        sys.exit(f"original não encontrado: {ORIGINAL}")
    shutil.copy2(ORIGINAL, BACKUP)
    shutil.copy2(ORIGINAL, MARCADA)

    word = win32com.client.DispatchEx("Word.Application")  # instância própria, não a do usuário
    word.Visible = False
    word.DisplayAlerts = 0
    resultado = {"edicoes": [], "contagens": {}}
    try:
        doc = word.Documents.Open(str(MARCADA), ConfirmConversions=False, ReadOnly=False,
                                  AddToRecentFiles=False, Visible=False)
        resultado["contagens"]["original"] = contar(doc)
        doc.TrackRevisions = True
        for edit in EDITS:
            try:
                apply(doc, edit)
                resultado["edicoes"].append({"id": edit[1], "status": "aplicada"})
            except Exception as exc:  # pula e registra; nada é forçado
                resultado["edicoes"].append({"id": edit[1], "status": "pulada", "motivo": str(exc)})
        resultado["imagens_com_estilo_titulo_corrigidas"] = desfaz_imagens_titulo(doc)
        resultado["revisoes"] = doc.Revisions.Count
        resultado["contagens"]["marcada"] = contar(doc)
        doc.Save()

        doc.TrackRevisions = False
        doc.Revisions.AcceptAll()
        for i in range(1, doc.TablesOfContents.Count + 1):
            doc.TablesOfContents(i).Update()
        resultado["sumarios_atualizados"] = doc.TablesOfContents.Count
        resultado["listas_figuras_campo"] = doc.TablesOfFigures.Count
        resultado["contagens"]["atualizada"] = contar(doc)
        doc.SaveAs2(str(ATUALIZADA), FileFormat=WD_FORMAT_DOCX)
        doc.Close(SaveChanges=False)
    finally:
        word.Quit()

    LOG.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    puladas = [e for e in resultado["edicoes"] if e["status"] == "pulada"]
    print(json.dumps(resultado["contagens"], ensure_ascii=False))
    print(f"aplicadas: {len(EDITS) - len(puladas)}/{len(EDITS)}; revisões: {resultado['revisoes']}")
    for e in puladas:
        print(f"PULADA {e['id']}: {e['motivo']}")


if __name__ == "__main__":
    main()
