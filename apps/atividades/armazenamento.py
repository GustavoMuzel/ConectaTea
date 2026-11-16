"""Armazenamento de arquivos (PDFs das atividades) dentro do próprio banco de dados.

Serve para hospedagens com disco temporário, como o plano gratuito do Render: lá, a pasta media/ é apagada a cada
reinício. Guardando o PDF no PostgreSQL, ele sobrevive aos reinícios e entra no backup do banco. Os PDFs são
pequenos (até 10 MB, conferido no formulário), então o volume é baixo. Em uma instalação maior, o caminho
natural é um armazenamento de objetos (S3, Cloudflare R2) com o django-storages.
"""

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


@deconstructible
class BancoDeDadosStorage(Storage):
    def _modelo(self):
        from .models import ArquivoArmazenado  # import tardio: o storage é criado antes dos apps carregarem
        return ArquivoArmazenado

    def _open(self, name, mode='rb'):
        arquivo = self._modelo().objects.get(nome=name)
        return ContentFile(bytes(arquivo.conteudo), name=name)

    def _save(self, name, content):
        content.seek(0)
        dados = b''.join(content.chunks())
        self._modelo().objects.create(nome=name, conteudo=dados, tamanho=len(dados))
        return name

    def exists(self, name):
        return self._modelo().objects.filter(nome=name).exists()

    def delete(self, name):
        self._modelo().objects.filter(nome=name).delete()

    def size(self, name):
        return self._modelo().objects.values_list('tamanho', flat=True).get(nome=name)

    def url(self, name):
        # Os PDFs nunca têm endereço público: são entregues pela view que confere a permissão.
        raise NotImplementedError('Arquivos do banco são entregues pela view material_atividade.')
