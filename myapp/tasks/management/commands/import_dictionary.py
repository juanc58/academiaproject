import csv
import os
from django.core.management.base import BaseCommand
from tasks.models import DictionaryEntry

class Command(BaseCommand):
    help = 'Carga datos desde diccionario.csv a la tabla DictionaryEntry'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='Ruta al archivo CSV')

    def handle(self, *args, **options):
        file_path = options['csv_file']
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f'Archivo no encontrado: {file_path}'))
            return

        with open(file_path, mode='r', encoding='utf-8') as f:
            # Según la previsualización, el delimitador es ';'
            reader = csv.DictReader(f, delimiter=';')
            count = 0
            for row in reader:
                codigo = row.get('codigo', '').strip()
                if not codigo:
                    continue
                
                # Crear o actualizar la entrada
                obj, created = DictionaryEntry.objects.update_or_create(
                    codigo=codigo,
                    defaults={
                        'descripcion': row.get('descripcion', ''),
                        'descripcion_en': row.get('descripcion_en', ''),
                        'clasificacion': row.get('clasificacion', ''),
                        'is_active': True
                    }
                )
                count += 1
                if count % 500 == 0:
                    self.stdout.write(f'Procesados {count} registros...')

            self.stdout.write(self.style.SUCCESS(f'Éxito: Se cargaron/actualizaron {count} registros en DictionaryEntry.'))
