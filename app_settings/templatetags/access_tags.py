from django import template

from app_settings.access import has_access

register = template.Library()


@register.filter
def can(user, permission_name):
    return has_access(user, permission_name)
