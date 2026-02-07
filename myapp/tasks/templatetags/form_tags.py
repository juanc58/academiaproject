from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name='add_class')
def add_class(field, css):
    """Añade una clase CSS a un campo de formulario renderizado.

    Uso en plantilla: {{ field|add_class:"mt-1 block w-full" }}
    """
    try:
        widget = field.field.widget
        existing = widget.attrs.get('class', '')
        new = (existing + ' ' + css).strip()
        return field.as_widget(attrs={'class': new})
    except Exception:
        # Fallback: devolver representación ingenua
        return mark_safe(str(field))
