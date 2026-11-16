# Instruções de execução e evidências (acompanhamento de 16/11/2026)

> Nenhuma senha, token ou dado pessoal real aparece neste documento, no repositório ou nos prints.
>
> - As contas de demonstração são fictícias, com e-mails do domínio reservado `example.com`.
> - Os IPs mostrados na auditoria são endereços reservados para documentação (203.0.113.x e 198.51.100.x) ou o
>   do próprio computador (127.0.0.1).
> - A senha das contas de demonstração é enviada ao orientador em mensagem privada.

## 1. Sistema publicado

| Item | Endereço |
|---|---|
| Sistema | https://conectatea-j0az.onrender.com |
| Documentação da API (OpenAPI) | https://conectatea-j0az.onrender.com/api/docs/ |
| Verificação do serviço | https://conectatea-j0az.onrender.com/api/saude/ |

O plano gratuito do Render desliga a aplicação depois de 15 minutos sem acesso. O primeiro acesso depois disso
leva cerca de 1 minuto, e uma tela do próprio Render ("Service waking up") aparece enquanto isso.

### Contas de demonstração

Todas foram criadas pelo comando `python manage.py popular_demo`, com dados fictícios e 6 semanas de histórico.

| Perfil | E-mail | O que dá para ver |
|---|---|---|
| Gestor | `coordenacao@example.com` | Painel de Gestão: aprovação com conferência do conselho, revogação, auditoria com IP |
| Profissional (psicóloga) | `mariana@example.com` | 4 alunos, pedidos de ajuda, salas com equipe, videochamadas, relatórios |
| Profissional (fono) | `camila@example.com` | 2 alunos e uma atividade proposta na sala do Pedro, esperando análise |
| Profissional (TO) | `rafael@example.com` | Membro das salas do Pedro e do Gabriel |
| Profissional (pedagoga) | `juliana@example.com` | Pedido de entrada na sala da Ana, esperando o dono |
| Profissional pendente | `bruno@example.com` | Conta esperando aprovação (CRP-PR 08/98765) |
| Aluno | `pedro@example.com` | Tela inicial com alertas, atividade atrasada, videochamada marcada |
| Aluno | `ana@example.com` | Pedido de ajuda aberto |
| Aluno | `lucas@example.com` | Preferência de letra grande ativada |
| Aluno sem vínculo | `helena@example.com` | Pedido de vínculo da Mariana, esperando o aceite |

## 2. Executar no computador

Pré-requisitos: Python 3.13 e Git. Comandos para o PowerShell (Windows); no Linux ou no macOS, troque
`.venv\Scripts\activate` por `source .venv/bin/activate` e `copy` por `cp`.

