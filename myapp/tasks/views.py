from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model, authenticate, login as auth_login, logout
from django.db import IntegrityError
from .forms import TaskForm, CustomUserCreationForm, UserEditForm, DictionaryEntryForm
from .models import Libros, Clasificacion, AnalyticsEvent, UserSecurity, DictionaryEntry
from .models import Prestamo
from django.db.models import Q
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncMonth
import datetime
from django.core.paginator import Paginator
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import UserSecurity  # si usaste otro nombre ajústalo
from django.http import HttpResponse
from django.http import JsonResponse
from django.utils import timezone
from django.template.loader import render_to_string
import io
from reportlab.lib.pagesizes import A4, landscape, A5
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

User = get_user_model()

def _superuser_required(view_func):
    from functools import wraps
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_superuser:
            messages.error(request, 'Acceso denegado: se requiere ser administrador.')
            return redirect('index')
        return view_func(request, *args, **kwargs)
    return _wrapped

@_superuser_required
def admin_panel(request):
    return render(request, 'admin/panel.html')

@_superuser_required
def admin_users(request):
    q = request.GET.get('q', '').strip()
    qs = User.objects.all().order_by('-is_superuser', 'username')
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(cedula__icontains=q))
    paginator = Paginator(qs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'admin/users_list.html', {'users': page_obj, 'q': q})

@_superuser_required
def admin_user_add(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Usuario creado')
            return redirect('admin_users')
    else:
        form = CustomUserCreationForm()
    return render(request, 'admin/user_form.html', {'form': form, 'create': True})

@_superuser_required
def admin_user_edit(request, pk):
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=u)
        if form.is_valid():
            # validar cambio de contraseña opcional (admin puede resetear sin conocer la actual)
            new1 = request.POST.get('new_password1', '').strip()
            new2 = request.POST.get('new_password2', '').strip()
            if (new1 or new2):
                if new1 != new2:
                    form.add_error(None, 'Las nuevas contraseñas no coinciden.')
                    return render(request, 'admin/user_form.html', {'form': form, 'create': False, 'user_obj': u})
                if len(new1) < 8 or not any(char.isdigit() for char in new1):
                    form.add_error(None, 'La contraseña debe tener al menos 8 caracteres y contener al menos un número.')
                    return render(request, 'admin/user_form.html', {'form': form, 'create': False, 'user_obj': u})

            # guardar cambios del formulario
            user_obj = form.save()

            # aplicar nueva contraseña si fue provista
            if new1:
                user_obj.set_password(new1)
                user_obj.save()

            messages.success(request, 'Usuario actualizado')
            return redirect('admin_users')
    else:
        form = UserEditForm(instance=u)
    return render(request, 'admin/user_form.html', {'form': form, 'create': False, 'user_obj': u})

@_superuser_required
def admin_user_delete(request, pk):
    u = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        u.delete()
        messages.success(request, 'Usuario eliminado')
        return redirect('admin_users')
    return render(request, 'admin/user_confirm_delete.html', {'user_obj': u})


@_superuser_required
def admin_books(request):
    q = request.GET.get('q', '').strip()
    qs = Libros.objects.all().order_by('cota')
    if q:
        qs = qs.filter(Q(cota__icontains=q) | Q(titulo__icontains=q) | Q(autor__icontains=q) | Q(co_autor__icontains=q))
    paginator = Paginator(qs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'admin/books_list.html', {'books': page_obj, 'q': q})

@_superuser_required
def admin_book_add(request):
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES)
        if form.is_valid():
            book = form.save(commit=False)
            book.user = request.user
            # asegurar que el libro quede activo al crearlo
            try:
                book.is_active = True
            except Exception:
                pass
            book.save()
            form.save_m2m()
            messages.success(request, 'Libro creado')
            return redirect('admin_books')
    else:
        form = TaskForm()
    return render(request, 'admin/book_form.html', {'form': form, 'create': True})

@_superuser_required
def admin_book_edit(request, pk):
    book = get_object_or_404(Libros, pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, 'Libro actualizado')
            return redirect('admin_books')
    else:
        form = TaskForm(instance=book)
    return render(request, 'admin/book_form.html', {'form': form, 'create': False, 'book': book})

@_superuser_required
def admin_book_delete(request, pk):
    book = get_object_or_404(Libros, pk=pk)
    if request.method == 'POST':
        book.delete()
        messages.success(request, 'Libro eliminado')
        return redirect('admin_books')
    return render(request, 'admin/book_confirm_delete.html', {'book': book})


