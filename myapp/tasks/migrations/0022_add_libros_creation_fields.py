from django.db import migrations, models
from django.utils import timezone


def fill_creation_dates(apps, schema_editor):
    Libros = apps.get_model('tasks', 'Libros')
    now = timezone.now()
    # Actualizar en bloque: evitar llamar a save() por instancia (evita validaciones de campo)
    fecha_val = now.date()
    hora_val = now.time().replace(microsecond=0)
    # Para las filas que tienen NULL en fecha_creacion u hora_creacion, establecer valores
    Libros.objects.filter(fecha_creacion__isnull=True).update(fecha_creacion=fecha_val)
    Libros.objects.filter(hora_creacion__isnull=True).update(hora_creacion=hora_val)


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0021_alter_prestamo_receiver_cedula_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='libros',
            name='fecha_creacion',
            field=models.DateField(auto_now_add=True, null=True, blank=True, verbose_name='fecha de creación'),
        ),
        migrations.AddField(
            model_name='libros',
            name='hora_creacion',
            field=models.TimeField(auto_now_add=True, null=True, blank=True, verbose_name='hora de creación'),
        ),
        migrations.RunPython(fill_creation_dates, reverse_code=migrations.RunPython.noop),
    ]
