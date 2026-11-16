# Teste de desempenho (RNF03)

**Requisito (Quadro 2 da monografia):** RNF03, Desempenho. Critério: *tempo de resposta das páginas principais
de até 2 segundos em rede doméstica (meta do projeto)*.

O teste foi feito em três partes, todas com os dados do comando `popular_demo` (9 alunos, 5 profissionais,
6 semanas de histórico):

1. **Consultas ao banco por página**: quantas consultas cada tela faz e se esse número cresce com os dados.
2. **Teste de carga** (Locust): várias pessoas usando o sistema ao mesmo tempo.
3. **Carregamento no navegador** (Playwright + Chromium): tempo até a página terminar de carregar, com CSS,
   fontes e scripts, numa rede limitada como a de uma casa.

## Ambiente (15/11/2026)

O servidor de teste reproduziu a configuração do Render: o mesmo código da branch `entrega-16-11`, com
`PRODUCAO=True` e `DEBUG=False`, gunicorn com 2 workers e timeout de 60 s, WhiteNoise servindo os arquivos
estáticos comprimidos, HTTPS e PDFs guardados no banco (`ARMAZENAMENTO_ARQUIVOS=banco`).

- **Servidor de teste:** máquina Linux com 4 processadores, Python 3.13, Django 6.1.1, gunicorn 26.2.0 e
  PostgreSQL 16 na mesma máquina.
- **Ferramentas:** Locust 2.47.0, Playwright 1.65.2 e Chromium (versões fixadas em `requirements-desempenho.txt`).

## 1. Consultas ao banco por página

A comparação é entre quem tem mais dados e quem tem menos: a Mariana (4 alunos) com a Juliana (1 aluno), e o
Pedro (histórico mais longo) com o Mateus. A tabela mostra a segunda visita a cada tela.

| Perfil | Tela | Consultas (mais dados / menos dados) |
|---|---|---|
| Profissional | Minhas atividades (biblioteca) | 6 / 6 |
| Profissional | Meus alunos | 8 / 8 |
| Profissional | Vincular alunos | 7 / 7 |
| Profissional | Salas | 7 / 7 |
| Profissional | Sala do aluno | 12 / 12 |
| Profissional | Evolução do aluno | 9 / 9 |
| Profissional | Relatórios | 9 / 9 |
| Profissional | Distribuir atividade | 9 / 9 |
| Aluno | Início | 9 / 9 |
| Aluno | Minhas atividades | 6 / 6 |
| Aluno | Meu histórico | 6 / 6 |
| Aluno | Anotações | 7 / 7 |
| Aluno | Minha equipe | 9 / 9 |
| Gestor | Painel de Gestão | 11 |
| Gestor | Auditoria | 7 |
| Visitante | Capa, Entrar, Sobre o TEA | 0 |

**Resultado:** nenhuma tela faz uma consulta por aluno ou por atividade (o problema conhecido como "N+1"). O
número de consultas é o mesmo com mais ou menos dados. Portanto, o tempo das telas não cresce conforme o
sistema recebe mais alunos e atividades. O teste automático `apps/acompanhamento/test_desempenho.py` confere
isso a cada mudança no código, inclusive na CI do GitHub, com limite de 15 consultas por tela.

## 2. Teste de carga

O roteiro está em `desempenho/locustfile.py`. Cada pessoa simulada entra com uma conta de demonstração e navega
como no uso real, esperando de 3 a 8 segundos entre um clique e outro (tempo de leitura). A proporção é de 6
alunos para 3 profissionais e 1 gestor:

- **Aluno:** abre o Início, a lista de atividades e uma atividade com o PDF, o histórico, a equipe e as anotações.
- **Profissional:** abre a lista de alunos e a evolução de um aluno, as salas e uma sala, a biblioteca e os
  relatórios.
- **Gestor:** abre o Painel de Gestão e a Auditoria.

O teste só lê dados: não conclui atividades nem altera nada. Cada cenário durou 2 minutos, com 5 pessoas
entrando por segundo até completar o total.

| Pessoas ao mesmo tempo | Acessos | Acessos por segundo | Falhas | Páginas: mediana | Páginas: pior p95 | Login: mediana / p95 |
|---:|---:|---:|---:|---:|---:|---:|
| 10 | 365 | 3,1 | 0 | 27 ms | 95 ms | 680 / 790 ms |
| 25 | 872 | 7,3 | 0 | 27 ms | 120 ms | 660 / 780 ms |
| 50 | 1.684 | 14,2 | 0 | 27 ms | 130 ms | 770 / 990 ms |
| 100 | 3.195 | 26,8 | 0 | 29 ms | 490 ms | 830 / 1.900 ms |

Como ler a tabela:
- **p95** é o tempo dentro do qual ficaram 95% dos acessos.
- **Páginas: pior p95** é o maior p95 entre todas as páginas do cenário.
- **Login** é o envio do formulário de entrada.

**Resultados:**
- **Nenhuma falha em 6.116 acessos.** Com até 50 pessoas ao mesmo tempo, 95% dos acessos a qualquer página
  ficaram abaixo de 0,13 s. Com 100 pessoas, abaixo de 0,49 s, e nenhuma página passou de 0,87 s.
- **O login é a operação mais lenta, de propósito.** A senha é conferida com PBKDF2-SHA256 em 1,5 milhão de
  repetições, o padrão do Django 6.1. Isso custa cerca de 0,25 s de processador por login e serve para dificultar
  a descoberta de senhas por força bruta (RNF04).