@_superuser_required
def admin_dictionary(request):
    q = request.GET.get('q', '').strip()
    qs = DictionaryEntry.objects.all().order_by('codigo')
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q) | Q(descripcion_en__icontains=q))
    paginator = Paginator(qs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    classification_list = None
    return render(request, 'admin/dictionary_list.html', {'entries': page_obj, 'q': q, 'classification_list': classification_list})

@_superuser_required
def admin_dictionary_add(request):
    if request.method == 'POST':
        form = DictionaryEntryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entrada agregada')
            return redirect('admin_dictionary')
    else:
        form = DictionaryEntryForm()
    return render(request, 'admin/dictionary_form.html', {'form': form, 'create': True})

@_superuser_required
def admin_dictionary_edit(request, pk):
    e = get_object_or_404(DictionaryEntry, pk=pk)
    if request.method == 'POST':
        form = DictionaryEntryForm(request.POST, instance=e)
        if form.is_valid():
            form.save()
            messages.success(request, 'Entrada actualizada')
            return redirect('admin_dictionary')
    else:
        form = DictionaryEntryForm(instance=e)
    return render(request, 'admin/dictionary_form.html', {'form': form, 'create': False, 'entry': e})

@_superuser_required
def admin_dictionary_delete(request, pk):
    e = get_object_or_404(DictionaryEntry, pk=pk)
    if request.method == 'POST':
        e.delete()
        messages.success(request, 'Entrada eliminada')
        return redirect('admin_dictionary')
    return render(request, 'admin/dictionary_confirm_delete.html', {'entry': e})

#INDEX

def index(request):
    return render(request, 'index.html')


############### Usuarios ###############

#REGISTRO


def signup(request):
    if request.method == 'GET':
        return render(request, 'signup.html', {
            'form': CustomUserCreationForm()
        })
    else:
        # usar instancia enlazada para conservar datos en la plantilla si hay errores
        form = CustomUserCreationForm(request.POST)
        required_fields = [
            'username', 'password1', 'password2', 'email',
            'first_name', 'last_name', 'cedula', 'telefono',
            'security_question', 'security_answer'
        ]

        field_errors = {
            'username': 'El nombre de usuario es obligatorio.',
            'password1': 'La contraseña es obligatoria.',
            'password2': 'Debe confirmar la contraseña.',
            'email': 'El correo electrónico es obligatorio.',
            'first_name': 'El primer nombre es obligatorio.',
            'last_name': 'El primer apellido es obligatorio.',
            'cedula': 'La cédula es obligatoria.',
            'telefono': 'El teléfono es obligatorio.',
            'security_question': 'La pregunta de seguridad es obligatoria.',
            'security_answer': 'La respuesta de seguridad es obligatoria.'
        }
        for field in required_fields:
            if not request.POST.get(field):
                return render(request, 'signup.html', {
                    'form': form,
                    'error': field_errors.get(field, f'El campo {field} es obligatorio.')
                })

        username = request.POST['username']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        cedula = request.POST['cedula']
        telefono = request.POST['telefono']
        email = request.POST['email']

        # Validaciones sencillas de formato
        if not cedula.isdigit():
            return render(request, 'signup.html', {
                'form': form,
                'error': 'La cédula solo debe contener números (sin letras ni espacios).'
            })

        if not telefono.isdigit():
            return render(request, 'signup.html', {
                'form': form,
                'error': 'El teléfono solo debe contener números (sin letras ni espacios).'
            })

        if '@' not in email:
            return render(request, 'signup.html', {
                'form': form,
                'error': 'El correo electrónico debe contener "@".'
            })

        # Chequeos adicionales
        if User.objects.filter(username=username).exists():
            return render(request, 'signup.html', {
                'form': form,
                'error': 'Usuario ya existe, por favor elija otro nombre de usuario'
            })

        if User.objects.filter(cedula=cedula).exists():
            return render(request, 'signup.html', {
                'form': form,
                'error': 'La cédula ya está registrada, por favor verifique o ingrese otra.'
            })

        if len(username) < 8:
            return render(request, 'signup.html', {
                'form': form,
                'error': 'El nombre de usuario debe tener al menos 8 caracteres.'
            })

        if len(password1) < 8 or not any(char.isdigit() for char in password1):
            return render(request, 'signup.html', {
                'form': form,
                'error': 'La contraseña debe tener al menos 8 caracteres y contener al menos un número.'
            })

        if password1 != password2:
            return render(request, 'signup.html', {
                'form': form,
                'error': 'Contraseñas no coinciden, por favor intente de nuevo'
            })

        try:
            user = User.objects.create_user(
                username=username,
                password=password1,
                email=email,
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                cedula=cedula,
                segundo_nombre=request.POST.get('segundo_nombre', ''),
                segundo_apellido=request.POST.get('segundo_apellido', ''),
                telefono=telefono,
                security_question=request.POST.get('security_question', ''),
                security_answer=request.POST.get('security_answer', '')
            )
            user.save()
            auth_login(request, user)
            return redirect('index')

        except IntegrityError:
            return render(request, 'signup.html', {
                'form': form,
                'error': 'Error al crear el usuario, por favor intente de nuevo.'
            })


#LOGIN

def signin(request):
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'GET':
        form = AuthenticationForm()
        return render(request, 'signin.html', {'form': form, 'next': next_url})
    else:
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            # registrar login
            try:
                AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EVENT_LOGIN, user=user)
            except Exception:
                pass
            if next_url:
                return redirect(next_url)
            return redirect('index')
        else:
            return render(request, 'signin.html', {'form': form, 'next': next_url, 'error': 'Usuario o contraseña incorrectos.'})


#LOGOUT

def signout(request):
    logout(request)
    return redirect('index')




#EDITAR USUARIO

@login_required
def edit_user(request):
    user = request.user
    if request.method == 'POST':
        # leer y normalizar campos
        email = request.POST.get('email', user.email).strip()
        first_name = request.POST.get('first_name', user.first_name).strip()
        segundo_nombre = request.POST.get('segundo_nombre', getattr(user, 'segundo_nombre', '')).strip()
        last_name = request.POST.get('last_name', user.last_name).strip()
        segundo_apellido = request.POST.get('segundo_apellido', getattr(user, 'segundo_apellido', '')).strip()
        telefono = request.POST.get('telefono', getattr(user, 'telefono', '')).strip()

        # Validaciones de seguridad: telefono solo dígitos enteros; email debe contener @ y terminar en .com
        if telefono and not telefono.isdigit():
            return render(request, 'edit_user.html', {
                'user': user,
                'error': 'El número telefónico solo puede contener dígitos (sin espacios ni símbolos).'
            })

        if email and ('@' not in email or not email.lower().endswith('.com')):
            return render(request, 'edit_user.html', {
                'user': user,
                'error': 'El correo electrónico debe contener "@" y terminar en ".com".'
            })

        # asignar valores ya validados
        user.email = email
        user.first_name = first_name
        user.segundo_nombre = segundo_nombre
        user.last_name = last_name
        user.segundo_apellido = segundo_apellido
        user.telefono = telefono

        # seguridad / contraseña (mantener la lógica previa)
        modify_security = request.POST.get('modifySecurity') == 'on'
        new1 = new2 = ''
        if modify_security:
            current_password = request.POST.get('current_password', '')
            if not user.check_password(current_password):
                # contraseña actual incorrecta
                return render(request, 'edit_user.html', {'user': user, 'error': 'Contraseña actual incorrecta.'})
            # cambiar contraseña si se indicó
            new1 = request.POST.get('new_password1', '')
            new2 = request.POST.get('new_password2', '')
            if new1 or new2:
                if new1 != new2:
                    return render(request, 'edit_user.html', {'user': user, 'error': 'Las nuevas contraseñas no coinciden.'})
                if len(new1) < 6:
                    return render(request, 'edit_user.html', {'user': user, 'error': 'La nueva contraseña debe tener al menos 6 caracteres.'})
                user.set_password(new1)

            # actualizar pregunta/resp. de seguridad (usar modelo UserSecurity)
            question = request.POST.get('security_question', '').strip()
            answer = request.POST.get('security_answer', '').strip()
            if question and answer:
                sec, created = UserSecurity.objects.get_or_create(user=user)
                sec.question = question
                sec.set_answer(answer)  # método que hasheará la respuesta (según modelo sugerido)
                sec.save()
            else:
                # opcional: si quieren permitir borrar pregunta, gestionar aquí
                pass

        # guardar cambios del usuario
        user.save()

        # si cambiamos la contraseña, hay que re-login opcional:
        if modify_security and (new1 and new1 == new2):
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)  # mantiene sesión activa tras cambiar contraseña

        return render(request, 'edit_user.html', {'user': user, 'success': 'Perfil actualizado correctamente.'})

    # GET
    return render(request, 'edit_user.html', {'user': user})




#RECUPERAR CONTRASEÑA - RECOVERY

