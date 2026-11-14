"""Configuração de produção (Render + Neon): roda o Django em outro processo com as variáveis do servidor."""
import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

RAIZ = Path(__file__).resolve().parents[2]


def _rodar(codigo, **env):
    ambiente = {**os.environ, 'SECRET_KEY': secrets.token_urlsafe(50), 'DJANGO_SETTINGS_MODULE': 'config.settings',
                **env}
    ambiente.pop('DB_ENGINE', None)
    return subprocess.run([sys.executable, '-c', codigo], cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                          timeout=120)


def test_database_url_do_neon_e_lida():
    url = 'postgresql://ana:s%40nha@ep-x.us-east-1.aws.neon.tech:5432/neondb?sslmode=require'
    r = _rodar('import django, json; django.setup(); from django.conf import settings; '
               'print(json.dumps(settings.DATABASES["default"], default=str))', DATABASE_URL=url)
    banco = json.loads(r.stdout)
    assert banco['ENGINE'] == 'django.db.backends.postgresql'
    assert (banco['NAME'], banco['USER'], banco['PASSWORD']) == ('neondb', 'ana', 's@nha')
    assert banco['HOST'] == 'ep-x.us-east-1.aws.neon.tech' and banco['OPTIONS'] == {'sslmode': 'require'}


def test_check_deploy_sem_avisos_em_producao():
    codigo = ('import django, sys; django.setup(); from django.core.management import call_command; '
              'call_command("check", deploy=True, fail_level="WARNING")')
    r = _rodar(codigo, PRODUCAO='True', DEBUG='False', ALLOWED_HOSTS='conectatea.onrender.com',
               SECURE_HSTS_SECONDS='3600')
    assert r.returncode == 0, r.stderr[-2000:]
