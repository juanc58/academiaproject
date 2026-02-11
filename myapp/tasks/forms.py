from .models import Libros, CONTENT_CHOICES, DictionaryEntry
import re
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms as djforms

#usuario personalizado

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    segundo_nombre = forms.CharField(max_length=150, required=False)
    segundo_apellido = forms.CharField(max_length=150, required=False)
    cedula = forms.IntegerField(required=True)
    telefono = forms.IntegerField(required=True)
    security_question = forms.CharField(max_length=255, required=True)
    security_answer = forms.CharField(max_length=255, required=True)
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "cedula" , "first_name", "segundo_nombre", "last_name", "segundo_apellido", "telefono", "email", "security_question", "security_answer", "is_staff")


class UserEditForm(djforms.ModelForm):
    class Meta:
        model = User
        fields = ['username','first_name','segundo_nombre','last_name','segundo_apellido','cedula','telefono','email','is_active','is_staff','is_superuser']


class DictionaryEntryForm(djforms.ModelForm):
    class Meta:
        model = DictionaryEntry
        fields = ['codigo','descripcion','descripcion_en','clasificacion','is_active']

#libros modelo - correccion de formulario

class TaskForm(forms.ModelForm):
    # campos parciales de cota (restaurados)
    cota_part1 = forms.CharField(max_length=10, required=True , label='Cota Parte 1')
    cota_part2 = forms.CharField(max_length=20, required=True , label='Cota Parte 2')
    # ahora obligatorios (según solicitud)
    cota_part3 = forms.CharField(max_length=10, required=True , label='Cota Parte 3')
    cota_part4 = forms.CharField(max_length=20, required=True, label='Cota Parte 4',
        help_text="La cota se compone en una combinacion de letras y numeros , donde el campo 1 y 2 provienen de la clasificacion del Libro en el area de la salud (Libro nacional de clasificacion de la medicina , anexado en la seccion diccionario) y el campo 3 y 4 son especificaciones del nombre del autor expresado en una letra y entre 1 a 3 numeros (tabla cutter/sanborn)")

    # nuevo campo de checkboxes para contenido del libro
    contenido = forms.MultipleChoiceField(
        choices=CONTENT_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Contenido del libro'
    )

    # fecha_registro: usar widget HTML5 date para mostrar calendario en navegadores compatibles
    fecha_registro = forms.DateField(required=True, label='Fecha de registro', widget=forms.DateInput(attrs={'type': 'date'}))

    # El campo 'materias' se reemplaza por clasificación asignada automáticamente
    cantidad = forms.IntegerField(required=False, min_value=0, initial=1, label='Cantidad disponible', help_text='Número de ejemplares disponibles')

    class Meta:
        model = Libros
        # excluir el campo cota y el usuario del ModelForm para manejarlo manualmente
        exclude = ['cota', 'user']
        fields = '__all__'
        help_texts = {
            'cota': "p.ej. 'A 123 C 111' — letras y números separados por espacios.",
            'titulo': "Escribir el título completo tal como figura en el libro y tomar en consideracion el subtitulo se ubica en el campo siguiente a este",
            'subtitulo' : "Escribir el subtítulo completo tal como figura en el libro (si lo tiene).",
            'autor': "El autor debe escribirse Apellidos, Nombres ej: García, Juan (Formato APA).",
            'editorial': "Nombre de la editorial (si lo tiene).",
            'fecha_publicacion': "Año de publicación: 4 dígitos, ej. 2020.",
            'ubicacion_publicacion': "Ciudad donde se publicó el libro (si lo tiene).",
            'volumen': "Número de volumen (si es parte de una serie o colección).",
            'co_autor': 'Coautor(es) del libro (si aplica).',
            'numero_registro': 'Número de registro interno (entero).',
            'fecha_registro': 'Fecha de registro del ejemplar en el sistema.',
            'edicion': "Número de edición (1ª, 2ª, etc.)",
            'serie': "Nombre de la serie o colección (si aplica).",
            'numero_serie': "Número dentro de la serie (si aplica).",
            'dimensiones': "Dimensiones físicas del libro (si se desea).",
            'paginas': "Número total de páginas (si se desea).",
            # 'especialidad' y 'datos_control' eliminados del modelo
            
            'portada': "Imagen de portada (opcional).",
            'cantidad': 'Número de ejemplares disponibles en stock (entero no negativo).',
            }

    def __init__(self, *args, **kwargs):
        # permitir precargar valores derivados de la instancia (especialmente para edición)
        instance = kwargs.get('instance', None)
        super().__init__(*args, **kwargs)
        # Poblar cota_part1 como ChoiceField con prefijos únicos del diccionario (si hay datos)
        try:
            prefixes = set()
            for code in DictionaryEntry.objects.values_list('codigo', flat=True).distinct():
                if not code:
                    continue
                parts = str(code).strip().split(None, 1)
                if parts:
                    prefixes.add(parts[0].upper())
            choices = [('', 'Seleccione prefijo')] + [(p, p) for p in sorted(prefixes)]
            # reemplazar el campo por ChoiceField para mostrar dropdown
            self.fields['cota_part1'] = forms.ChoiceField(choices=choices, required=True, label='Cota Parte 1')
        except Exception:
            # si falla al obtener prefijos, dejamos el CharField original
            pass

        if instance is not None:
            # contenido en la instancia normalmente se guarda como cadena separada por comas
            contenido_val = getattr(instance, 'contenido', '') or ''
            if contenido_val:
                try:
                    # limpiar espacios alrededor de cada valor (p.ej. 'mapas' vs ' mapas')
                    initial_list = [v.strip() for v in contenido_val.split(',') if v.strip()]
                    self.fields['contenido'].initial = initial_list
                    # también asignar a self.initial para asegurar que CheckboxSelectMultiple muestre los checks al renderizar
                    if not getattr(self, 'is_bound', False):
                        try:
                            self.initial['contenido'] = initial_list
                        except Exception:
                            pass
                except Exception:
                    # si falla, dejar como está
                    pass

                # durante edición, si la instancia tiene classification, podríamos mostrarla (readonly en la plantilla)
                pass

            # si hay instancia y valor de cota, descomponer en partes para inicializar el formulario
            try:
                if getattr(instance, 'cota', None):
                    parts = instance.cota.split() if instance.cota else []
                    if len(parts) >= 1: self.initial['cota_part1'] = parts[0]
                    if len(parts) >= 2: self.initial['cota_part2'] = parts[1]
                    if len(parts) >= 3: self.initial['cota_part3'] = parts[2]
                    if len(parts) >= 4: self.initial['cota_part4'] = parts[3]
            except Exception:
                pass

        # asegurar que numero_registro sea obligatorio en el formulario de creación/edición
        try:
            self.fields['numero_registro'].required = True
        except Exception:
            pass

    def clean_cota(self):
        # mantenemos por compatibilidad si alguien usa clean_cota; preferimos usar partes
        v = self.cleaned_data.get('cota', '') or ''
        return v.strip().upper()

    def clean_cota_part1(self):
        v = self.cleaned_data.get('cota_part1', '') or ''
        v = v.strip()
        if not v:
            raise forms.ValidationError('El primer recuadro de la cota es obligatorio.')
        if not v.replace(' ', '').isalpha():
            # permitir espacios internos en algunos prefijos, pero exigir letras en general
            raise forms.ValidationError('El primer recuadro de la cota debe contener solo letras.')
        return v.upper()

    def clean_cota_part2(self):
        v = (self.cleaned_data.get('cota_part2') or '').strip()
        if not v:
            raise forms.ValidationError('El segundo recuadro de la cota es obligatorio.')
        return v

    def clean_cota_part3(self):
        v = (self.cleaned_data.get('cota_part3') or '').strip()
        if v == '':
            raise forms.ValidationError('El tercer recuadro de la cota es obligatorio.')
        if not (v.isalpha() and len(v) <= 5):
            raise forms.ValidationError('El tercer recuadro de la cota debe contener solo letras (máx 5).')
        return v.upper()

    def clean_cota_part4(self):
        v = (self.cleaned_data.get('cota_part4') or '').strip()
        if v == '':
            raise forms.ValidationError('El cuarto recuadro de la cota es obligatorio.')
        if not (v.replace(' ', '').isdigit() and len(v) <= 10):
            raise forms.ValidationError('El cuarto recuadro de la cota debe contener solo números (máx 10).')
        return v

    def clean(self):
        cleaned = super().clean()
        # validar numero_registro y fecha_registro como obligatorios
        nr = cleaned.get('numero_registro')
        fr = cleaned.get('fecha_registro')
        if nr in (None, ''):
            self.add_error('numero_registro', 'El número de registro es obligatorio.')
        else:
            try:
                cleaned['numero_registro'] = int(nr)
            except Exception:
                self.add_error('numero_registro', 'El número de registro debe ser un entero válido.')

        if fr in (None, ''):
            self.add_error('fecha_registro', 'La fecha de registro es obligatoria.')

        # validar que la combinacion de cota_part1 + ' ' + cota_part2 exista en DictionaryEntry.codigo
        p1 = cleaned.get('cota_part1', '') or ''
        p2 = cleaned.get('cota_part2', '') or ''
        if p1 and p2:
            # Normalizar: colapsar espacios y forzar mayúsculas en las partes
            p1_norm = re.sub(r"\s+", " ", p1.strip()).upper()
            p2_norm = re.sub(r"\s+", " ", p2.strip()).upper()
            combined = f"{p1_norm} {p2_norm}".strip()
            try:
                # Intentos de búsqueda en orden de preferencia
                de = None
                # 1) coincidencia exacta (case-insensitive)
                de = DictionaryEntry.objects.filter(codigo__iexact=combined).first()
                # 2) intentar startswith (p.ej. el código en DB puede tener sufijos adicionales)
                if not de:
                    de = DictionaryEntry.objects.filter(codigo__istartswith=combined).first()
                # 3) intento más flexible: contiene
                if not de:
                    de = DictionaryEntry.objects.filter(codigo__icontains=combined).first()

                if not de:
                    # si no hay coincidencia, marcar error en ambos campos
                    self.add_error('cota_part1', 'La combinación de cota no corresponde a ningún código válido en el diccionario.')
                    self.add_error('cota_part2', 'La combinación de cota no corresponde a ningún código válido en el diccionario.')
                else:
                    # guardar la entrada para usarla en save()
                    self._matched_dictionary_entry = de
                    # además actualizar cleaned para que quede normalizado
                    cleaned['cota_part1'] = p1_norm
                    cleaned['cota_part2'] = p2_norm
            except Exception:
                pass

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        # componer cota uniendo solo las partes no vacías con un único espacio
        p1 = (self.cleaned_data.get('cota_part1') or '').strip()
        p2 = (self.cleaned_data.get('cota_part2') or '').strip()
        p3 = (self.cleaned_data.get('cota_part3') or '').strip()
        p4 = (self.cleaned_data.get('cota_part4') or '').strip()
        parts = [p for p in [p1, p2, p3, p4] if p != '']
        instance.cota = ' '.join(parts).upper()
        # asignar la entrada del diccionario encontrada (si existe) incluso si commit=False
        try:
            matched = getattr(self, '_matched_dictionary_entry', None)
            if matched:
                instance.dictionary_entry = matched
        except Exception:
            pass

        # contenido como cadena
        contenido_list = self.cleaned_data.get('contenido', [])
        # normalizar: strip y filtrar solo valores permitidos por CONTENT_CHOICES
        allowed = {c[0] for c in CONTENT_CHOICES}
        try:
            clean_vals = [v.strip() for v in contenido_list if v and v.strip() in allowed]
        except Exception:
            clean_vals = [v for v in contenido_list if v]
        instance.contenido = ','.join(clean_vals) if clean_vals else ''

        # cantidad (stock)
        try:
            cantidad_val = self.cleaned_data.get('cantidad')
            if cantidad_val is not None:
                instance.cantidad = int(cantidad_val)
        except Exception:
            # ignore invalid and leave default
            pass

        # no vinculamos DictionaryEntry automáticamente

        # no tocar relaciones M2M si commit=False; dejar pendientes para la vista
        if commit:
            instance.save()
            # si el formulario maneja M2M nativamente, save_m2m() lo aplicará
            try:
                self.save_m2m()
            except Exception:
                pass

            # ya no manejamos materias manualmente; la classification se asigna arriba
        else:
            # ya no hay manejo de materias pendientes
            pass

        return instance


