from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0017_normalize_clasificacion_labels'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='libros',
            name='especialidad',
        ),
        migrations.RemoveField(
            model_name='libros',
            name='datos_control',
        ),
    ]
