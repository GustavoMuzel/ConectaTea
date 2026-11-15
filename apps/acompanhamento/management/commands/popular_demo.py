"""Cria um cenário de demonstração do ConectaTEA "em uso" para a apresentação: perfis, atividades com PDF,
6 semanas de histórico, salas com equipe, videochamadas e auditoria.

Todos os dados são fictícios. Os e-mails usam o domínio reservado example.com (RFC 2606) e nenhum e-mail é
enviado. Uso:
    python manage.py popular_demo            # cria (se ainda não existir)
    python manage.py popular_demo --apagar   # remove só os dados de demonstração
"""

import os
import random
import textwrap
from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from apps.acompanhamento.models import Anotacao, Atribuicao, LogAcesso, PedidoAjuda, RegistroEvolucao
from apps.atividades.models import Atividade
from apps.salas.models import MembroSala, ParticipacaoVideochamada, Sala, SolicitacaoVinculo
from apps.usuarios.models import Aluno, PreferenciaAcessibilidade, Profissional, User

DOMINIO = 'example.com'
SENHA_PADRAO = 'Demo-ConectaTEA-2026'
Cat = LogAcesso.Categoria

GESTOR = ('coordenacao', 'Coordenação Pedagógica')
PROFISSIONAIS = [
    # chave, nome, profissão, UF, número do registro, área de atuação, aprovado
    ('mariana', 'Dra. Mariana Albuquerque', 'psicologia', 'SP', '06/154321', 'ABA', True),
    ('rafael', 'Rafael Nogueira', 'terapia_ocupacional', 'MG', '12345-TO', 'Integração sensorial', True),
    ('camila', 'Camila Duarte', 'fonoaudiologia', 'RJ', '1-23456', 'Comunicação alternativa', True),
    ('juliana', 'Juliana Ramos', 'pedagogia', '', '', 'Alfabetização', True),
    ('bruno', 'Bruno Teixeira', 'psicologia', 'PR', '08/98765', 'Habilidades sociais', False),  # espera aprovação
]
ALUNOS = [
    # chave, nome, profissional responsável (None = sem vínculo), nascimento, responsável
    ('pedro', 'Pedro Henrique Lima', 'mariana', date(2011, 3, 14), 'Cláudia Lima'),
    ('ana', 'Ana Clara Souza', 'mariana', date(2012, 7, 2), 'Roberto Souza'),
    ('lucas', 'Lucas Martins', 'mariana', date(2010, 11, 20), 'Fernanda Martins'),
    ('beatriz', 'Beatriz Oliveira', 'mariana', date(2013, 1, 9), 'Paulo Oliveira'),
    ('gabriel', 'Gabriel Costa', 'camila', date(2012, 5, 30), 'Renata Costa'),
    ('sofia', 'Sofia Almeida', 'camila', date(2011, 9, 17), 'Marcos Almeida'),
    ('mateus', 'Mateus Pereira', 'juliana', date(2013, 4, 4), 'Juliana Pereira'),
    ('helena', 'Helena Rocha', None, date(2012, 8, 25), 'Sérgio Rocha'),      # pedido de vínculo esperando aceite
    ('davi', 'Davi Fernandes', None, date(2011, 12, 3), 'Luciana Fernandes'),  # acabou de criar a conta
]
# Por profissional: as primeiras já foram feitas nas semanas anteriores; as últimas (ABERTAS) estão em aberto.
ATIVIDADES = {
    'mariana': [
        ('Reconhecer emoções em rostos', 'emoções',
         'Olhe as quatro carinhas do PDF. Escreva qual emoção cada uma mostra e como você percebeu.',
         ['Olhe cada rosto com calma.', '1. Boca para cima e olhos fechadinhos.',
          '2. Sobrancelhas para baixo e boca apertada.', '3. Lágrimas descendo.',
          '4. Boca aberta e olhos bem abertos.', 'Qual emoção cada rosto mostra?']),
        ('Como cumprimentar um colega', 'habilidades sociais',
         'Leia os três passos e conte como foi cumprimentar alguém hoje.',
         ['Passo 1: olhe para a pessoa (pode ser para o rosto ou para o ombro).',
          'Passo 2: diga "oi" ou "bom dia" e o nome da pessoa.', 'Passo 3: espere a resposta.',
          'Tente com um colega da escola hoje.']),
        ('Respirar fundo quando fico nervoso', 'autorregulação',
         'Faça a respiração do quadrado três vezes e escreva como você se sentiu depois.',
         ['Puxe o ar contando até 4.', 'Segure contando até 4.', 'Solte o ar contando até 4.',
          'Espere contando até 4.', 'Repita três vezes.']),
        ('Combinar uma mudança na rotina', 'rotina',
         'Pense em uma mudança que aconteceu nesta semana e escreva o que ajudou você.',
         ['Às vezes a rotina muda: a aula troca de sala ou o ônibus atrasa.',
          'O que ajuda: saber antes, ver no quadro de rotina, perguntar a um adulto.',
          'Escreva uma mudança desta semana e o que ajudou.']),
        ('Esperar a minha vez', 'habilidades sociais',
         'Veja as situações do PDF e escreva o que você pode fazer enquanto espera.',
         ['Situação 1: fila do lanche.', 'Situação 2: o professor está falando com outro aluno.',
          'Situação 3: um jogo com os colegas.', 'Ideias: contar até 10, respirar devagar, olhar a fila.']),
        ('Iniciar uma conversa sobre um assunto de interesse', 'comunicação',
         'Escolha um assunto de que você gosta e escreva duas perguntas para começar uma conversa.',
         ['Exemplo: "Você gosta de dinossauros? Qual é o seu preferido?"',
          'Escreva duas perguntas sobre um assunto de que você gosta.']),
    ],
    'camila': [
        ('Pedir ajuda na escola', 'comunicação',
         'Treine as frases do PDF e escreva qual delas você usaria com o professor.',
         ['Frases para pedir ajuda:', '"Professor, eu não entendi. Pode explicar de novo?"',
          '"Pode me mostrar um exemplo?"', '"Eu preciso de mais tempo."']),
        ('Contar como foi o meu fim de semana', 'comunicação',
         'Responda às três perguntas do PDF sobre o seu fim de semana.',
         ['1. Onde você estava?', '2. Com quem você estava?', '3. O que você mais gostou de fazer?']),
        ('Entender expressões com duplo sentido', 'linguagem',
         'Leia as expressões e escreva o que elas querem dizer de verdade.',
         ['1. "Estou morrendo de fome."', '2. "Caiu a ficha."', '3. "Ele tem a cabeça nas nuvens."',
          'O que cada frase quer dizer de verdade?']),
    ],
    'juliana': [
        ('Minha rotina da manhã', 'rotina',
         'Coloque em ordem os passos da sua manhã e escreva qual é o mais difícil para você.',
         ['Acordar, ir ao banheiro, escovar os dentes, trocar de roupa, tomar café e ir para a escola.',
          'Qual passo é o mais difícil? O que ajuda?']),
        ('Organizar o material da mochila', 'organização',
         'Use a lista do PDF para arrumar a mochila e escreva o que faltou.',
         ['Lista: caderno, estojo, livro do dia, garrafa de água, agenda.',
          'Confira cada item antes de sair de casa.']),
        ('O que fazer quando o barulho incomoda', 'autorregulação',
         'Escreva duas coisas que ajudam você quando o barulho fica muito alto.',
         ['Ideias: usar o abafador de ruído, pedir para ir a um lugar calmo, respirar devagar.',
          'Combine um sinal com o professor para avisar que está difícil.']),
    ],
}
ABERTAS = {'mariana': 2, 'camila': 1, 'juliana': 1}
NAO_FEZ = {('beatriz', 'Respirar fundo quando fico nervoso')}  # ficou atrasada
RESPOSTAS = [
    'Fiz com calma. A primeira foi fácil, a última eu precisei olhar de novo.',
    'Eu tentei hoje no intervalo. Foi um pouco difícil, mas a pessoa respondeu.',
    'Gostei dessa atividade. Escrevi as respostas no caderno também.',
    'Entendi quase tudo. A parte 3 eu fiquei com dúvida.',
    'Usei a ideia de contar até 10 e funcionou na fila.',
    'Minhas perguntas foram sobre trens e sobre jogos de computador.',
    'Fiz com a minha mãe. Demorei, mas terminei.',
]
CORRECOES = [
    'Muito bem! Você percebeu os detalhes. Vamos treinar mais um pouco na próxima semana.',
    'Ótimo começo. Na próxima vez, tente também perguntar o nome do colega.',
    'Boa resposta. Você usou a estratégia certa na hora certa.',
    'Parabéns pelo esforço! Vamos conversar sobre a parte 3 na videochamada.',
]
IPS = ['203.0.113.10', '203.0.113.24', '198.51.100.7', '198.51.100.31', '203.0.113.55']  # faixas de documentação