def recovery(request):
    if request.method == 'GET':
        return render(request, 'recovery.html')

    cedula = request.POST.get('cedula', '').strip()
    if not cedula or not cedula.isdigit():
        return render(request, 'recovery.html', {
            'error': 'La cédula solo debe contener números (sin letras ni espacios).'
        })

    user = User.objects.filter(cedula=cedula).first()
    if not user:
        return render(request, 'recovery.html', {
            'error': 'No se encontró usuario para la cédula indicada.'
        })

    # Si se envía nuevo password, procesarlo
    password1 = request.POST.get('password1', '').strip()
    password2 = request.POST.get('password2', '').strip()
    if password1 or password2:
        if password1 != password2:
            return render(request, 'recovery.html', {
                'cedula': cedula,
                'username': user.username,
                'show_change': True,
                'error': 'Las contraseñas no coinciden.'
            })
        if len(password1) < 8 or not any(char.isdigit() for char in password1):
            return render(request, 'recovery.html', {
                'cedula': cedula,
                'username': user.username,
                'show_change': True,
                'error': 'La contraseña debe tener al menos 8 caracteres y contener al menos un número.'
            })
        user.set_password(password1)
        user.save()
        return redirect('signin')

    # Si se envía respuesta a la pregunta de seguridad, verificarla
    if request.POST.get('security_answer'):
        answer = request.POST.get('security_answer', '').strip()
        if answer == (user.security_answer or ''):
            return render(request, 'recovery.html', {
                'cedula': cedula,
                'username': user.username,
                'show_change': True
            })
        else:
            return render(request, 'recovery.html', {
                'cedula': cedula,
                'security_question': user.security_question,
                'show_questions': True,
                'error': 'Pregunta o respuesta de seguridad incorrecta.'
            })

    # Mostrar la pregunta de seguridad por defecto
    return render(request, 'recovery.html', {
        'cedula': cedula,
        'security_question': user.security_question,
        'show_questions': True
    })


def change_password(request):
    if request.method == 'GET':
        return render(request, 'change_password.html')
    else:
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        cedula = request.POST.get('cedula')

        if not password1 or not password2:
            return render(request, 'change_password.html', {
                'error': 'Debe ingresar y confirmar la nueva contraseña.'
            })

        if password1 != password2:
            return render(request, 'change_password.html', {
                'error': 'Las contraseñas no coinciden.'
            })

        if len(password1) < 8 or not any(char.isdigit() for char in password1):
            return render(request, 'change_password.html', {
                'error': 'La contraseña debe tener al menos 8 caracteres y contener al menos un número.'
            })

        user = User.objects.filter(cedula=cedula).first()
        if not user:
            return render(request, 'change_password.html', {
                'error': 'No se encontró usuario para cambiar la contraseña.'
            })

        user.set_password(password1)
        user.save()
        return redirect('signin')
    
    
 ##########################   LIBROS   ##########################
 
 
#VER Y BUSCAR LIBROS

def tasks(request):
    q = request.GET.get('q', '').strip()
    materia_id = request.GET.get('materia', '').strip()

    # nuevos parámetros
    sort_by = request.GET.get('sort_by', '').strip()  # autor, titulo, editorial, ubicacion_publicacion, fecha_publicacion
    order = request.GET.get('order', 'asc').strip()   # asc or desc
    filter_field = request.GET.get('filter_field', '').strip()
    filter_value = request.GET.get('filter_value', '').strip()
    min_year = request.GET.get('min_year', '').strip()
    max_year = request.GET.get('max_year', '').strip()

    qs = Libros.objects.all()

    # búsqueda libre existente
    if q:
        terms = [t for t in q.split() if t]
        query = Q()
        for term in terms:
            # campos de texto básicos
            term_q = (
                Q(cota__icontains=term) |
                Q(titulo__icontains=term) |
                Q(subtitulo__icontains=term) |
                Q(autor__icontains=term) |
                Q(editorial__icontains=term) |
                Q(serie__icontains=term) |
                Q(contenido__icontains=term) |
                Q(co_autor__icontains=term)
            )
            # si el término es numérico, intentar comparar con numero_registro (entero)
            try:
                n = int(term)
                term_q = term_q | Q(numero_registro=n)
            except Exception:
                pass

            # intentar interpretar el término como fecha (varios formatos) o año
            try:
                # año YYYY
                if len(term) == 4 and term.isdigit():
                    term_q = term_q | Q(fecha_registro__year=int(term))
                else:
                    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%Y/%m/%d'):
                        try:
                            dt = datetime.datetime.strptime(term, fmt).date()
                            term_q = term_q | Q(fecha_registro=dt)
                            break
                        except Exception:
                            continue
            except Exception:
                pass

            query &= term_q
        qs = qs.filter(query)

    # filtro por clasificación (opcional) - usar 'materia' param kept for compatibility
    if materia_id:
        qs = qs.filter(classification__id=materia_id)

    # filtro por campo seleccionado (texto -> icontains)
    text_filter_fields = {'autor','titulo','editorial','ubicacion_publicacion'}
    if filter_field and filter_value:
        if filter_field in text_filter_fields:
            kwargs = {f"{filter_field}__icontains": filter_value}
            qs = qs.filter(**kwargs)

    # filtro por rango de año en fecha_publicacion
    if filter_field == 'fecha_publicacion':
        try:
            if min_year:
                qs = qs.filter(fecha_publicacion__gte=int(min_year))
            if max_year:
                qs = qs.filter(fecha_publicacion__lte=int(max_year))
        except ValueError:
            # ignorar si no son enteros válidos
            pass

    # ordenación: permitir solo campos seguros
    allowed_sort = ['autor', 'titulo', 'editorial', 'ubicacion_publicacion', 'fecha_publicacion']
    if sort_by in allowed_sort:
        prefix = '-' if order == 'desc' else ''
        qs = qs.order_by(f"{prefix}{sort_by}")
    else:
        qs = qs.order_by('cota')

    qs = qs.distinct()

    # paginación
    paginator = Paginator(qs, 20)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    from .models import Clasificacion
    materias = Clasificacion.objects.all().order_by('code')
    # adjuntar conteo de prestados para cada libro en la página
    for t in page_obj.object_list:
        tot = Prestamo.objects.filter(book=t, status=Prestamo.STATUS_ACTIVE).aggregate(total=Sum('cantidad'))['total'] or 0
        setattr(t, 'prestados', int(tot))
        setattr(t, 'total', int(t.cantidad or 0))

    return render(request, 'tasks.html', {
        'tasks': page_obj,
        'q': q,
    'materias': materias,
    'selected_materia': materia_id,
        'sort_by': sort_by,
        'order': order,
        'filter_field': filter_field,
        'filter_value': filter_value,
        'min_year': min_year,
        'max_year': max_year,
    })


