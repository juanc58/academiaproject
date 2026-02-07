from django.core.management.base import BaseCommand
from tasks.models import Clasificacion

CLASS_LIST = [
"QS-Anatomía Humana",
"QT-Fisiología",
"QU-Bioquímica. Biología Celular y Genética",
"QV-Farmacología",
"QW-Microbiología. Inmunología",
"QX-Parasitología. Vectores de Enfermedades",
"QY-Patología Clínica de Laboratorio",
"QZ-Patología",
"W-Medicina General. Profesiones de la Salud",
"WA-Salud Pública",
"WB-Práctica de la Medicina",
"WC-Enfermedades Transmisibles",
"WD-Medicina en Entornos Selectos",
"WE-Sistema Musculoesquelético",
"WF-Sistema Respiratorio",
"WG-Sistema Cardiovascular",
"WH-Sistemas Hemático y Linfático",
"WI-Sistema Digestivo",
"WJ-Sistema Urogenital",
"WK-Sistema Endocrino",
"WL-Sistema Nervioso",
"WM-Psiquiatría",
"WN-Radiología. Diagnóstico por Imagen",
"WO-Cirugía",
"WP-Medicina Reproductiva",
"WQ-Obstetricia. Embarazo",
"WR-Dermatología. Sistema Tegumentario",
"WS-Pediatría",
"WT-Geriatría",
"WU-Odontología. Cirugía Oral",
"WV-Otorrinolaringología",
"WW-Oftalmología",
"WX-Hospitales y Otros Centros de Salud",
"WY-Enfermería",
"WZ-Historia de la Medicina. Miscelánea Médica",
]

class Command(BaseCommand):
    help = 'Importa la lista fija de clasificaciones en la tabla Clasificacion'

    def handle(self, *args, **options):
        created = 0
        for item in CLASS_LIST:
            parts = item.split('-', 1)
            code = parts[0].strip() if parts else item.strip()
            label = parts[1].strip() if len(parts) > 1 else ''
            obj, was_created = Clasificacion.objects.get_or_create(code=code, defaults={'label': label or item})
            if not was_created and obj.label != (label or item):
                obj.label = label or item
                obj.save()
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Clasificaciones importadas/actualizadas. Nuevas: {created}'))
