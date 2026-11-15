"""Tempo de carregamento das páginas principais no navegador (RNF03: até 2 segundos em rede doméstica).

Abre cada página num Chromium com a rede limitada, como numa conexão doméstica, e mede pelo próprio navegador
(Navigation Timing) o tempo até a página terminar de carregar, com CSS, fontes e scripts (evento load). Cada
página é medida na primeira visita (sem nada guardado no navegador) e nas visitas seguintes (CSS e fontes já
guardados).

Requer: pip install playwright && playwright install chromium
Uso:
    python desempenho/tempo_carregamento.py --url https://conectatea-j0az.onrender.com --senha <senha da demo>
"""

import argparse
import gzip
import statistics
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

# Perfis de rede (latência de ida e volta em ms; velocidades em kbit/s).
REDES = {
    'domestica': {'latencia': 150, 'download': 10_000, 'upload': 2_000},  # banda larga simples, servidor nos EUA
    '4g-lento': {'latencia': 150, 'download': 1_600, 'upload': 750},     # perfil "Slow 4G" do Lighthouse
    'sem-limite': None,
}
PAGINAS = {
    'pedro': ['/aluno/', '/aluno/atividades/', '/aluno/historico/', '/salas/minha-equipe/'],
    'mariana': ['/painel/', '/painel/alunos/', '/salas/', '/aluno/dashboard-profissional/'],
    'coordenacao': ['/painel-gestao/', '/painel-gestao/auditoria/'],
}
PUBLICAS = ['/', '/entrar/', '/sobre-o-tea/']
MEDIR = """() => { const n = performance.getEntriesByType('navigation')[0];
  return {conteudo: n.domContentLoadedEventEnd, completo: n.loadEventEnd}; }"""


def limitar_rede(contexto, pagina, rede, pasta_cdn):
    if rede:
        cdp = contexto.new_cdp_session(pagina)
        cdp.send('Network.enable')
        cdp.send('Network.emulateNetworkConditions', {
            'offline': False, 'latency': rede['latencia'],
            'downloadThroughput': rede['download'] * 1000 / 8, 'uploadThroughput': rede['upload'] * 1000 / 8,
        })
    if pasta_cdn:  # sem internet: serve as cópias locais do CDN com o atraso que a rede simulada teria
        def servir(rota):
            arquivo = Path(pasta_cdn) / rota.request.url.split('/')[-1]
            conteudo = arquivo.read_bytes()
            if rede:  # o CDN envia o arquivo comprimido: o atraso considera o tamanho comprimido
                tamanho = len(gzip.compress(conteudo))
                time.sleep(rede['latencia'] / 1000 + tamanho * 8 / (rede['download'] * 1000))
            tipo = 'text/css' if arquivo.suffix == '.css' else 'text/javascript'
            rota.fulfill(body=conteudo, content_type=tipo)
        pagina.route('https://cdn.jsdelivr.net/**', servir)


def visitar(pagina, url):
    pagina.goto(url, wait_until='load')
    return pagina.evaluate(MEDIR)


def medir(navegador, args, rede, conta, caminhos):
    resultados = {}
    contexto = navegador.new_context(ignore_https_errors=args.ignorar_certificado)
    pagina = contexto.new_page()
    limitar_rede(contexto, pagina, rede, args.cdn_local)
    if conta:
        pagina.goto(args.url + '/entrar/')
        pagina.fill('input[name=username]', f'{conta}@example.com')
        pagina.fill('input[name=password]', args.senha)
        with pagina.expect_navigation():
            pagina.click('form button[type=submit]')
        if pagina.url.rstrip('/').endswith('/entrar'):
            raise SystemExit(f'Login recusado para {conta}@example.com: confira a senha.')
    for caminho in caminhos:
        # Primeira visita com o navegador "limpo" (sem cache), depois as visitas seguintes.
        cdp = contexto.new_cdp_session(pagina)
        cdp.send('Network.clearBrowserCache')
        primeira = visitar(pagina, args.url + caminho)
        seguintes = [visitar(pagina, args.url + caminho) for _ in range(args.vezes)]
        resultados[caminho] = (primeira, seguintes)
    contexto.close()
    return resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--url', required=True)
    parser.add_argument('--senha', required=True, help='senha das contas de demonstração')
    parser.add_argument('--rede', choices=REDES, default='domestica')
    parser.add_argument('--vezes', type=int, default=5, help='visitas seguintes medidas por página')
    parser.add_argument('--ignorar-certificado', action='store_true', help='para teste local com HTTPS próprio')
    parser.add_argument('--cdn-local', help='pasta com bootstrap.min.css e chart.umd.min.js (sem internet)')
    parser.add_argument('--chromium', help='caminho de um Chromium já instalado')
    args = parser.parse_args()
    args.url = args.url.rstrip('/')
    rede = REDES[args.rede]

    with sync_playwright() as p:
        navegador = p.chromium.launch(executable_path=args.chromium)
        linhas = []
        for conta, caminhos in [(None, PUBLICAS)] + list(PAGINAS.items()):
            for caminho, (primeira, seguintes) in medir(navegador, args, rede, conta, caminhos).items():
                completo = statistics.median(m['completo'] for m in seguintes)
                linhas.append((conta or 'visitante', caminho, primeira['completo'], completo))
        navegador.close()

    print(f'Rede: {args.rede}  |  meta do RNF03: 2000 ms')
    if args.cdn_local:
        print('Com --cdn-local o navegador não usa cache: as visitas seguintes também baixam tudo de novo.')
    print(f'\n{"perfil":12} {"página":32} {"1ª visita":>10} {"seguintes":>10}  meta')
    for perfil, caminho, primeira, seguintes in linhas:
        ok = 'ok' if max(primeira, seguintes) <= 2000 else 'ACIMA'
        print(f'{perfil:12} {caminho:32} {primeira:8.0f}ms {seguintes:8.0f}ms  {ok}')
    pior = max(max(linha[2], linha[3]) for linha in linhas)
    print(f'\nPior caso: {pior:.0f} ms ({"dentro" if pior <= 2000 else "fora"} da meta de 2 s).')


if __name__ == '__main__':
    main()
