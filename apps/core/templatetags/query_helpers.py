from django import template

register = template.Library()


@register.filter
def getlist(querydict, key):
    return querydict.getlist(key)


@register.simple_tag(takes_context=True)
def filter_url(context, **updates):
    request = context["request"]
    params = request.GET.copy()
    for key, value in updates.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    query = params.urlencode()
    return f"{request.path}?{query}" if query else request.path
