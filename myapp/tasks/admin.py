from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Libros, DictionaryEntry

# Register your models here.

#class TasksAdmin(admin.ModelAdmin):
    #readonly_fields = ('user',)

admin.site.register(Libros)
admin.site.register(User, UserAdmin)
@admin.register(DictionaryEntry)
class DictionaryEntryAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'clasificacion', 'descripcion')
    search_fields = ('codigo', 'descripcion', 'descripcion_en', 'clasificacion')

