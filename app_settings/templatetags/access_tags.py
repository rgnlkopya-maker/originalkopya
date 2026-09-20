from django import template

from app_settings.access import has_access, has_feature_access

register = template.Library()


@register.filter
def can(user, permission_name):
    return has_access(user, permission_name)


@register.filter
def can_feature(user, feature_key):
    return has_feature_access(user, feature_key)
