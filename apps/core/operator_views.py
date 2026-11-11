import uuid
from functools import wraps

from django.core.exceptions import ValidationError
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.assets.models import Asset
from apps.assets.operator_review import OperatorReview, OperatorReviewUnavailable

from .operator_forms import OperatorReviewForm


def private_invitation_response(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        # Keep the token path out of Referer without producing Origin: null on form posts.
        response["Referrer-Policy"] = "strict-origin"
        response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response
    return wrapped


# Run CSRF protection inside the privacy wrappers so even CSRF failures get these headers.
@csrf_exempt
@never_cache
@private_invitation_response
@sensitive_post_parameters()
@csrf_protect
@require_http_methods(("GET", "POST"))
def operator_review(request, token):
    def unavailable():
        return render(request, "assets/operator_review.html", {"unavailable": True}, status=404)

    try:
        token = uuid.UUID(str(token))
    except (ValueError, TypeError, AttributeError):
        return unavailable()
    review = OperatorReview.objects.filter(token=token).first()
    if not review or not review.is_available:
        return unavailable()
    asset = Asset.public.filter(pk=review.asset_id).first()
    if asset is None:
        return unavailable()
    form = OperatorReviewForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            form.submit(review)
        except OperatorReviewUnavailable:
            return unavailable()
        except ValidationError:
            form.add_error(None, "The proposal could not be accepted. Check the details and retry.")
        else:
            # Do not echo the proposal, private identity, token, or review metadata.
            return render(request, "assets/operator_review.html", {"submitted": True})
    return render(request, "assets/operator_review.html", {
        "form": form, "asset_name": asset.public_name,
    })