```powershell
git clone -b entrega-16-11 https://github.com/GustavoMuzel/ConectaTea.git
cd ConectaTea
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

No arquivo `.env`, troque o valor de `SECRET_KEY` pelo resultado deste comando:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Depois, crie o banco (SQLite, sem instalar nada), os dados de demonstração e suba o servidor:

```powershell
python manage.py migrate
python manage.py popular_demo --senha "escolha-uma-senha"
python manage.py runserver
```

O sistema abre em http://127.0.0.1:8000. Sem a chave do Brevo no `.env`, os e-mails não são enviados, e o código de
recuperação de senha aparece no terminal. Para usar o PostgreSQL, veja os comentários do `.env.example`.

## 3. Testes, cobertura e qualidade

```powershell
pytest -m unit          # 113 testes unitários (regras de negócio, sem banco e sem rede)
pytest                  # todos os 413 testes
flake8                  # análise estática
pip install coverage==7.17.3
coverage run -m pytest -m unit; coverage report    # cobertura dos testes unitários
coverage run -m pytest; coverage report            # cobertura de todos os testes
```

| Verificação | Resultado (15/11/2026) |
|---|---|
| Testes automatizados | 413 passando: 113 unitários e 300 de integração |
| Cobertura dos testes unitários | 52% (mínimo do plano de ensino: 50%; a CI falha abaixo disso) |
| Cobertura de todos os testes | 97% |
| flake8 | Sem avisos |
| CI (GitHub Actions) | 3 checagens verdes: testes unitários com cobertura, integração em PostgreSQL 16, linter |

A CI roda a cada push e a cada pull request para a `main`. A execução da versão apresentada aparece na aba
**Actions** do repositório e no pull request #4 ("Entrega 16 11").

## 4. Roteiro de verificação das funcionalidades

Em cada linha estão o requisito da monografia, como ver o comportamento no sistema e o teste que o garante.

| Requisito | Como verificar no sistema | Teste automatizado |
|---|---|---|
| RF01 Cadastro | Em `/cadastro/`, marque Aluno e digite um celular com 10 números: o cadastro é recusado. Marque Profissional e escolha Psicologia: são pedidos o estado e o número do CRP | `usuarios/test_cadastro_campos.py`, `usuarios/test_conselho.py` |
| RF02 Login e bloqueio | Erre 5 vezes a senha de uma conta: o login fica bloqueado por 15 minutos. O botão "Mostrar" mostra a senha digitada | `usuarios/test_limites.py`, `usuarios/test_auth.py` |
| RF03 Recuperar a senha | "Esqueci minha senha": chega um código de 6 números por e-mail, válido por 10 minutos | `usuarios/test_unitario.py` (`test_codigo_*`), `usuarios/test_acesso.py` |
| RF04 Acesso por perfil | Como aluno, abra `/painel/`: acesso negado (403). Como Juliana, "Meus alunos" mostra só o Mateus; o endereço da evolução de um aluno de outro profissional responde 404 | `usuarios/test_acesso.py`, `atividades/test_painel.py` |
| RF05 Aprovação e revogação | Como `coordenacao`, no Painel de Gestão: "Consultar no site do CRP" e "Conferi e aprovo" no Bruno. "Revogar" corta o acesso na hora | `usuarios/test_conselho.py`, `usuarios/test_painel_gestao.py` |
| RF06 Atividades | Como Mariana, crie uma atividade com PDF e outra com link do Google Forms. Um link que não é do Forms é recusado | `atividades/test_material.py`, `atividades/test_rf06.py` |
| RF07 Distribuição individual | Como Mariana, distribua uma atividade só para o Pedro. Como Ana, ela não aparece | `acompanhamento/test_aluno.py` (`test_atividade_distribuida_so_para_um_aluno_nao_aparece_para_o_colega`), `acompanhamento/test_distribuir.py` |
| RF08 Realizar | Como Pedro: o Início mostra os alertas. Tente concluir sem abrir o PDF (recusado), abra o PDF, escreva a resposta e conclua | `acompanhamento/test_aluno.py`, `acompanhamento/test_painel_aluno.py` |
| RF09 Refazer e histórico | Como Pedro, em "Meu histórico", use "Fazer de novo" | `acompanhamento/test_rf09.py` |
| RF10 Evolução | Como Mariana, em "Meus alunos" > "Ver evolução": respostas do aluno e campo de correção | `atividades/test_evolucao.py`, `atividades/test_rf10.py` |
| RF11 Anotações | Como Pedro, em "Anotações", veja a anotação compartilhada da Mariana | `acompanhamento/test_rf11.py` |
| RF12 Pedir ajuda | Como Pedro, numa atividade, use "Preciso de ajuda". Como Mariana, o pedido aparece em "Meus alunos", com contador no menu | `acompanhamento/test_ajuda_e_avisos.py` |
| RF13 Videochamada | Como Mariana, na sala do Pedro, marque a chamada. Como Pedro, responda "Vou participar"; o botão de entrar aparece 15 minutos antes. A sala mostra o histórico com entrada, saída e duração | `salas/test_salas.py` (`test_aluno_so_entra_na_chamada_no_horario_marcado`, `test_entrada_e_saida_vem_dos_eventos_do_jitsi`, `test_revogar_aprovacao_do_dono_bloqueia_a_videochamada`) |
| RF14 Preferências | Em "Preferências", ative letra grande e alto contraste. O Lucas já usa letra grande | `usuarios/test_rf14.py` |
| RF15 Vínculo com aceite | Como Helena, aceite o pedido da Mariana: a sala é criada | `salas/test_vinculo.py` |
| RF16 Sala e equipe | Como Mariana, aprove a Juliana na sala da Ana e analise a atividade que a Camila propôs na sala do Pedro | `salas/test_salas.py` |
| RNF05 e RNF11 Auditoria | Como `coordenacao`, em Painel de Gestão > Auditoria: filtros por tipo, pessoa, aluno e período, IP e exportação em CSV | `usuarios/test_auditoria.py` |
| RNF03 Desempenho | Método e resultados em [desempenho.md](desempenho.md) | `acompanhamento/test_desempenho.py` |

## 5. Integrações

| Integração | Para que serve | Como verificar |
|---|---|---|
| Brevo (API REST de e-mail) | Recuperação de senha, avisos ao responsável e ao profissional | "Esqueci minha senha" com um e-mail seu, ou Painel de Gestão > "Enviar e-mail de teste". As contas `@example.com` não recebem e-mail |
| Jitsi Meet (IFrame API) | Videochamada dentro do sistema, com eventos de entrada e saída | Entrar na chamada da sala; o histórico registra os horários |
| Google Forms | Material da atividade | Criar uma atividade com link `https://forms.gle/...` |
| Render e Neon | Hospedagem da aplicação e do banco PostgreSQL | Site publicado; passo a passo em [deploy.md](deploy.md) |
| API REST própria (JWT) | Login por token, atividades do aluno, alunos do profissional | Em `/api/docs/`, use `POST /api/auth/login/` com `email` e `password` e depois "Authorize" com o token |

## 6. Evidências

- **Prints do sistema** (dados fictícios), em `docs/evidencias/telas/`:
  1. `01-aluno-inicio-com-alertas.png`: tela inicial do aluno, com atividade atrasada e videochamada marcada.
  2. `02-profissional-meus-alunos-e-pedidos-de-ajuda.png`: pedidos de ajuda e lista de alunos.
  3. `03-sala-videochamada-marcada-e-historico.png`: sala com chamada marcada, senha, pedido de entrada e
     histórico das chamadas.
  4. `04-gestao-conselho-aprovacao-e-revogacao.png`: registro no conselho, "Conferi e aprovo" e "Revogar".
  5. `05-gestao-auditoria-com-ip.png`: auditoria de todas as ações, com IP.
  6. `06-login-botao-mostrar-senha.png` e `07-cadastro-celular-11-numeros.png`: ajustes do formulário.
- **Desempenho**: [desempenho.md](desempenho.md), com as tabelas em `docs/evidencias/desempenho/`.
- **Testes e CI**: aba Actions do repositório e pull request #4.
