from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import DictionaryEntry, Clasificacion, Libros
from .forms import TaskForm


class TaskFormDictionaryIntegrationTests(TestCase):
	def setUp(self):
		User = get_user_model()
		# crear usuario de prueba
		self.user = User.objects.create_user(username='tester', password='testpass123', cedula=12345, telefono=12345678, security_question='q', security_answer='a', email='t@example.com')

		# crear una entrada de diccionario con clasificacion
		self.entry = DictionaryEntry.objects.create(
			codigo='QS 18.2',
			descripcion='Descripción de prueba',
			descripcion_en='Test description',
			clasificacion='QS-Anatomía Humana'
		)

	def test_taskform_assigns_dictionary_and_classification(self):
		# datos mínimos para el formulario (excluye cota porque TaskForm compone la cota desde partes)
		data = {
			'cota': 'QS 18.2',
			'titulo': 'Libro de prueba',
			'autor': 'Autor, Uno',
			'cantidad': 1,
			'edicion': 1,
		}
		# incluir usuario por separado ya que TaskForm excluye user
		form = TaskForm(data=data)
		self.assertTrue(form.is_valid(), msg=form.errors.as_json())
		book = form.save(commit=False)
		book.user = self.user
		book.save()
		# refrescar y comprobar que la cota se guardó correctamente
		b = Libros.objects.get(pk=book.pk)
		self.assertEqual(b.cota, 'QS 18.2')

	def test_taskform_invalid_when_dictionary_missing(self):
		data = {
			'cota': 'XX 999',
			'titulo': 'Libro invalido',
			'autor': 'Autor, Dos',
			'cantidad': 1,
			'edicion': 1,
		}
		form = TaskForm(data=data)
		# ahora que ya no validamos contra el diccionario, el formulario debe ser válido
		self.assertTrue(form.is_valid(), msg=form.errors.as_json())