@login_required
def cart_add(request, pk):
    """Añade un libro al carrito guardado en session. Máximo 10 ítems."""
    book = get_object_or_404(Libros, pk=pk)
    # calcular cuántos ejemplares están actualmente prestados (activos)
    prestados_qs = Prestamo.objects.filter(book=book, status=Prestamo.STATUS_ACTIVE)
    prestados_total = prestados_qs.aggregate(total=Sum('cantidad'))['total'] or 0
    disponible = (book.cantidad or 0) - prestados_total
    if disponible <= 0:
        # si es AJAX devolver JSON con error
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'message': 'No hay ejemplares disponibles', 'count': 0})
        messages.error(request, 'No hay ejemplares disponibles para préstamo de este libro.')
        return redirect(request.META.get('HTTP_REFERER', reverse('tasks')))

    cart = request.session.get('loan_cart', [])
    # evitar duplicados
    if str(pk) not in cart:
        cart.insert(0, str(pk))
        # mantener máximo 10
        cart = cart[:10]
    request.session['loan_cart'] = cart
    # registrar usuario que añadió (último)
    request.session['loan_cart_user'] = request.user.get_full_name() or request.user.username
    request.session.modified = True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        # además incluir información de prestados/total
        return JsonResponse({'ok': True, 'count': len(cart), 'prestados': int(prestados_total), 'total': int(book.cantidad or 0)})
    return redirect(request.META.get('HTTP_REFERER', reverse('tasks')))


@login_required
def cart_remove(request, pk):
    """Quita un libro del carrito en session."""
    cart = request.session.get('loan_cart', [])
    pk_s = str(pk)
    if pk_s in cart:
        cart = [i for i in cart if i != pk_s]
        request.session['loan_cart'] = cart
        request.session.modified = True
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'count': len(cart)})
    return redirect(request.META.get('HTTP_REFERER', reverse('tasks')))


#CREAR LIBRO

def create_task(request):
    if not request.user.is_authenticated:
        return redirect('signin')

    if request.method == 'GET':
        return render(request, 'create_task.html', {'form': TaskForm()})
    else:
        form = TaskForm(request.POST, request.FILES)
        if form.is_valid():
            # componer cota desde las partes y comprobar existencia (case-insensitive)
            p1 = (form.cleaned_data.get('cota_part1') or '').strip()
            p2 = (form.cleaned_data.get('cota_part2') or '').strip()
            p3 = (form.cleaned_data.get('cota_part3') or '').strip()
            p4 = (form.cleaned_data.get('cota_part4') or '').strip()
            parts = [p for p in [p1, p2, p3, p4] if p != '']
            cota_val = ' '.join(parts).upper() if parts else ''
            if cota_val and Libros.objects.filter(cota__iexact=cota_val).exists():
                return render(request, 'create_task.html', {
                    'form': form,
                    'error': f'La cota "{cota_val}" ya existe.'
                })

            new_task = form.save(commit=False)
            new_task.user = request.user
            # forzar que el libro esté activo al crearlo
            try:
                new_task.is_active = True
            except Exception:
                pass
            try:
                new_task.save()
            except IntegrityError as e:
                # si la excepción viene por la cota, informar claramente
                if cota_val and Libros.objects.filter(cota__iexact=cota_val).exists():
                    return render(request, 'create_task.html', {
                        'form': form,
                        'error': f'La cota "{cota_val}" ya existe en la base de datos.'
                    })
                # mensaje genérico si no es por cota
                return render(request, 'create_task.html', {
                    'form': form,
                    'error': 'Error al guardar el libro: conflicto de registro (cota duplicada u otro índice único).'
                })
            except Exception as e:
                return render(request, 'create_task.html', {
                    'form': form,
                    'error': 'Error al guardar el libro: ' + str(e)
                })

            try:
                form.save_m2m()
            except Exception:
                pass

            # registrar alta de libro
            try:
                AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EVENT_ADD, book=new_task, user=request.user)
            except Exception:
                pass

            # La clasificación se asigna automáticamente en TaskForm.save(); no se aceptan materias manuales

            return redirect('tasks')
        else:
            return render(request, 'create_task.html', {
                'form': form,
                'error': 'Error al registrar el libro, por favor verifique los datos ingresados'
            })
            

#EDITAR LIBRO

def task_detail(request, pk):
    book = get_object_or_404(Libros, pk=pk)
    # registrar vista/consulta
    try:
        AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EVENT_VIEW, book=book, user=request.user if request.user.is_authenticated else None)
    except Exception:
        pass
    prestados = Prestamo.objects.filter(book=book, status=Prestamo.STATUS_ACTIVE).aggregate(total=Sum('cantidad'))['total'] or 0
    return render(request, 'task_detail.html', {'book': book, 'prestados': int(prestados), 'total': int(book.cantidad or 0)})

@login_required(login_url='signin')
def task_edit(request, pk):
    book = get_object_or_404(Libros, pk=pk)

    # permitir que superusers editen libros inactivos; usuarios normales no
    if not getattr(book, 'is_active', True) and not (request.user.is_authenticated and request.user.is_superuser):
        messages.error(request, 'No es posible editar un libro inactivo. Use la interfaz administrativa para reactivar o modificar este registro.')
        return redirect('task_detail', pk=book.pk)

    # poblar el campo único de cota con el valor completo del libro
    initial = {}
    if getattr(book, 'cota', None):
        initial['cota'] = book.cota

    if request.method == 'POST':
        form = TaskForm(request.POST, request.FILES, instance=book)
        if form.is_valid():
            edited = form.save(commit=False)
            # Forzar y normalizar 'contenido' desde cleaned_data para asegurarnos que se guarden múltiples checkboxes
            try:
                contenido_list = form.cleaned_data.get('contenido', []) if hasattr(form, 'cleaned_data') else []
                # obtener lista permitida desde el módulo de forms
                from .forms import CONTENT_CHOICES
                allowed = {c[0] for c in CONTENT_CHOICES}
                clean_vals = [v.strip() for v in contenido_list if v and v.strip() in allowed]
                edited.contenido = ','.join(clean_vals) if clean_vals else ''
                pass
            except Exception as e:
                print('[DEBUG] error al normalizar contenido en task_edit:', e)
            # continuación de flujo normal
            # conservar propietario original o asignar request.user según necesidad:
            edited.user = book.user
            edited.save()
            # continuar con guardado y manejo de relaciones
            try:
                # primero aplicar save_m2m estándar (por si hay otros M2M manejados por ModelForm)
                form.save_m2m()
            except Exception:
                # ignorar errores menores de save_m2m y manejar materias de forma explícita
                pass

            # La clasificación y vínculo al diccionario se gestionan en TaskForm.save(); no se manejan materias manuales
            try:
                fresh = Libros.objects.get(pk=edited.pk)
            except Exception:
                fresh = edited
            return redirect('task_detail', pk=fresh.pk)
    else:
        form = TaskForm(instance=book, initial=initial)

    return render(request, 'task_edit.html', {'form': form, 'book': book})


############# FICHA PDF #############


