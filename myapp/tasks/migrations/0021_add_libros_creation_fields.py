from django.db import migrations


class Migration(migrations.Migration):

    # Esta migración fue convertida a no-op porque la lógica de rellenado
    # fue movida a 0022_add_libros_creation_fields.py que usa actualizaciones
    # en bloque (QuerySet.update) evitando validaciones de modelo.
    dependencies = [
        ('tasks', '0020_add_prestamo_receiver_fields'),
    ]

    operations = [
    ]
