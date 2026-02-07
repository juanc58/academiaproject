from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0018_remove_especialidad_datoscontrol'),
    ]

    operations = [
        migrations.AddField(
            model_name='libros',
            name='co_autor',
            field=models.CharField(max_length=100, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='libros',
            name='numero_registro',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='libros',
            name='fecha_registro',
            field=models.DateField(null=True, blank=True),
        ),
    ]
