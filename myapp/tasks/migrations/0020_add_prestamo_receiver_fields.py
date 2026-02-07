from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tasks', '0019_add_coautor_numreg_fechareg'),
    ]

    operations = [
        migrations.AddField(
            model_name='prestamo',
            name='receiver_cedula',
            field=models.CharField(max_length=32, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='prestamo',
            name='receiver_first_name',
            field=models.CharField(max_length=150, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='prestamo',
            name='receiver_last_name',
            field=models.CharField(max_length=150, null=True, blank=True),
        ),
    ]