def task_pdf_card(request, pk):
    book = get_object_or_404(Libros, pk=pk)
    # bloquear impresión de ficha si el libro está inactivo
    if not getattr(book, 'is_active', True):
        messages.error(request, 'No es posible imprimir la ficha de un libro inactivo.')
        return redirect('task_detail', pk=book.pk)
    # registrar impresión PDF
    try:
        AnalyticsEvent.objects.create(event_type=AnalyticsEvent.EVENT_PDF, book=book, user=request.user if request.user.is_authenticated else None)
    except Exception:
        pass

    buffer = io.BytesIO()
    page_size = landscape(A5)
    c = canvas.Canvas(buffer, pagesize=page_size)
    w, h = page_size
    m = 0.7 * cm

    # espacio reservado arriba para el título (fuera del recuadro)
    title_space = 1.0 * cm
    # dibujar rectángulo principal desplazado hacia abajo para dejar espacio al título
    rect_x = m
    rect_y = m
    rect_width = w - 2 * m
    rect_height = h - 2 * m - title_space  # altura reducida para que el título quede fuera

    # borde externo (rectángulo)
    c.setLineWidth(1)
    c.rect(rect_x, rect_y, rect_width, rect_height)

    # Título centrado por fuera (arriba del recuadro)
    title_text = "ACADEMIA NACIONAL DE MEDICINA - BIBLIOTECA"
    c.setFont("Helvetica-Bold", 11)
    title_y = rect_y + rect_height + (title_space / 2)  # centrado vertical en el espacio superior
    c.drawCentredString(w / 2, title_y, title_text)

    # Área portada (derecha) dentro del rectángulo
    cover_w = 5.0 * cm
    cover_h = 7.0 * cm
    cover_x = rect_x + rect_width - cover_w - (0.3 * cm)
    cover_y = rect_y + rect_height - cover_h - (0.6 * cm)  # dejar pequeño margen superior dentro del rect.
    c.rect(cover_x, cover_y, cover_w, cover_h)
    if getattr(book, 'portada', None):
        try:
            img = ImageReader(book.portada.path)
            c.drawImage(img, cover_x+2, cover_y+2, cover_w-4, cover_h-4, preserveAspectRatio=True, anchor='nw')
        except Exception:
            pass

    # Cajas y etiquetas principales (imitando ficha)
    x0 = rect_x + 6
    # AUMENTE el margen superior del bloque de datos (mayor separación desde la parte superior del rectángulo)
    top_block_margin = 1.9 * cm  # aumentado
    y = rect_y + rect_height - top_block_margin
    line_h = 12

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "COTA:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 36, y, book.cota or "")
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "N.º REGISTRO:")
    c.setFont("Helvetica", 9)
    numero_reg = getattr(book, 'numero_registro', None) or getattr(book, 'id', '')
    c.drawString(x0 + 70, y, str(numero_reg))
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "FECHA REGISTRO:")
    c.setFont("Helvetica", 9)
    fr = getattr(book, 'fecha_registro', None)
    try:
        fr_txt = fr.strftime('%Y-%m-%d') if fr else ''
    except Exception:
        fr_txt = str(fr) if fr else ''
    c.drawString(x0 + 90, y, fr_txt)
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "TÍTULO:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 40, y, (book.titulo or "")[:80])
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "SUBTÍTULO:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 60, y, (book.subtitulo or "")[:80])
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "AUTOR:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 40, y, (book.autor or "")[:60])
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "COAUTOR:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 50, y, (getattr(book, 'co_autor', '') or '')[:60])
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "AÑO PUB:")
    c.setFont("Helvetica", 9)
    try:
        ap = book.fecha_publicacion.strftime('%Y') if getattr(book, 'fecha_publicacion', None) else ''
    except Exception:
        ap = str(getattr(book, 'fecha_publicacion', '') or '')
    c.drawString(x0 + 53, y, ap)
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "EDITORIAL:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 60, y, (book.editorial or "")[:60])
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "CLASIFICACIÓN:")
    c.setFont("Helvetica", 9)
    try:
        clas_txt = book.classification.label if getattr(book, 'classification', None) and getattr(book.classification, 'label', None) else (str(book.classification) if getattr(book, 'classification', None) else '')
    except Exception:
        clas_txt = str(getattr(book, 'classification', '') or '')
    c.drawString(x0 + 86, y, (clas_txt or '')[:60])
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "EDICIÓN:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 50, y, f"{book.edicion}ª" if book.edicion else "")
    y -= line_h

    c.setFont("Helvetica-Bold", 9)
    c.drawString(x0, y, "UBICACIÓN:")
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 60, y, (book.ubicacion_publicacion or "")[:60])
    y -= (line_h + 8) # un poco más de espacio antes del bloque inferior

    # sección inferior: aumentar separación entre las filas y margen superior del bloque
    c.setFont("Helvetica-Bold", 9)
    bottom_x = x0
    # Espaciado más grande entre líneas de firma
    sig_spacing = 30  # distancia vertical entre cada campo (aumentada)
    line_len = 220
    # Ajustar posición vertical para tener mayor margen superior antes de esta zona
    y -= 6  # pequeño ajuste extra para empujar hacia abajo (puedes aumentar)
    # PRESTADO POR
    c.drawString(bottom_x, y, "PRESTADO POR:")
    c.line(bottom_x + 80, y-2, bottom_x + 80 + line_len, y-2)
    y -= sig_spacing
    # RECIBIDO POR
    c.drawString(bottom_x, y, "RECIBIDO POR:")
    c.line(bottom_x + 80, y-2, bottom_x + 80 + line_len, y-2)
    y -= sig_spacing
    # FIRMA
    c.drawString(bottom_x, y, "FIRMA:")
    c.line(bottom_x + 40, y-2, bottom_x + 40 + (line_len * 0.6), y-2)

    # Pie pequeño con número de serie / vol / año
    c.setFont("Helvetica", 8)
    footer_items = []
    nr = getattr(book, 'numero_registro', None)
    if nr:
        footer_items.append(f"N.º registro: {nr}")
    footer_items.append(f"ID: {book.id}")
    if getattr(book, 'paginas', None):
        footer_items.append(f"Páginas: {book.paginas}")
    if getattr(book, 'volumen', None):
        footer_items.append(f"Vol: {book.volumen}")
    if getattr(book, 'serie', None):
        footer_items.append(f"Serie: {book.serie}")
    # incluir fecha_registro si existe
    if getattr(book, 'fecha_registro', None):
        try:
            footer_items.append(f"Fecha registro: {book.fecha_registro.strftime('%Y-%m-%d')}")
        except Exception:
            footer_items.append(f"Fecha registro: {book.fecha_registro}")
    c.drawString(m + 6, m + 6, '  |  '.join(footer_items))

    c.showPage()
    c.save()

    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename=\"Ficha_{book.id}.pdf\"'
    return response


#################################### DASHBOARD - ESTADISTICA #####################################

