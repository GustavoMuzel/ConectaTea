"""Teste de carga do ConectaTEA (RNF03) com o Locust.

Simula pessoas usando o sistema ao mesmo tempo com as contas de demonstração (comando popular_demo):
alunos abrindo atividades e PDFs, profissionais acompanhando alunos e salas e o gestor consultando a auditoria.
Só faz leituras: não conclui atividades nem altera dados (os acessos e a evolução consultada entram na
auditoria, como no uso real, e saem junto com o popular_demo --apagar).

Uso (veja docs/desempenho.md):
    SENHA_DEMO=<senha das contas de demonstração>
    locust -f desempenho/locustfile.py --host https://conectatea-j0az.onrender.com
e abra http://localhost:8089 para escolher o número de usuários.
"""

import os
import random
import re

import urllib3
from locust import HttpUser, between, task
from locust.exception import StopUser

SENHA = os.environ.get('SENHA_DEMO', '')
VERIFICAR_CERTIFICADO = os.environ.get('VERIFICAR_CERTIFICADO', '1') != '0'
if not VERIFICAR_CERTIFICADO:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ALUNOS = ['pedro', 'ana', 'lucas', 'beatriz', 'gabriel', 'sofia', 'mateus']
PROFISSIONAIS = ['mariana', 'camila', 'juliana']

RE_CSRF = re.compile(r'name="csrfmiddlewaretoken" value="([^"]+)"')
RE_CONFIRMAR = re.compile(r'/aluno/atividades/(\d+)/confirmar/')
RE_MATERIAL = re.compile(r'/painel/atividades/(\d+)/material/')
RE_EVOLUCAO = re.compile(r'/painel/alunos/(\d+)/"')
RE_SALA = re.compile(r'/salas/(\d+)/"')


class UsuarioConectaTEA(HttpUser):
    abstract = True
    wait_time = between(3, 8)  # tempo de leitura entre um clique e outro
    contas = []

    def on_start(self):
        if not SENHA:
            raise StopUser('Defina a variável SENHA_DEMO com a senha das contas de demonstração.')
        # Certificado próprio no teste local; no site publicado, a verificação fica ligada.
        self.client.verify = VERIFICAR_CERTIFICADO
        email = f'{random.choice(self.contas)}@example.com'
        pagina = self.client.get('/entrar/', name='entrar (abrir)')
        token = RE_CSRF.search(pagina.text)
        with self.client.post('/entrar/', name='entrar (enviar)', catch_response=True,
                              data={'username': email, 'password': SENHA,
                                    'csrfmiddlewaretoken': token.group(1) if token else ''},
                              headers={'Referer': self.host.rstrip('/') + '/entrar/'}) as resposta:
            if resposta.url.rstrip('/').endswith('/entrar'):
                resposta.failure(f'login recusado para {email}')
                raise StopUser()

    def abrir(self, caminho, nome=None):
        return self.client.get(caminho, name=nome or caminho)


class Aluno(UsuarioConectaTEA):
    weight = 6
    contas = ALUNOS

    @task(3)
    def inicio(self):
        self.abrir('/aluno/')

    @task(3)
    def fazer_atividade(self):
        lista = self.abrir('/aluno/atividades/')
        ids = RE_CONFIRMAR.findall(lista.text)
        if not ids:
            return
        pagina = self.abrir(f'/aluno/atividades/{random.choice(ids)}/confirmar/', '/aluno/atividades/[id]/confirmar/')
        material = RE_MATERIAL.search(pagina.text)
        if material:
            self.abrir(material.group(0), '/painel/atividades/[id]/material/ (PDF)')

    @task(1)
    def historico(self):
        self.abrir('/aluno/historico/')

    @task(1)
    def minha_equipe(self):
        self.abrir('/salas/minha-equipe/')

    @task(1)
    def anotacoes(self):
        self.abrir('/aluno/anotacoes/')


class Profissional(UsuarioConectaTEA):
    weight = 3
    contas = PROFISSIONAIS

    @task(3)
    def acompanhar_aluno(self):
        lista = self.abrir('/painel/alunos/')
        ids = RE_EVOLUCAO.findall(lista.text)
        if ids:
            self.abrir(f'/painel/alunos/{random.choice(ids)}/', '/painel/alunos/[id]/ (evolução)')

    @task(2)
    def sala(self):
        lista = self.abrir('/salas/')
        ids = RE_SALA.findall(lista.text)
        if ids:
            self.abrir(f'/salas/{random.choice(ids)}/', '/salas/[id]/')

    @task(1)
    def biblioteca(self):
        self.abrir('/painel/')

    @task(1)
    def relatorios(self):
        self.abrir('/aluno/dashboard-profissional/')


class Gestor(UsuarioConectaTEA):
    weight = 1
    contas = ['coordenacao']

    @task(2)
    def painel(self):
        self.abrir('/painel-gestao/')

    @task(1)
    def auditoria(self):
        self.abrir('/painel-gestao/auditoria/')
