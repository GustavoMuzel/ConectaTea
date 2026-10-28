# R1: guard de permissão em "Aprovar profissionais"

**Data:** 2026-10-27. **Status:** aplicado na árvore de trabalho, não commitado.

## Problema
A action em massa `aprovar_profissionais`, de `ProfissionalAdmin`, não verificava permissão. Um staff que tinha só `view_profissional` conseguia aprovar profissionais. Isso fere o RF05/RN01.

## Diff

`apps/usuarios/admin.py`
```diff
-from django.contrib import admin
+from django.contrib import admin, messages
@@ class ProfissionalAdmin(SoftDeleteAdminMixin, admin.ModelAdmin):
     @admin.action(description='Aprovar profissionais selecionados')
     def aprovar_profissionais(self, request: HttpRequest, queryset: QuerySet) -> None:
+        if not self.has_change_permission(request):  # staff só de leitura não aprova (RF05/RN01)
+            self.message_user(request, 'Você não tem permissão para aprovar profissionais.', messages.ERROR)
+            return
         total = queryset.update(is_approved=True)
         self.message_user(request, f'{total} profissional(is) aprovado(s).')
```

`apps/usuarios/test_admin.py`
```diff
+@pytest.mark.django_db
+@pytest.mark.parametrize('perms, aprovados', [
+    (['view_profissional'], 0),
+    (['view_profissional', 'change_profissional'], 2),
+])
+def test_aprovar_em_massa_exige_change_profissional(client, dados, perms, aprovados):
+    pendentes = [
+        Profissional.objects.create(
+            user=User.objects.create_user(f'p{i}@ex.com', f'P{i}', SENHA, role=User.Role.PROFISSIONAL),
+            especialidade='Pedagogia',
+        ).pk
+        for i in range(2)
+    ]
+    _staff(client, *perms)
+    resp = client.post(reverse('admin:usuarios_profissional_changelist'),
+                       {'action': 'aprovar_profissionais', '_selected_action': pendentes}, follow=True)
+
+    assert Profissional.objects.filter(pk__in=pendentes, is_approved=True).count() == aprovados
+    sem_permissao = 'Você não tem permissão para aprovar profissionais.' in resp.content.decode()
+    assert sem_permissao is (aprovados == 0)
```

## Teste
`apps/usuarios/test_admin.py::test_aprovar_em_massa_exige_change_profissional`, com 2 casos:
- **Staff só com `view_profissional`:** 0 aprovados e a mensagem de erro aparece.
- **Staff com `view_profissional` e `change_profissional`:** 2 aprovados e nenhuma mensagem de erro.

Contra o `admin.py` original (guardado com `git stash` só desse arquivo), o caso sem permissão falha com `assert 2 == 0`. O teste, portanto, detecta o problema.

## /django-review
- **Resultado:** aprovado, sem achados (nenhum CRÍTICO, ALTO, MÉDIO ou BAIXO).
- **`list_editable = ['is_approved']`:** não abre outro caminho para aprovar. O Django exige `has_change_permission` tanto para salvar quanto para montar o formset.
- **Observação, não é achado:** a action continua aparecendo no menu para quem só tem leitura. O guard foi colocado dentro da action, e não em `permissions=['change']` no decorator, por escolha do usuário.

## /django-test
- **Coletados:** 104, que são os 102 da baseline mais os 2 casos novos.
- **Resultado:** 104 passed, 0 failed, 0 skipped, em 207,6 s.
- **Warnings:** 8 `InsecureKeyLengthWarning`, que vêm da `SECRET_KEY` fictícia do CI, de 12 bytes.
