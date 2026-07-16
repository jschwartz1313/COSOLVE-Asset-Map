from django import template

register = template.Library()


@register.filter
def getlist(querydict, key):
    return querydict.getlist(key)
