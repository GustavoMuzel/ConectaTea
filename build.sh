#!/usr/bin/env bash
# Build do Render: instala, junta os estáticos, aplica as migrações no Neon e cria o administrador inicial.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# Cria o administrador na primeira vez (DJANGO_SUPERUSER_EMAIL, _NAME e _PASSWORD no Render).
# Nas próximas, ele já existe e o comando só avisa.
if [ -n "$DJANGO_SUPERUSER_EMAIL" ]; then
  python manage.py createsuperuser --noinput || echo "Administrador já existe."
fi