@login_required(login_url='signin')
def dashboard(request):
    # periodo: últimos 12 meses
    today = datetime.date.today()
    first_day = (today.replace(day=1) - datetime.timedelta(days=365)).replace(day=1)
    # generar lista de meses (YYYY-MM) ordenada ascendente
    months = []
    dt = first_day
    while dt <= today:
        months.append(dt.strftime('%Y-%m'))
        # avanzar mes
        year = dt.year + (dt.month // 12)
        month = dt.month % 12 + 1
        dt = dt.replace(year=year, month=month, day=1)

    # consulta agrupada por mes y tipo
    events = AnalyticsEvent.objects.filter(timestamp__date__gte=first_day).annotate(month=TruncMonth('timestamp')).values('event_type', 'month').annotate(count=Count('id'))
    # preparar mapeo
    data_map = {et: {m:0 for m in months} for et, _ in AnalyticsEvent.EVENT_CHOICES}
    for e in events:
        m = e['month'].strftime('%Y-%m')
        if m in months:
            data_map[e['event_type']][m] = e['count']

    labels = months
    views_data = [data_map[AnalyticsEvent.EVENT_VIEW][m] for m in months]
    adds_data = [data_map[AnalyticsEvent.EVENT_ADD][m] for m in months]
    pdfs_data = [data_map[AnalyticsEvent.EVENT_PDF][m] for m in months]
    logins_data = [data_map[AnalyticsEvent.EVENT_LOGIN][m] for m in months]

    return render(request, 'dashboard.html', {
        'labels': labels,
        'views_data': views_data,
        'adds_data': adds_data,
        'pdfs_data': pdfs_data,
        'logins_data': logins_data,
    })
    
    
##########################   TASK LIST - PRESTAMOS   ########################## 

def task_list(request):
    # Mostrar el carrito (o una lista vacía) con hasta 10 libros guardados en session
    cart_ids = request.session.get('loan_cart', [])[:10]
    # obtener objetos y mantener el orden según cart_ids
    libs_qs = Libros.objects.filter(id__in=cart_ids)
    libs_map = {str(b.id): b for b in libs_qs}
    cart_books = [libs_map[i] for i in cart_ids if str(i) in libs_map]
    loan_user = request.session.get('loan_cart_user')
    # calcular prestados por libro y adjuntar atributos en cada instancia para la plantilla
    for b in cart_books:
        tot = Prestamo.objects.filter(book=b, status=Prestamo.STATUS_ACTIVE).aggregate(total=Sum('cantidad'))['total'] or 0
        setattr(b, 'prestados', int(tot))
        setattr(b, 'total', int(b.cantidad or 0))

    return render(request, 'task_list.html', {'cart_books': cart_books, 'loan_cart_user': loan_user})


@login_required
def cart_checkout(request):
    """Confirma los préstamos listados en la sesión: crea Prestamo por cada libro con cantidad=1.
    Verifica disponibilidad dentro de una transacción para evitar sobre-reservas.
    """
    cart_ids = request.session.get('loan_cart', [])[:10]
    if not cart_ids:
        messages.info(request, 'El carrito está vacío.')
        return redirect('cart_view')

    # leer datos del receptor si vienen en el POST (se piden en la plantilla)
    receiver_cedula = None
    receiver_first_name = None
    receiver_last_name = None
    if request.method == 'POST':
        receiver_cedula = request.POST.get('receiver_cedula', '').strip() or None
        receiver_first_name = request.POST.get('receiver_first_name', '').strip() or None
        receiver_last_name = request.POST.get('receiver_last_name', '').strip() or None

        # Validar que se hayan provisto los datos del receptor (cedula, nombre y apellido)
        is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
        field_errors = {}
        if not receiver_cedula:
            field_errors['receiver_cedula'] = 'La cédula es obligatoria.'
        else:
            # validar que la cédula sea numérica
            if not receiver_cedula.isdigit():
                field_errors['receiver_cedula'] = 'La cédula debe contener solo dígitos.'
        if not receiver_first_name:
            field_errors['receiver_first_name'] = 'El nombre del receptor es obligatorio.'
        if not receiver_last_name:
            field_errors['receiver_last_name'] = 'El apellido del receptor es obligatorio.'

        if field_errors:
            if is_ajax:
                return JsonResponse({'ok': False, 'errors': field_errors}, status=400)
            # para peticiones normales, concatenar mensajes y mostrar como message
            messages.error(request, ' '.join(field_errors.values()))
            return redirect('cart_view')

    # usar transacción para evitar condiciones de carrera
    created = []
    failed = []
    try:
        with transaction.atomic():
            for pk_s in cart_ids:
                try:
                    pk = int(pk_s)
                except Exception:
                    continue
                book = Libros.objects.select_for_update().filter(pk=pk).first()
                if not book:
                    failed.append((pk, 'Libro no encontrado'))
                    continue
                prestados_total = Prestamo.objects.filter(book=book, status=Prestamo.STATUS_ACTIVE).aggregate(total=Sum('cantidad'))['total'] or 0
                disponible = (book.cantidad or 0) - prestados_total
                if disponible <= 0:
                    failed.append((pk, 'Sin stock'))
                    continue
                # crear prestamo por 1 ejemplar, incluyendo datos del receptor si se recogieron
                p = Prestamo.objects.create(
                    book=book,
                    user=request.user,
                    cantidad=1,
                    status=Prestamo.STATUS_ACTIVE,
                    receiver_cedula=receiver_cedula,
                    receiver_first_name=receiver_first_name,
                    receiver_last_name=receiver_last_name,
                    approved_at=timezone.now(),
                )
                created.append(p)
    except Exception as e:
        messages.error(request, 'Error al procesar el checkout: ' + str(e))
        return redirect('cart_view')

    # limpiar carrito de la sesión (quitar los que se crearon)
    remaining = [i for i in cart_ids if str(i) not in [str(p.book_id) for p in created]]
    request.session['loan_cart'] = remaining
    request.session.modified = True

    # Responder apropiadamente según si es AJAX
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'ok': True,
            'created': len(created),
            'failed': [{'id': f[0], 'reason': f[1]} for f in failed],
            'remaining_count': len(remaining),
        })

    if created:
        messages.success(request, f'Se confirmaron {len(created)} préstamos.')
    if failed:
        messages.warning(request, f'No se pudieron crear {len(failed)} préstamos: {", ".join([f[1] for f in failed])}.')

    return redirect('cart_view')


@login_required
def my_loans(request):
    """Muestra los préstamos activos del usuario."""
    # ordenar por fecha de aprobación si existe, si no por id descendente (recientes primero)
    # mostrar sólo préstamos activos
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        qs = Prestamo.objects.filter(status=Prestamo.STATUS_ACTIVE).order_by('-approved_at', '-id')
    else:
        qs = Prestamo.objects.filter(user=request.user, status=Prestamo.STATUS_ACTIVE).order_by('-approved_at', '-id')
    # paginación simple: 10 por página
    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'my_loans.html', {'loans': page_obj})


@login_required
def returns_history(request):
    """Muestra el historial de devoluciones del usuario (préstamos con status 'returned')."""
    q = request.GET.get('q', '').strip()
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    # si es staff o superuser, mostrar historial de todos los usuarios
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        qs = Prestamo.objects.filter(status=Prestamo.STATUS_RETURNED)
    else:
        qs = Prestamo.objects.filter(user=request.user, status=Prestamo.STATUS_RETURNED)
    # filtro por título del libro
    if q:
        qs = qs.filter(book__titulo__icontains=q)
    # filtro por rango de fecha (returned_at)
    from datetime import datetime
    try:
        if start_date:
            sd = datetime.fromisoformat(start_date).date()
            qs = qs.filter(returned_at__date__gte=sd)
    except Exception:
        pass
    try:
        if end_date:
            ed = datetime.fromisoformat(end_date).date()
            qs = qs.filter(returned_at__date__lte=ed)
    except Exception:
        pass

    qs = qs.order_by('-returned_at', '-approved_at', '-id')
    # paginación
    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'returns_history.html', {
        'returned': page_obj,
        'q': q,
        'start_date': start_date,
        'end_date': end_date,
    })


