import csv
from django.core.management.base import BaseCommand, CommandError
from tasks.models import DictionaryEntry
from django.db import transaction


class Command(BaseCommand):
    help = 'Importa un archivo CSV al modelo DictionaryEntry. Uso: python manage.py import_dictionary <ruta_al_csv>'

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str, help='Ruta al archivo CSV a importar')
        parser.add_argument('--codigo-col', type=str, default='codigo', help='Columna para codigo (default: codigo)')
        parser.add_argument('--desc-col', type=str, default='descripcion', help='Columna para descripcion (default: descripcion)')
        parser.add_argument('--desc-en-col', type=str, default='descripcion_en', help='Columna para descripcion_en (default: descripcion_en)')
        parser.add_argument('--clasificacion-col', type=str, default='clasificacion', help='Columna para clasificacion (default: clasificacion)')

    def sniff_dialect(self, path):
        # intenta detectar delimitador (coma o punto y coma) leyendo una muestra y probando varias codificaciones
        sample = None
        for enc in ('utf-8', 'cp1252', 'latin-1'):
            try:
                with open(path, 'r', encoding=enc, errors='strict') as f:
                    sample = f.read(8192)
                break
            except Exception:
                sample = None
                continue
        if not sample:
            # fallback: leer en binario y decode laxamente
            with open(path, 'rb') as f:
                sample = f.read(8192).decode('utf-8', errors='replace')
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=',;')
            return dialect
        except csv.Error:
            return csv.get_dialect('excel')

    def handle(self, *args, **options):
        path = options['csv_path']
        codigo_col = options['codigo_col']
        desc_col = options['desc_col']
        desc_en_col = options['desc_en_col']
        clas_col = options.get('clasificacion_col', 'clasificacion')
        try:
            dialect = self.sniff_dialect(path)
            # intentar varias codificaciones hasta que una funcione
            csvfile = None
            for enc in ('utf-8', 'cp1252', 'latin-1'):
                try:
                    csvfile = open(path, newline='', encoding=enc)
                    break
                except UnicodeDecodeError:
                    # probar siguiente encoding
                    try:
                        if csvfile:
                            csvfile.close()
                    except Exception:
                        pass
                    csvfile = None
                    continue
            if csvfile is None:
                # abrir en modo permissive como último recurso
                csvfile = open(path, newline='', encoding='utf-8', errors='replace')

            reader = csv.DictReader(csvfile, dialect=dialect)
            entries = []
            with transaction.atomic():
                for row in reader:
                    # mapear columnas con varios posibles encabezados
                    codigo = (row.get(codigo_col) or row.get('codigo') or row.get('Codigo') or '').strip()
                    descripcion = (row.get(desc_col) or row.get('descripcion') or row.get('Descripcion') or '').strip()
                    descripcion_en = (row.get(desc_en_col) or row.get('descripcion_en') or row.get('Descripcion_en') or '').strip()
                    clasificacion = (row.get(clas_col) or row.get('clasificacion') or row.get('Clasificacion') or '').strip()
                    if not codigo:
                        # saltar filas sin codigo
                        continue
                    obj, created = DictionaryEntry.objects.update_or_create(
                        codigo=codigo,
                        defaults={'descripcion': descripcion, 'descripcion_en': descripcion_en, 'clasificacion': clasificacion}
                    )
                    entries.append((obj, created))

            try:
                csvfile.close()
            except Exception:
                pass

            self.stdout.write(self.style.SUCCESS(f'Importadas/actualizadas {len(entries)} entradas desde {path}'))
        except FileNotFoundError:
            raise CommandError(f'Archivo no encontrado: {path}')
        except Exception as e:
            raise CommandError(str(e))
