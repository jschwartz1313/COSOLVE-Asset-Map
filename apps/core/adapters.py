from allauth.account.adapter import DefaultAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.shortcuts import redirect


class ClosedAccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        return False


class InvitedUserSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Allow organization sign-in only for active users created by an administrator."""

    def is_open_for_signup(self, request, sociallogin):
        return False

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return
        verified_emails = [
            email.email for email in sociallogin.email_addresses if email.verified
        ]
        if not verified_emails:
            messages.error(request, "Your organization did not provide a verified email address.")
            raise ImmediateHttpResponse(redirect("account_login"))
        user = (
            get_user_model()
            .objects.filter(email__iexact=verified_emails[0], is_active=True)
            .first()
        )
        if user is None:
            messages.error(
                request,
                "An administrator must create your account before organization sign-in "
                "can be used.",
            )
            raise ImmediateHttpResponse(redirect("account_login"))
        sociallogin.connect(request, user)
