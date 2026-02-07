from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone

#crear superusuario

class CustomUserManager(UserManager):
    def _normalize_cedula(self, cedula):
        if cedula in (None, ''):
            return None
        try:
            return int(cedula)
        except ValueError:
            raise ValueError("La cédula debe ser un número entero válido.")

    def _normalize_telefono(self, telefono):
        if telefono in (None, ''):
            return None
        try:
            return int(telefono)
        except ValueError:
            raise ValueError("El teléfono debe ser un número entero válido.")

    def create_user(self, username, email=None, cedula=None, telefono=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        cedula = self._normalize_cedula(cedula)
        telefono = self._normalize_telefono(telefono)
        user = self.model(username=username, email=email, cedula=cedula, telefono=telefono, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, cedula=None, telefono=None, security_question=None, security_answer=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        if extra_fields.get('is_staff') is not True or extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_staff=True and is_superuser=True.')
        cedula = self._normalize_cedula(cedula)
        telefono = self._normalize_telefono(telefono)
        # security_question/answer se pasan en extra_fields si vienen por createsuperuser
        if security_question is not None:
            extra_fields['security_question'] = security_question
        if security_answer is not None:
            extra_fields['security_answer'] = security_answer
        return self.create_user(username, email=email, cedula=cedula, telefono=telefono, password=password, **extra_fields)

#usuario personalizado

class User(AbstractUser):
    segundo_nombre = models.CharField("segundo nombre", max_length=150, blank=True)
    segundo_apellido = models.CharField("segundo apellido", max_length=150, blank=True)
    cedula = models.IntegerField("cedula", unique=True, null=True, blank=False)
    telefono = models.IntegerField("telefono", null=False, blank=False)
    security_question = models.CharField("pregunta de seguridad", max_length=255, null=False, blank=False)
    security_answer = models.CharField("respuesta de seguridad", max_length=255, null=False, blank=False)

    objects = CustomUserManager()
    REQUIRED_FIELDS = ['cedula', 'telefono', 'security_question', 'security_answer', 'email']

# modelo libros

# Opciones de edición (1ª ed. a 10ª ed.)
EDICION_CHOICES = [(i, f"{i}ª ed.") for i in range(1, 50)]
VOLUMEN_CHOICES = [(i, f"{i} v.") for i in range(1, 100)]


# Opciones de contenido del libro (para checkbox)
CONTENT_CHOICES = [
    ('ilustraciones', 'Ilustraciones'),
    ('mapas', 'Mapas'),
    ('graficos', 'Gráficos'),
    ('tablas', 'Tablas'),
    ('retratos', 'Retratos'),
    ('cuadros', 'Cuadros')
]

# Nueva tabla para las clasificaciones derivadas del prefijo de la cota
class Clasificacion(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label = models.CharField(max_length=200)

    def __str__(self):
        # Mostrar sólo la etiqueta legible (p. ej. "Anatomía humana")
        return self.label

class Libros(models.Model):
    cota = models.CharField(max_length=30, unique=True)
    titulo = models.CharField(max_length=100)
    subtitulo = models.CharField(max_length=100, null=True, blank=True)
    autor = models.CharField(max_length=100)
    co_autor = models.CharField(max_length=100, null=True, blank=True)
    fecha_publicacion = models.IntegerField(null=True, blank=True)
    editorial = models.CharField(max_length=100, null=True, blank=True)
    edicion = models.PositiveSmallIntegerField("edición", choices=EDICION_CHOICES, default=1)
    ubicacion_publicacion = models.CharField(max_length=100, null=True, blank=True)
    volumen = models.PositiveSmallIntegerField("volumen", choices=VOLUMEN_CHOICES, null=True, blank=True)
    paginas = models.IntegerField(null=True, blank=True)
    # cantidad disponible en stock
    cantidad = models.PositiveIntegerField("cantidad", default=1, help_text="Cantidad disponible en el inventario")
    serie = models.CharField(max_length=100, null=True, blank=True)
    numero_serie = models.IntegerField(null=True, blank=True)
    # datos_control eliminado
    numero_registro = models.IntegerField(null=True, blank=True)
    fecha_registro = models.DateField(null=True, blank=True)
    # Fecha y hora de creación automáticas
    fecha_creacion = models.DateField("fecha de creación", auto_now_add=True, null=True, blank=True)
    hora_creacion = models.TimeField("hora de creación", auto_now_add=True, null=True, blank=True)
    dimensiones = models.CharField(max_length=100, null=True, blank=True)
    portada = models.ImageField("portada", upload_to='covers/', null=True, blank=True, help_text="Imagen de portada (opcional)")
    contenido = models.CharField("contenido del libro", max_length=200, null=True, blank=True,
                                help_text="Seleccione los contenidos (guardado como valores separados por comas)")

    # Clasificación derivada del prefijo de la cota (se asigna automáticamente)
    classification = models.ForeignKey('Clasificacion', null=True, blank=True, on_delete=models.SET_NULL, related_name='libros')

    # relación opcional con la entrada del diccionario (si la cota corresponde a un código válido)
    dictionary_entry = models.ForeignKey('DictionaryEntry', null=True, blank=True, on_delete=models.SET_NULL, related_name='libros')

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING)
    # permitir inhabilitar libro sin borrar
    is_active = models.BooleanField('activo', default=True, help_text='Desmarcar para inhabilitar este libro sin borrarlo')
    
    def __str__(self):
        return f"{self.cota} - {self.titulo} ({self.edicion}ª ed.) por {self.autor} ({self.fecha_publicacion})"

    # Normalizar cota a mayúsculas siempre antes de guardar
    def save(self, *args, **kwargs):
        if self.cota:
            self.cota = self.cota.upper()
        # Si existe una entrada del diccionario vinculada, sincronizar la Clasificacion
        try:
            if getattr(self, 'dictionary_entry', None):
                # la entrada del diccionario puede ser un objeto o un id; intentar obtener el objeto
                de = self.dictionary_entry
                # si es un id (int), intentar obtener el objeto
                from django.core.exceptions import ObjectDoesNotExist
                if not hasattr(de, 'codigo'):
                    try:
                        de = DictionaryEntry.objects.get(pk=de)
                    except Exception:
                        de = None
                if de:
                    # Preferir derivar el prefijo (code) desde el campo 'codigo' del diccionario,
                    # p.ej. 'WG 123' -> 'WG', o 'W 123' -> 'W'. Esto es más fiable que parsear
                    # el campo 'clasificacion' libre que puede tener formatos variados.
                    code = None
                    label_value = None
                    try:
                        codigo_field = (de.codigo or '').strip()
                        if codigo_field:
                            code = codigo_field.split(None, 1)[0].upper()
                    except Exception:
                        code = None

                    # Si no pudimos obtener code desde codigo_field, usar el campo clasificacion como fallback
                    clas_label = (de.clasificacion or '').strip()
                    if not code and clas_label:
                        try:
                            code = clas_label.split('-', 1)[0].strip()
                        except Exception:
                            try:
                                code = clas_label.split()[0].strip()
                            except Exception:
                                code = None

                    # Determinar label legible para la clasificación: preferir la parte derecha después de '-' en clas_label
                    if clas_label and '-' in clas_label:
                        label_value = clas_label.split('-', 1)[1].strip()
                    elif clas_label:
                        label_value = clas_label
                    else:
                        # si no hay label en el campo, intentar inferir algo del codigo (se puede mejorar)
                        label_value = ''

                    from .models import Clasificacion as _Clasificacion
                    if code:
                        clas_obj, _ = _Clasificacion.objects.get_or_create(code=code, defaults={'label': label_value})
                        # Si existe pero no tiene label y tenemos label_value, actualizarlo
                        try:
                            if (not getattr(clas_obj, 'label', None)) and label_value:
                                clas_obj.label = label_value
                                clas_obj.save(update_fields=['label'])
                        except Exception:
                            pass
                        # asignar sólo si distinto
                        if self.classification_id != getattr(clas_obj, 'id', None):
                            self.classification = clas_obj
        except Exception:
            # no interrumpir el guardado por fallos en sincronización
            pass

        super().save(*args, **kwargs)

    @property
    def descripcion(self):
        return self.dictionary_entry.descripcion if self.dictionary_entry else ''

    @property
    def descripcion_en(self):
        return self.dictionary_entry.descripcion_en if self.dictionary_entry else ''

class AnalyticsEvent(models.Model):
    EVENT_VIEW = 'view'
    EVENT_ADD = 'add'
    EVENT_PDF = 'pdf'
    EVENT_LOGIN = 'login'
    EVENT_CHOICES = [
        (EVENT_VIEW, 'View'),
        (EVENT_ADD, 'Add'),
        (EVENT_PDF, 'PDF Print'),
        (EVENT_LOGIN, 'Login'),
    ]

    event_type = models.CharField(max_length=10, choices=EVENT_CHOICES)
    book = models.ForeignKey('Libros', null=True, blank=True, on_delete=models.SET_NULL, related_name='events')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.book_id or '-'} - {self.user_id or '-'} @ {self.timestamp}"

class UserSecurity(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='security')
    question = models.CharField(max_length=255)
    answer_hash = models.CharField(max_length=255)
    created_at = models.DateTimeField(default=timezone.now)

    def set_answer(self, raw_answer):
        self.answer_hash = make_password(raw_answer)

    def check_answer(self, raw_answer):
        return check_password(raw_answer, self.answer_hash)

    def __str__(self):
        return f"Security for {self.user_id}"


class Prestamo(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_RETURNED = 'returned'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Activo'),
        (STATUS_RETURNED, 'Devuelto'),
    ]

    book = models.ForeignKey('Libros', on_delete=models.CASCADE, related_name='prestamos')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    cantidad = models.PositiveIntegerField(default=1)
    # Datos de la persona que recibe el préstamo
    receiver_cedula = models.CharField("cédula receptor", max_length=32, null=True, blank=True)
    receiver_first_name = models.CharField("nombre receptor", max_length=150, null=True, blank=True)
    receiver_last_name = models.CharField("apellido receptor", max_length=150, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    # Fecha y hora en que el préstamo fue aprobado/confirmado (timezone-aware)
    approved_at = models.DateTimeField(null=True, blank=True)
    # Fecha y hora en que el préstamo fue devuelto
    returned_at = models.DateTimeField(null=True, blank=True)
    # Reporte y puntuaciones al devolver
    return_report = models.TextField('reporte devolución', null=True, blank=True)
    return_book_rating = models.PositiveSmallIntegerField('puntuación libro', null=True, blank=True)
    return_receiver_rating = models.PositiveSmallIntegerField('puntuación receptor', null=True, blank=True)

    def __str__(self):
        return f"Prestamo {self.book_id} x{self.cantidad} ({self.status}) by {self.user_id or '-'}"


# Entradas del diccionario importadas desde CSV
class DictionaryEntry(models.Model):
    codigo = models.CharField(max_length=200, unique=True, db_index=True)
    descripcion = models.TextField(blank=True)
    descripcion_en = models.TextField(blank=True)
    # nuevo campo para clasificacion
    clasificacion = models.CharField(max_length=200, blank=True)
    # permitir inhabilitar entrada del diccionario
    is_active = models.BooleanField('activo', default=True, help_text='Desmarcar para inhabilitar esta entrada del diccionario')

    class Meta:
        ordering = ['codigo']

    def __str__(self):
        return self.codigo