def email(chave):
    return f'{chave}@{DOMINIO}'


def pdf_de_texto(titulo, linhas):
    """PDF de uma página, só com texto (Helvetica, WinAnsi para os acentos), sem bibliotecas externas."""
    def esc(texto):
        return texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
    corpo = ['BT', '/F1 22 Tf', '60 760 Td', f'({esc(titulo)}) Tj', '/F1 14 Tf', '0 -48 Td', '24 TL']
    for linha in linhas:
        for pedaco in textwrap.wrap(linha, 62):
            corpo += [f'({esc(pedaco)}) Tj', 'T*']
        corpo.append('T*')
    corpo += ['/F1 10 Tf', '(ConectaTEA - material de demonstração) Tj', 'ET']
    fluxo = '\n'.join(corpo).encode('cp1252', errors='replace')
    objetos = [
        b'<< /Type /Catalog /Pages 2 0 R >>',
        b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
        b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R '
        b'/Resources << /Font << /F1 5 0 R >> >> >>',
        b'<< /Length ' + str(len(fluxo)).encode() + b' >>\nstream\n' + fluxo + b'\nendstream',
        b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
    ]
    saida, posicoes = bytearray(b'%PDF-1.4\n'), []
    for numero, objeto in enumerate(objetos, start=1):
        posicoes.append(len(saida))
        saida += f'{numero} 0 obj\n'.encode() + objeto + b'\nendobj\n'
    inicio_xref = len(saida)
    saida += f'xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n'.encode()
    for posicao in posicoes:
        saida += f'{posicao:010d} 00000 n \n'.encode()
    saida += f'trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{inicio_xref}\n%%EOF\n'.encode()
    return bytes(saida)


