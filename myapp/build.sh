#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# Cargar datos del diccionario automáticamente en cada despliegue
python manage.py import_dictionary diccionario.csv