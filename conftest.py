import socket

import pytest
from django.core.cache import cache

GRUPOS = ('unit', 'integration')
# Fixtures do pytest-django que liberam o banco ou montam o site inteiro: só valem em teste de integração.
FIXTURES_DE_INTEGRACAO = {
    'db', 'transactional_db', 'django_db_reset_sequences', 'django_db_serialized_rollback',
    'client', 'admin_client', 'admin_user', 'django_user_model', 'live_server',
}


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items):
    """Todo teste pertence a exatamente um grupo, e teste unitário não usa banco.

    Roda antes do filtro do -m, então confere todos os testes, inclusive os do outro grupo. Sem isso, um teste
    sem marcador ficaria fora das duas checagens da pipeline sem ninguém perceber.
    """
    erros = []
    for item in items:
        grupos = [grupo for grupo in GRUPOS if item.get_closest_marker(grupo)]
        if len(grupos) != 1:
            erros.append(f'{item.nodeid}: marque com exatamente um de @pytest.mark.unit e @pytest.mark.integration')
        elif grupos == ['unit'] and (item.get_closest_marker('django_db')
                                     or FIXTURES_DE_INTEGRACAO & set(item.fixturenames)):
            erros.append(f'{item.nodeid}: teste unitário não pode usar o banco; marque como integration')
    if erros:
        raise pytest.UsageError('Separação dos testes inválida:\n' + '\n'.join(erros))


@pytest.fixture(autouse=True)
def _sem_rede_nos_unitarios(request, monkeypatch):
    """Teste unitário que tentar abrir conexão de rede falha na hora (o banco já é bloqueado pelo pytest-django)."""
    if request.node.get_closest_marker('unit'):
        def bloqueado(*args, **kwargs):
            raise RuntimeError('Teste unitário tentou acessar a rede. Simule a chamada ou marque como integration.')
        monkeypatch.setattr(socket.socket, 'connect', bloqueado)
        monkeypatch.setattr(socket, 'create_connection', bloqueado)


@pytest.fixture(autouse=True)
def _cache_limpo():
    """O limite de pedidos do RF03 usa o cache: sem isto, um teste herdaria o bloqueio do anterior."""
    cache.clear()
