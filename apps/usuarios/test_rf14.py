import pytest
from django.urls import reverse

from .models import PreferenciaAcessibilidade, User

SENHA = 'Senha-forte-123'
URL = reverse('preferencias')


@pytest.fixture
def usuario(client):
    user = User.objects.create_user('ana@ex.com', 'Ana', SENHA, role=User.Role.ALUNO)
    client.force_login(user)
    return user


@pytest.mark.django_db
def test_usuario_salva_preferencias(client, usuario):
    assert client.get(URL).status_code == 200
    resp = client.post(URL, {'tamanho_fonte': 'grande', 'alto_contraste': 'on'})
    assert resp.status_code == 302 and resp.url == URL
    prefs = PreferenciaAcessibilidade.objects.get(user=usuario)
    assert (prefs.tamanho_fonte, prefs.alto_contraste, prefs.reduzir_estimulos) == ('grande', True, False)
    # Só as próprias: salvar de novo atualiza o mesmo registro e não mexe no de outro usuário.
    outro = User.objects.create_user('bia@ex.com', 'Bia', SENHA, role=User.Role.ALUNO)
    client.post(URL, {'tamanho_fonte': 'normal', 'reduzir_estimulos': 'on'})
    assert PreferenciaAcessibilidade.objects.filter(user=usuario).count() == 1
    assert not PreferenciaAcessibilidade.objects.filter(user=outro).exists()
    prefs.refresh_from_db()
    assert (prefs.tamanho_fonte, prefs.alto_contraste, prefs.reduzir_estimulos) == ('normal', False, True)
    # O dono vem da sessão, nunca do POST; valor fora da lista é recusado e nada muda.
    client.post(URL, {'tamanho_fonte': 'grande', 'user': outro.pk})
    assert not PreferenciaAcessibilidade.objects.filter(user=outro).exists()
    resp = client.post(URL, {'tamanho_fonte': 'enorme'})
    assert resp.status_code == 200 and 'tamanho_fonte' in resp.context['form'].errors
    prefs.refresh_from_db()
    assert prefs.tamanho_fonte == 'grande'


@pytest.mark.django_db
def test_context_processor_aplica_classes(client, usuario):
    def classes_do_body():
        html = client.get(reverse('preferencias')).content.decode()
        return html[html.index('<body'):html.index('>', html.index('<body'))]

    sem_nada = classes_do_body()  # padrão (abrir a tela cria o registro com os valores iniciais)
    assert not any(c in sem_nada for c in ['font-lg', 'font-xlg', 'high-contrast', 'reduce-stimuli'])

    PreferenciaAcessibilidade.objects.update_or_create(
        user=usuario, defaults={'tamanho_fonte': 'grande', 'alto_contraste': True},
    )
    body = classes_do_body()
    assert 'font-lg' in body and 'high-contrast' in body and 'reduce-stimuli' not in body

    PreferenciaAcessibilidade.objects.filter(user=usuario).update(tamanho_fonte='muito_grande', reduzir_estimulos=True)
    body = classes_do_body()
    assert 'font-xlg' in body and 'reduce-stimuli' in body

    client.logout()
    assert 'font-xlg' not in client.get(reverse('login')).content.decode()  # visitante: padrão


@pytest.mark.django_db
def test_usuario_deslogado_nao_acessa(client):
    resp = client.get(URL)
    assert resp.status_code == 302 and resp.url.startswith(reverse('login'))
    assert client.post(URL, {'tamanho_fonte': 'grande'}).status_code == 302
    assert not PreferenciaAcessibilidade.objects.exists()