@login_required
def loan_return(request, pk):
    """Marca un préstamo como devuelto si pertenece al usuario."""
    # permitir a staff/superuser operar sobre cualquier préstamo; usuarios normales sólo sobre los suyos
    if request.user.is_authenticated and (request.user.is_staff or request.user.is_superuser):
        loan = get_object_or_404(Prestamo, pk=pk)
    else:
        loan = get_object_or_404(Prestamo, pk=pk, user=request.user)
    if request.method == 'POST':
        loan.status = Prestamo.STATUS_RETURNED
        # marcar la hora exacta de devolución (timezone-aware)
        loan.returned_at = timezone.now()
        # leer reporte y puntuaciones si vienen
        report = request.POST.get('return_report', '').strip() or None
        book_rating = request.POST.get('return_book_rating', '').strip() or None
        receiver_rating = request.POST.get('return_receiver_rating', '').strip() or None
        # validar puntuaciones
        try:
            if book_rating:
                br = int(book_rating)
                if 1 <= br <= 5:
                    loan.return_book_rating = br
            if receiver_rating:
                rr = int(receiver_rating)
                if 1 <= rr <= 5:
                    loan.return_receiver_rating = rr
        except Exception:
            # ignorar valores inválidos (no impedir devolución)
            pass
        if report:
            loan.return_report = report
        loan.save()
        # calcular nuevo conteo de prestados para el libro asociado
        book = loan.book
        prestados_total = Prestamo.objects.filter(book=book, status=Prestamo.STATUS_ACTIVE).aggregate(total=Sum('cantidad'))['total'] or 0
        # si es AJAX devolver JSON con información útil para actualizar UI en tiempo real
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            # renderizar partial del loan actualizado para reemplazar la fila entera en el cliente
            try:
                loan_html = render_to_string('tasks/_loan_item.html', {'loan': loan}, request=request)
            except Exception:
                loan_html = None
            return JsonResponse({
                'ok': True,
                'loan_id': loan.id,
                'book_id': book.id,
                'prestados': int(prestados_total),
                'total': int(book.cantidad or 0),
                'returned_at': loan.returned_at.isoformat() if loan.returned_at else None,
                'return_report': loan.return_report,
                'return_book_rating': loan.return_book_rating,
                'return_receiver_rating': loan.return_receiver_rating,
                'loan_html': loan_html,
            })
        messages.success(request, 'Préstamo marcado como devuelto.')
        return redirect('my_loans')
    return render(request, 'loan_confirm_return.html', {'loan': loan})


@login_required
def cart_json(request):
    """Devuelve el contenido del carrito (sesión) en JSON para uso en pop-ups/JS."""
    cart_ids = request.session.get('loan_cart', [])[:10]
    libs_qs = Libros.objects.filter(id__in=cart_ids)
    libs_map = {str(b.id): b for b in libs_qs}
    items = []
    for pk in cart_ids:
        b = libs_map.get(str(pk))
        if not b:
            continue
        prestados = Prestamo.objects.filter(book=b, status=Prestamo.STATUS_ACTIVE).aggregate(total=Sum('cantidad'))['total'] or 0
        items.append({
            'id': b.id,
            'titulo': b.titulo,
            'autor': b.autor,
            'cota': b.cota,
            'portada': b.portada.url if getattr(b, 'portada', None) else '',
            'prestados': int(prestados),
            'total': int(b.cantidad or 0),
        })
    return JsonResponse({'ok': True, 'items': items, 'loan_cart_user': request.session.get('loan_cart_user', '')})


def dictionary_view(request):
    q = request.GET.get('q', '').strip()
    clas = request.GET.get('clas', '').strip()
    # Mostrar sólo entradas activas en la vista pública
    qs = DictionaryEntry.objects.filter(is_active=True)
    if q:
        qs = qs.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q) | Q(descripcion_en__icontains=q))
    # filtro por clasificación (acepta prefijos como 'QS' o la etiqueta completa 'QS-Anatomía Humana')
    if clas:
        # intentar extraer el código antes del guion si el usuario pasó la etiqueta completa
        code = clas.split('-', 1)[0].strip()
        # filtrar por campo clasificacion o por prefijo de codigo (p. ej. 'QS')
        qs = qs.filter(
            Q(clasificacion__icontains=clas) | Q(clasificacion__icontains=code) | Q(codigo__istartswith=code)
        )
    from django.core.paginator import Paginator
    paginator = Paginator(qs, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    classification_list = [
        'QS-Anatomía Humana', 'QT-Fisiología', 'QU-Bioquímica. Biología Celular y Genética',
        'QV-Farmacología', 'QW-Microbiología. Inmunología', 'QX-Parasitología. Vectores de Enfermedades',
        'QY-Patología Clínica de Laboratorio', 'QZ-Patología', 'W-Medicina General. Profesiones de la Salud',
        'WA-Salud Pública', 'WB-Práctica de la Medicina', 'WC-Enfermedades Transmisibles',
        'WD-Medicina en Entornos Selectos', 'WE-Sistema Musculoesquelético', 'WF-Sistema Respiratorio',
        'WG-Sistema Cardiovascular', 'WH-Sistemas Hemático y Linfático', 'WI-Sistema Digestivo',
        'WJ-Sistema Urogenital', 'WK-Sistema Endocrino', 'WL-Sistema Nervioso', 'WM-Psiquiatría',
        'WN-Radiología. Diagnóstico por Imagen', 'WO-Cirugía', 'WP-Medicina Reproductiva',
        'WQ-Obstetricia. Embarazo', 'WR-Dermatología. Sistema Tegumentario', 'WS-Pediatría',
        'WT-Geriatría', 'WU-Odontología. Cirugía Oral', 'WV-Otorrinolaringología', 'WW-Oftalmología',
        'WX-Hospitales y Otros Centros de Salud', 'WY-Enfermería', 'WZ-Historia de la Medicina. Miscelánea Médica'
    ]
    return render(request, 'dictionary.html', {
        'entries': page_obj,
        'q': q,
        'selected_clas': clas,
        'classification_list': classification_list,
    })


def autocomplete_codes(request):
    """Devuelve JSON con códigos del diccionario que coinciden con el término 'q'."""
    term = request.GET.get('q', '').strip()
    # Autocompletado público: sólo códigos activos
    qs = DictionaryEntry.objects.filter(is_active=True)
    if term:
        qs = qs.filter(codigo__icontains=term)
    # limitar a 50 resultados
    results = list(qs.order_by('codigo').values_list('codigo', flat=True)[:50])
    return JsonResponse({'results': results})


@login_required
def reports_index(request):
    """Lista libros que tengan al menos un prestamo con reporte o calificaciones."""
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    min_score = request.GET.get('min_score', '').strip()

    # base loans that have any report/ratings
    loan_qs = Prestamo.objects.filter(
        Q(return_report__isnull=False) | Q(return_book_rating__isnull=False) | Q(return_receiver_rating__isnull=False)
    )
    from datetime import datetime
    try:
        if start_date:
            sd = datetime.fromisoformat(start_date).date()
            loan_qs = loan_qs.filter(returned_at__date__gte=sd)
    except Exception:
        pass
    try:
        if end_date:
            ed = datetime.fromisoformat(end_date).date()
            loan_qs = loan_qs.filter(returned_at__date__lte=ed)
    except Exception:
        pass
    try:
        if min_score:
            ms = int(min_score)
            loan_qs = loan_qs.filter(Q(return_book_rating__gte=ms) | Q(return_receiver_rating__gte=ms))
    except Exception:
        pass

    # obtain books that have matching loans
    qs = Libros.objects.filter(prestamos__in=loan_qs).distinct().order_by('cota')
    # anotar promedios de calificaciones por libro (agregar Avg sobre prestamos filtrados)
    qs = qs.annotate(
        avg_book_rating=Avg('prestamos__return_book_rating'),
        avg_receiver_rating=Avg('prestamos__return_receiver_rating')
    )
    # anotar conteos (número de prestamos con reportes/puntuaciones)
    qs = qs.annotate(
        count_reports=Count('prestamos', filter=Q(prestamos__return_report__isnull=False)),
        count_book_ratings=Count('prestamos', filter=Q(prestamos__return_book_rating__isnull=False)),
        count_receiver_ratings=Count('prestamos', filter=Q(prestamos__return_receiver_rating__isnull=False)),
    )
    # pagination for books
    paginator = Paginator(qs, 10)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'reports_list.html', {
        'books': page_obj,
        'start_date': start_date,
        'end_date': end_date,
        'min_score': min_score,
    })