- **Por que o tempo sobe com 100 pessoas.** Enquanto muitas pessoas entram ao mesmo tempo, os 2 workers ficam
  ocupados conferindo senhas, e as outras páginas esperam na fila. O gráfico do relatório mostra que isso
  acontece só nos primeiros 30 segundos, enquanto as pessoas estão entrando. Depois, o p95 volta a ficar abaixo
  de 0,1 s. Mesmo nesse pico, todas as páginas ficaram abaixo de 2 s. O login teve p95 de 1,9 s, e o pior login
  chegou a 2,05 s.

As tabelas completas de cada cenário estão em `docs/evidencias/desempenho/`.

## 3. Carregamento no navegador

O script `desempenho/tempo_carregamento.py` abre cada página no Chromium com a rede limitada. Ele mede, pelo
próprio navegador (Navigation Timing), o tempo até o evento `load`: o HTML, o CSS, as fontes e os scripts
completamente carregados. Foram usados dois perfis de rede:

- **Doméstica:** 10 Mbit/s e 150 ms de latência, que representa uma banda larga simples acessando um servidor
  nos EUA.
- **4G lenta:** 1,6 Mbit/s e 150 ms de latência, o perfil "Slow 4G" do Lighthouse. É mais exigente do que o
  RNF03 pede.

| Perfil | Página | Rede doméstica | 4G lenta |
|---|---|---:|---:|
| Visitante | Capa | 615 ms | 830 ms |
| Visitante | Entrar | 554 ms | 832 ms |
| Visitante | Sobre o TEA | 556 ms | 831 ms |
| Aluno | Início | 551 ms | 827 ms |
| Aluno | Minhas atividades | 758 ms | 826 ms |
| Aluno | Meu histórico | 550 ms | 821 ms |
| Aluno | Minha equipe | 554 ms | 1.177 ms |
| Profissional | Minhas atividades | 586 ms | 858 ms |
| Profissional | Meus alunos | 555 ms | 808 ms |
| Profissional | Salas | 550 ms | 828 ms |
| Profissional | Relatórios (com gráficos) | 839 ms | 1.405 ms |
| Gestor | Painel de Gestão | 661 ms | 1.394 ms |
| Gestor | Auditoria | 546 ms | 875 ms |

Cada valor é o maior entre a primeira visita e a mediana de 3 visitas seguintes.

**Resultado:** todas as páginas principais carregaram em menos de 2 s. Na rede doméstica, o pior caso foi
**0,84 s**; na 4G lenta, **1,4 s**. As páginas mais pesadas são as que têm gráficos (Relatórios e Painel de
Gestão), por causa da biblioteca Chart.js, que só é carregada nelas.

## Conclusão

No ambiente de teste, o **RNF03 foi atendido**:
- as páginas principais carregam no navegador em menos de 1 s numa rede doméstica simulada e em menos de 1,5 s
  numa 4G lenta;
- o servidor respondeu sem falhas a até 100 pessoas usando o sistema ao mesmo tempo;
- o número de consultas ao banco por tela é pequeno (de 6 a 12) e não cresce com os dados.

## Limitações do teste

- **O servidor de teste é mais forte que o plano gratuito do Render.** A máquina de teste tem 4 processadores, e
  o plano gratuito do Render, 0,1 processador.
  - As páginas gastam pouco processador (cerca de 30 ms), então devem continuar bem abaixo de 2 s.
  - O login, que gasta cerca de 0,25 s de processador, **pode levar alguns segundos no Render**. Por isso, o
    teste deve ser repetido no site publicado (próxima seção). Se o login passar de 2 s lá, uma opção é usar as
    600 mil repetições recomendadas pela OWASP, menos que o padrão do Django: o login fica cerca de 2,5 vezes
    mais rápido e continua dentro da recomendação de segurança.
- **O banco ficou na mesma máquina.** No site, o Render e o Neon ficam na mesma região (Virgínia, EUA): cada
  consulta soma cerca de 1 a 2 ms, ou seja, até uns 25 ms por página.
- **O Locust rodou na mesma máquina que o servidor**, disputando o processador com ele.
- **Sem acesso à internet, o Bootstrap e o Chart.js foram servidos por cópias locais** das mesmas versões, com o
  atraso que a rede simulada teria no download comprimido. Nesse modo, o navegador não usa cache, então as
  visitas seguintes também baixaram tudo de novo: os números são conservadores.

## Como repetir no site publicado (do seu computador)

Na pasta do projeto, com o `.venv` ativado:

```powershell
pip install -r requirements-desempenho.txt
playwright install chromium
```

### Teste de carga com o Locust

Use **poucos usuários** (10 a 20): o site é do plano gratuito e o objetivo é medir, não derrubar o site. Abra o
site antes, para ele "acordar".

```powershell
$env:SENHA_DEMO = Read-Host "Senha das contas de demonstracao"
locust -f desempenho/locustfile.py --host https://conectatea-j0az.onrender.com
```

1. Abra http://localhost:8089 no navegador.
2. Preencha *Number of users* = 10 e *Ramp up* = 1, e clique em *Start*.
3. Depois de 2 minutos, clique em *Stop*. A aba *Statistics* mostra os tempos por página, e *Download Data*
   baixa o relatório em HTML.

### Carregamento no navegador

```powershell
python desempenho/tempo_carregamento.py --url https://conectatea-j0az.onrender.com --senha (Read-Host "Senha")
```

Na sua casa, a rede já é "doméstica" de verdade. Para medir sem a limitação simulada, use `--rede sem-limite`.

Outra opção, sem instalar nada: no Chrome, abra a página, aperte F12 > aba **Lighthouse** > **Analyze page
load**. Isso funciona nas páginas públicas (capa, Entrar, Sobre o TEA) e, estando logado, nas internas.

Os acessos do teste entram na auditoria, como no uso real, e são apagados junto com os dados de demonstração
pelo `popular_demo --apagar`.