class Command(BaseCommand):
    help = 'Cria (ou apaga, com --apagar) os dados fictícios de demonstração do ConectaTEA.'

    def add_arguments(self, parser):
        parser.add_argument('--apagar', action='store_true', help='Remove só os dados de demonstração.')
        parser.add_argument('--senha', default=SENHA_PADRAO, help='Senha de todas as contas de demonstração.')

    def handle(self, *args, **opcoes):
        self._conferir_ambiente()
        if opcoes['apagar']:
            self._apagar()
            return
        if User.objects.filter(email=email(GESTOR[0])).exists():
            raise CommandError('Os dados de demonstração já existem. Para recriar, rode antes com --apagar.')
        random.seed(2026)  # sempre o mesmo cenário
        self.agora = timezone.now()
        self.hoje = timezone.localdate(self.agora)
        self.arquivos_salvos = []
        try:
            with transaction.atomic():
                self._criar(opcoes['senha'])
        except Exception:
            for nome in self.arquivos_salvos:  # no disco, o arquivo não volta junto com o banco
                default_storage.delete(nome)
            raise
        self._resumo(opcoes['senha'])

    # Conferências e utilitários ---------------------------------------------------------------------------

    def _conferir_ambiente(self):
        executor = MigrationExecutor(connection)
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError('O banco ainda tem migrações pendentes. Rode "python manage.py migrate" (ou espere o '
                               'deploy do Render terminar) e tente de novo.')
        if os.environ.get('DATABASE_URL') and settings.ARMAZENAMENTO_ARQUIVOS != 'banco':
            raise CommandError('No banco do site (DATABASE_URL), os PDFs precisam ficar no banco: defina também '
                               'ARMAZENAMENTO_ARQUIVOS=banco, como no Render.')

    def _quando(self, dias_atras, hora=15, minuto=0):
        dia = self.hoje - timedelta(days=dias_atras)
        momento = timezone.make_aware(datetime.combine(dia, time(hora, minuto)))
        if dias_atras >= 0 and momento > self.agora:
            # O que é "de hoje" não pode ficar depois da hora em que o comando roda (a auditoria mostraria o futuro).
            inicio_do_dia = timezone.make_aware(datetime.combine(self.hoje, time.min))
            recuo = timedelta(minutes=(hora * 60 + minuto) % 97 + 3)
            momento = max(self.agora - recuo, inicio_do_dia)
        return momento

    @staticmethod
    def _datar(objeto, **campos):
        # Campos auto_now_add ignoram o valor passado na criação: a data do passado entra por update.
        type(objeto).objects.filter(pk=objeto.pk).update(**campos)

    def _log(self, user, acao, categoria, aluno=None, dias_atras=0, hora=14, minuto=None):
        log = LogAcesso.objects.create(user=user, aluno=aluno, acao=acao[:200], categoria=categoria,
                                       ip=random.choice(IPS))
        minuto = random.randint(0, 59) if minuto is None else minuto
        self._datar(log, ocorrido_em=self._quando(dias_atras, hora, minuto))

    def _pdf(self, atividade, titulo, linhas):
        atividade.arquivo_pdf.save(f'{slugify(titulo)[:60]}.pdf', ContentFile(pdf_de_texto(titulo, linhas)),
                                   save=False)
        self.arquivos_salvos.append(atividade.arquivo_pdf.name)

    # Criação ------------------------------------------------------------------------------------------------

    def _criar(self, senha):
        self.gestor = User.objects.create_user(email(GESTOR[0]), GESTOR[1], senha, role=User.Role.ADMIN,
                                               is_staff=True, termos_aceitos_em=self._quando(45, 9))
        self.gestor.user_permissions.add(
            Permission.objects.get(codename='change_profissional', content_type__app_label='usuarios'))
        self._datar(self.gestor, created_at=self._quando(45, 9))

        self.prof = {}
        for chave, nome, profissao, uf, numero, area, aprovado in PROFISSIONAIS:
            criado = 43 if aprovado else 1
            user = User.objects.create_user(email(chave), nome, senha, role=User.Role.PROFISSIONAL,
                                            termos_aceitos_em=self._quando(criado, 9))
            prof = Profissional(user=user, profissao=profissao, uf_registro=uf, numero_registro=numero,
                                especialidade=f'{Profissional.Profissao(profissao).label} · {area}',
                                is_approved=aprovado)
            prof.registro_profissional = prof.registro_formatado or None
            if aprovado:
                prof.aprovado_em, prof.aprovado_por = self._quando(42, 10), self.gestor
            prof.save()
            self._datar(user, created_at=self._quando(criado, 9))
            self._log(user, 'Criou a conta (Profissional)', Cat.AUTENTICACAO, dias_atras=criado, hora=9)
            if aprovado:
                registro = prof.registro_formatado or 'Pedagogia, sem conselho'
                self._log(self.gestor, f'Aprovou o profissional {nome} ({registro})', Cat.GESTAO,
                          dias_atras=42, hora=10)
            self.prof[chave] = prof

        self.aluno = {}
        for chave, nome, resp_chave, nascimento, responsavel in ALUNOS:
            criado = 41 if resp_chave else 2
            user = User.objects.create_user(email(chave), nome, senha, role=User.Role.ALUNO,
                                            termos_aceitos_em=self._quando(criado, 19))
            aluno = Aluno.objects.create(
                user=user, profissional=self.prof[resp_chave] if resp_chave else None, birth_date=nascimento,
                guardian_name=responsavel, guardian_phone='(11) 90000-0000', guardian_email=email(f'resp.{chave}'),
                consentimento_data=self._quando(criado, 19),
            )
            self._datar(user, created_at=self._quando(criado, 19))
            self._log(user, 'Criou a conta (Aluno)', Cat.AUTENTICACAO, dias_atras=criado, hora=19)
            self.aluno[chave] = aluno
            if resp_chave:
                dono = self.prof[resp_chave]
                pedido = SolicitacaoVinculo.objects.create(profissional=dono, aluno=aluno,
                                                           status=SolicitacaoVinculo.Status.ACEITA,
                                                           respondida_em=self._quando(40, 18))
                self._datar(pedido, criada_em=self._quando(40, 10))
                sala = Sala.objects.create(aluno=aluno, dono=dono)
                self._datar(sala, criada_em=self._quando(40, 18))
                self._log(dono.user, 'Enviou pedido de vínculo', Cat.SALAS, aluno, dias_atras=40, hora=10)
                self._log(user, f'Aceitou o vínculo com {dono.user.name}', Cat.SALAS, aluno, dias_atras=40, hora=18)

        # Helena: pedido de vínculo esperando o aceite (dá para mostrar o fluxo ao vivo). Davi: ainda sem pedido.
        pedido = SolicitacaoVinculo.objects.create(profissional=self.prof['mariana'], aluno=self.aluno['helena'])
        self._datar(pedido, criada_em=self._quando(1, 11))
        self._log(self.prof['mariana'].user, 'Enviou pedido de vínculo', Cat.SALAS, self.aluno['helena'],
                  dias_atras=1, hora=11)
        PreferenciaAcessibilidade.objects.create(user=self.aluno['lucas'].user, tamanho_fonte='grande')

        self._equipes()
        self._atividades()
        self._propostas_na_sala()
        self._pedidos_de_ajuda()
        self._videochamadas()
        self._anotacoes()
        self._entradas_no_sistema()

    def _membro(self, chave_aluno, chave_prof, dias_atras, aprovado=True):
        sala, prof = self.aluno[chave_aluno].sala, self.prof[chave_prof]
        membro = MembroSala.objects.create(
            sala=sala, profissional=prof,
            status=MembroSala.Status.APROVADO if aprovado else MembroSala.Status.PENDENTE,
            respondido_em=self._quando(dias_atras - 1, 9) if aprovado else None,
        )
        self._datar(membro, solicitado_em=self._quando(dias_atras, 16))
        self._log(prof.user, 'Pediu para entrar na sala do aluno', Cat.SALAS, sala.aluno, dias_atras=dias_atras,
                  hora=16)
        if aprovado:
            self._log(sala.dono.user, f'Aprovou {prof.user.name} na sala', Cat.SALAS, sala.aluno,
                      dias_atras=dias_atras - 1, hora=9)

    def _equipes(self):
        self._membro('pedro', 'rafael', 32)
        self._membro('pedro', 'camila', 30)
        self._membro('gabriel', 'rafael', 21)
        self._membro('ana', 'juliana', 1, aprovado=False)  # esperando o dono aprovar

    def _atividades(self):
        for chave_prof, itens in ATIVIDADES.items():
            prof = self.prof[chave_prof]
            alunos = [(chave, a) for chave, a in self.aluno.items() if a.profissional_id == prof.pk]
            feitas = len(itens) - ABERTAS[chave_prof]
            for indice, (titulo, categoria, instrucoes, linhas) in enumerate(itens):
                aberta = indice >= feitas
                criada = [6, 3][indice - feitas] if aberta else 40 - indice * 7
                distribuida = criada if aberta else criada - 1
                atividade = Atividade(profissional=prof, title=titulo, category=categoria, description=instrucoes,
                                      tipo_material=Atividade.TipoMaterial.PDF)
                self._pdf(atividade, titulo, linhas)
                atividade.save()
                self._datar(atividade, created_at=self._quando(criada, 10))
                self._log(prof.user, f'Criou a atividade "{titulo}"', Cat.ATIVIDADES, dias_atras=criada, hora=10)
                for posicao, (chave_aluno, aluno) in enumerate(alunos):
                    # Atividade em aberto: alguns prazos já passaram (aparecem como atrasadas).
                    prazo = (self.hoje + timedelta(days=[-2, 2, 4, -1, 5][(posicao + indice) % 5]) if aberta
                             else self.hoje - timedelta(days=distribuida - 7))
                    atribuicao = Atribuicao.objects.create(atividade=atividade, aluno=aluno, profissional=prof,
                                                           prazo=prazo)
                    self._datar(atribuicao, atribuida_em=self._quando(distribuida, 11))
                    if (chave_aluno, titulo) in NAO_FEZ:
                        continue
                    if not aberta:
                        self._concluir(aluno, atividade, prof, distribuida - random.randint(1, 5))
                        if chave_aluno == 'pedro' and indice == 0:  # refez a primeira: duas tentativas
                            self._concluir(aluno, atividade, prof, distribuida - 9)
                    elif posicao == 0 and indice == feitas:  # o primeiro aluno já fez a mais nova
                        self._concluir(aluno, atividade, prof, 1)
                self._log(prof.user, f'Distribuiu a atividade "{titulo}" para {len(alunos)} aluno(s)',
                          Cat.ATIVIDADES, dias_atras=distribuida, hora=11)

    def _concluir(self, aluno, atividade, prof, dias_atras):
        dias_atras = max(dias_atras, 0)
        hora = random.choice([9, 14, 16, 19])
        correcao = random.choice(CORRECOES + ['', ''])
        RegistroEvolucao.objects.create(
            aluno=aluno, atividade=atividade, status=RegistroEvolucao.Status.CONCLUIDA,
            resposta=random.choice(RESPOSTAS), observacoes=correcao,
            data_realizacao=self._quando(dias_atras, hora, random.randint(0, 59)),
        )
        Atribuicao.objects.filter(aluno=aluno, atividade=atividade).update(status=Atribuicao.Status.CONCLUIDA)
        self._log(aluno.user, f'Concluiu a atividade "{atividade.title}"', Cat.ATIVIDADES, aluno,
                  dias_atras=dias_atras, hora=hora)
        if correcao and dias_atras > 0:
            self._log(prof.user, 'Visualizou a evolução do aluno', Cat.DADOS_ALUNO, aluno,
                      dias_atras=dias_atras - 1, hora=10, minuto=5)
            self._log(prof.user, f'Escreveu correção na atividade "{atividade.title}"', Cat.DADOS_ALUNO, aluno,
                      dias_atras=dias_atras - 1, hora=10, minuto=12)

    def _propostas_na_sala(self):
        """Equipe da sala do Pedro: uma atividade aprovada, uma recusada com motivo e uma esperando análise."""
        sala = self.aluno['pedro'].sala
        for autor, titulo, publicacao, motivo, dias in [
            ('rafael', 'Massinha para fortalecer as mãos', Atividade.Publicacao.PUBLICADA, '', 8),
            ('camila', 'Leitura de uma história longa', Atividade.Publicacao.RECUSADA,
             'Texto longo demais para este momento. Vamos dividir em partes menores.', 5),
            ('camila', 'Treino de sons com a letra R', Atividade.Publicacao.EM_ANALISE, '', 1),
        ]:
            nome_autor = self.prof[autor].user.name
            proposta = Atividade(profissional=sala.dono, aluno=sala.aluno, autor=self.prof[autor], title=titulo,
                                 category='equipe', description=f'Proposta de {nome_autor} para o Pedro.',
                                 tipo_material=Atividade.TipoMaterial.PDF, publicacao=publicacao, motivo_recusa=motivo)
            self._pdf(proposta, titulo, ['Atividade proposta pela equipe da sala.', 'Faça com calma.'])
            proposta.save()
            self._datar(proposta, created_at=self._quando(dias, 17))
            self._log(self.prof[autor].user, f'Propôs a atividade "{titulo}" na sala', Cat.ATIVIDADES, sala.aluno,
                      dias_atras=dias, hora=17)
            if publicacao != Atividade.Publicacao.EM_ANALISE:
                verbo = 'Aprovou' if publicacao == Atividade.Publicacao.PUBLICADA else 'Recusou'
                self._log(sala.dono.user, f'{verbo} a atividade proposta "{titulo}"', Cat.ATIVIDADES, sala.aluno,
                          dias_atras=dias - 1, hora=9)

    def _pedidos_de_ajuda(self):
        for chave, titulo, mensagem, dias, respondido in [
            ('ana', 'Esperar a minha vez', 'Não entendi a situação 2.', 0, False),
            ('beatriz', 'Iniciar uma conversa sobre um assunto de interesse', '', 1, False),
            ('lucas', 'Combinar uma mudança na rotina', 'Não sei qual mudança escrever.', 17, True),
        ]:
            aluno = self.aluno[chave]
            hora = 8 if dias == 0 else 16
            atividade = Atividade.objects.get(title=titulo, profissional=aluno.profissional)
            pedido = PedidoAjuda.objects.create(
                aluno=aluno, atividade=atividade, mensagem=mensagem,
                respondido_em=self._quando(dias - 1, 10) if respondido else None,
                respondido_por=aluno.profissional.user if respondido else None,
            )
            self._datar(pedido, criado_em=self._quando(dias, hora))
            self._log(aluno.user, f'Pediu ajuda na atividade "{titulo}"', Cat.ATIVIDADES, aluno, dias_atras=dias,
                      hora=hora)
            if respondido:
                self._log(aluno.profissional.user, f'Respondeu ao pedido de ajuda em "{titulo}"', Cat.ATIVIDADES,
                          aluno, dias_atras=dias - 1, hora=10)

    def _videochamadas(self):
        for chave, semanas, daqui_a, pauta in [
            ('pedro', 4, 1, 'Conversar com a equipe sobre os cumprimentos'),
            ('ana', 2, 2, 'Revisar a atividade de esperar a vez'),
            ('gabriel', 3, 3, 'Treinar as frases para pedir ajuda'),
        ]:
            sala = self.aluno[chave].sala
            pessoas = [sala.aluno.user, sala.dono.user] + [m.profissional.user for m in sala.membros_aprovados()]
            for semana in range(semanas):
                dia = 7 * semana + 5
                inicio = self._quando(dia, 15)
                self._log(sala.dono.user, f'Marcou videochamada para {timezone.localtime(inicio):%d/%m/%Y %H:%M}',
                          Cat.SALAS, sala.aluno, dias_atras=dia + 2, hora=18)
                for ordem, user in enumerate(pessoas):
                    if semana == 2 and ordem > 1:  # numa das semanas, a equipe não conseguiu entrar
                        continue
                    entrada = inicio + timedelta(minutes=ordem * 2)
                    participacao = ParticipacaoVideochamada.objects.create(
                        sala=sala, user=user, entrou_em=entrada,
                        saiu_em=entrada + timedelta(minutes=random.randint(25, 40)),
                    )
                    self._datar(participacao, acionada_em=entrada - timedelta(seconds=40))
            # Próxima chamada já marcada; o Pedro respondeu que vai participar.
            sala.proxima_chamada = self._quando(-daqui_a, 15)
            sala.pauta_chamada = pauta
            marcada = timezone.localtime(sala.proxima_chamada)
            self._log(sala.dono.user, f'Marcou videochamada para {marcada:%d/%m/%Y %H:%M}', Cat.SALAS, sala.aluno,
                      dias_atras=1, hora=18)
            if chave == 'pedro':
                sala.resposta_aluno, sala.respondida_em = 'sim', self._quando(0, 8, 20)
                self._log(sala.aluno.user, 'Respondeu à videochamada: vai participar', Cat.SALAS, sala.aluno,
                          dias_atras=0, hora=8, minuto=20)
            sala.save()

    def _anotacoes(self):
        for chave, autor, texto, visibilidade, dias in [
            ('pedro', 'mariana', 'Pedro está mais tranquilo nas trocas de atividade. Manter o aviso antes da troca.',
             Anotacao.Visibilidade.PRIVADA, 9),
            ('pedro', 'mariana', 'Pedro, parabéns pelos cumprimentos desta semana!',
             Anotacao.Visibilidade.COMPARTILHADA, 4),
            ('pedro', None, 'Hoje eu cumprimentei o João no intervalo.', Anotacao.Visibilidade.COMPARTILHADA, 3),
            ('ana', 'mariana', 'Fica ansiosa em filas. Treinar estratégias de espera antes do recreio.',
             Anotacao.Visibilidade.PRIVADA, 6),
            ('gabriel', 'camila', 'Usou a prancha de comunicação sem ajuda pela primeira vez.',
             Anotacao.Visibilidade.PRIVADA, 11),
        ]:
            aluno = self.aluno[chave]
            nota = Anotacao.objects.create(autor=self.prof[autor].user if autor else aluno.user, aluno=aluno,
                                           texto=texto, visibilidade=visibilidade)
            momento = self._quando(dias, 18)
            self._datar(nota, criado_em=momento, atualizado_em=momento)

    def _entradas_no_sistema(self):
        """Movimento da última semana, com uma senha errada e uma tentativa com e-mail que não existe."""
        pessoas = [self.prof[c].user for c in ('mariana', 'rafael', 'camila', 'juliana')] + \
            [self.aluno[c].user for c in ('pedro', 'ana', 'lucas', 'gabriel', 'sofia', 'mateus')]
        for dias in range(7, -1, -1):
            for user in random.sample(pessoas, 5):
                self._log(user, 'Entrou no sistema', Cat.AUTENTICACAO, dias_atras=dias, hora=random.randint(8, 20))
        self._log(self.gestor, 'Entrou no sistema', Cat.AUTENTICACAO, dias_atras=1, hora=9)
        self._log(self.aluno['lucas'].user, 'Tentativa de login com senha errada', Cat.AUTENTICACAO, dias_atras=2,
                  hora=19, minuto=2)
        self._log(None, f'Tentativa de login com e-mail não cadastrado (x***@{DOMINIO})', Cat.AUTENTICACAO,
                  dias_atras=1, hora=3)

    # Apagar e resumo ----------------------------------------------------------------------------------------

    def _apagar(self):
        users = User.objects.filter(email__endswith=f'@{DOMINIO}')
        alunos = Aluno.objects.filter(user__in=users)
        profs = Profissional.objects.filter(user__in=users)
        with transaction.atomic():
            # Se alguém usou uma conta de demonstração com um aluno real, o aluno real fica, só perde o vínculo.
            Aluno.objects.filter(profissional__in=profs).exclude(pk__in=alunos).update(profissional=None)
            atividades = Atividade.objects.filter(Q(profissional__in=profs) | Q(autor__in=profs) | Q(aluno__in=alunos))
            arquivos = [nome for nome in atividades.values_list('arquivo_pdf', flat=True) if nome]
            salas = Sala.objects.filter(Q(aluno__in=alunos) | Q(dono__in=profs))
            LogAcesso.objects.filter(Q(user__in=users) | Q(aluno__in=alunos)).delete()
            LogAcesso.objects.filter(user__isnull=True, acao__contains=f'@{DOMINIO}').delete()
            ParticipacaoVideochamada.objects.filter(Q(user__in=users) | Q(sala__in=salas)).delete()
            MembroSala.objects.filter(Q(profissional__in=profs) | Q(sala__in=salas)).delete()
            PedidoAjuda.objects.filter(Q(aluno__in=alunos) | Q(atividade__in=atividades)).delete()
            RegistroEvolucao.objects.filter(Q(aluno__in=alunos) | Q(atividade__in=atividades)).delete()
            Atribuicao.objects.filter(
                Q(aluno__in=alunos) | Q(atividade__in=atividades) | Q(profissional__in=profs)).delete()
            Anotacao.objects.filter(Q(aluno__in=alunos) | Q(autor__in=users)).delete()
            salas.delete()
            SolicitacaoVinculo.objects.filter(Q(aluno__in=alunos) | Q(profissional__in=profs)).delete()
            atividades.delete()
            alunos.delete()
            profs.delete()
            total = users.count()
            users.delete()  # preferências e códigos de senha saem junto (CASCADE)
        for nome in arquivos:
            default_storage.delete(nome)
        self.stdout.write(self.style.SUCCESS(f'Dados de demonstração removidos ({total} contas).'))

    def _resumo(self, senha):
        self.stdout.write(self.style.SUCCESS('Dados de demonstração criados.'))
        self.stdout.write(f'Senha de todas as contas: {senha}\n')
        self.stdout.write(f'Gestor        {email(GESTOR[0]):26} {GESTOR[1]}')
        for chave, nome, *_resto, aprovado in PROFISSIONAIS:
            self.stdout.write(f'Profissional  {email(chave):26} {nome}{"" if aprovado else " (espera aprovação)"}')
        for chave, nome, resp, *_resto in ALUNOS:
            situacao = f'com {self.prof[resp].user.name}' if resp else 'sem profissional'
            self.stdout.write(f'Aluno         {email(chave):26} {nome} ({situacao})')