@login_required
def report_detail(request, pk):
    book = get_object_or_404(Libros, pk=pk)
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    min_score = request.GET.get('min_score', '').strip()

    loans = Prestamo.objects.filter(book=book).filter(
        Q(return_report__isnull=False) | Q(return_book_rating__isnull=False) | Q(return_receiver_rating__isnull=False)
    )
    from datetime import datetime
    try:
        if start_date:
            sd = datetime.fromisoformat(start_date).date()
            loans = loans.filter(returned_at__date__gte=sd)
    except Exception:
        pass
    try:
        if end_date:
            ed = datetime.fromisoformat(end_date).date()
            loans = loans.filter(returned_at__date__lte=ed)
    except Exception:
        pass
    try:
        if min_score:
            ms = int(min_score)
            loans = loans.filter(Q(return_book_rating__gte=ms) | Q(return_receiver_rating__gte=ms))
    except Exception:
        pass

    loans = loans.order_by('-returned_at', '-approved_at')
    # paginate loans
    paginator = Paginator(loans, 10)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    # calcular promedios para este libro (sobre loans filtrados)
    agg = loans.aggregate(avg_book=Avg('return_book_rating'), avg_receiver=Avg('return_receiver_rating'))
    avg_book = agg.get('avg_book')
    avg_receiver = agg.get('avg_receiver')
    return render(request, 'reports_detail.html', {'book': book, 'loans': page_obj, 'start_date': start_date, 'end_date': end_date, 'min_score': min_score, 'avg_book': avg_book, 'avg_receiver': avg_receiver})


@login_required
def reports_users_index(request):
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    min_score = request.GET.get('min_score', '').strip()
    q = request.GET.get('q', '').strip()

    loan_qs = Prestamo.objects.filter(returned_at__isnull=False, return_receiver_rating__isnull=False)
    from datetime import datetime
    try:
        if start_date:
            sd = datetime.fromisoformat(start_date).date()
            loan_qs = loan_qs.filter(returned_at__date__gte=sd)
    except Exception:
        pass
    try:
        if end_date:
            ed = datetime.fromisoformat(end_date).date()
            loan_qs = loan_qs.filter(returned_at__date__lte=ed)
    except Exception:
        pass
    try:
        if min_score:
            ms = int(min_score)
            loan_qs = loan_qs.filter(return_receiver_rating__gte=ms)
    except Exception:
        pass

    users_qs = loan_qs.values('receiver_cedula', 'receiver_first_name', 'receiver_last_name') \
        .annotate(avg_receiver_rating=Avg('return_receiver_rating'), count_reports=Count('id')) \
        .order_by('-avg_receiver_rating')

    if q:
        users_qs = users_qs.filter(
            Q(receiver_cedula__icontains=q) | Q(receiver_first_name__icontains=q) | Q(receiver_last_name__icontains=q)
        )

    paginator = Paginator(users_qs, 10)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)
    return render(request, 'reports_users_list.html', {
        'users': users_page,
        'q': q,
        'start_date': start_date,
        'end_date': end_date,
        'min_score': min_score,
    })


@login_required
def reports_user_detail(request):
    receiver_cedula = request.GET.get('receiver_cedula', '').strip()
    if not receiver_cedula:
        return HttpResponse('receiver_cedula is required', status=400)
    start_date = request.GET.get('start_date', '').strip()
    end_date = request.GET.get('end_date', '').strip()

    loans = Prestamo.objects.filter(receiver_cedula=receiver_cedula)
    from datetime import datetime
    try:
        if start_date:
            sd = datetime.fromisoformat(start_date).date()
            loans = loans.filter(returned_at__date__gte=sd)
    except Exception:
        pass
    try:
        if end_date:
            ed = datetime.fromisoformat(end_date).date()
            loans = loans.filter(returned_at__date__lte=ed)
    except Exception:
        pass

    loans = loans.order_by('-returned_at', '-approved_at')
    paginator = Paginator(loans, 10)
    page = request.GET.get('page')
    loans_page = paginator.get_page(page)
    avg_receiver = loans.aggregate(avg=Avg('return_receiver_rating'))['avg']
    # intentar obtener nombre del receptor desde los préstamos (si existe)
    name_info = loans.values('receiver_first_name', 'receiver_last_name').first() or {}
    receiver_first_name = name_info.get('receiver_first_name') or ''
    receiver_last_name = name_info.get('receiver_last_name') or ''
    return render(request, 'reports_user_detail.html', {
        'loans': loans_page,
        'receiver_cedula': receiver_cedula,
        'receiver_first_name': receiver_first_name,
        'receiver_last_name': receiver_last_name,
        'avg_receiver': avg_receiver,
        'start_date': start_date,
        'end_date': end_date,
    })


def user_guide(request):
    """Renderiza la guía de usuario (acordeón)."""
    return render(request, 'user_guide.html')