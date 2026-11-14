"""Página pública "Sobre o TEA"."""
import pytest
from django.urls import reverse

from .models import Profissional, User

pytestmark = pytest.mark.integration


@pytest.mark.django_db
def test_pagina_publica_com_fontes_e_aviso(client):
    resp = client.get(reverse('sobre_tea'))
    html = resp.content.decode()
    assert resp.status_code == 200
    assert 'não substitui a avaliação de um profissional' in html
    assert 'educadiversidade.unesp.br' in html and '12.764' in html and '6A02' in html


@pytest.mark.django_db
def test_link_no_menu_para_visitante_e_usuario_logado(client):
    url = reverse('sobre_tea')
    assert f'href="{url}"' in client.get(reverse('home')).content.decode()
    user = User.objects.create_user('p@ex.com', 'Prof', 'Senha-forte-123', role=User.Role.PROFISSIONAL)
    Profissional.objects.create(user=user, especialidade='Psicologia', is_approved=True)
    client.force_login(user)
    assert f'href="{url}"' in client.get(reverse('painel')).content.decode()
