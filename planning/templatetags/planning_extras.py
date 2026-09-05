from django import template

register = template.Library()


@register.filter
def planning_entry(entry_map, key):
    return entry_map.get(key, {})
