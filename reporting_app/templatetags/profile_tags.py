from django import template

register = template.Library()


@register.filter
def has_profile(user, attr_name):
    if not user:
        return False
    return hasattr(user, attr_name)
