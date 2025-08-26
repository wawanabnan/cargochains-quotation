from django import template
register = template.Library()

@register.filter
def get_item(d, k):
    try:
        return d.get(k, 0)
    except Exception:
        return 0
