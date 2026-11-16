"""Shared sheet access rules for HTML views and future API endpoints."""
from django.db.models import Q
from .models import StatSheet
from django.core.exceptions import PermissionDenied, ValidationError
from campaigns.models import CampaignMembership

def accessible_sheets(user):
    """Return sheets the user may view and edit; membership alone is insufficient."""
    if not user.is_authenticated:
        return StatSheet.objects.none()
    return StatSheet.objects.filter(
        Q(campaign__gm=user) | Q(controller=user) | Q(access_grants__user=user)
    ).distinct()


# Omitted controller means “assign the requesting user.”
DEFAULT_CONTROLLER = object()


def resolve_creation_controller(
    *,
    user,
    campaign,
    controller=DEFAULT_CONTROLLER,
):
    """Check creation permissions and return the permitted controller."""

    if not user.is_authenticated:
        raise PermissionDenied("Log in before creating a sheet.")

    is_gm = campaign.gm_id == user.pk

    is_member = CampaignMembership.objects.filter(
        campaign=campaign,
        user=user,
    ).exists()

    if not is_gm and not is_member:
        raise PermissionDenied(
            "You must belong to this campaign to create a sheet."
        )

    # No explicit choice: assign the sheet to its creator.
    if controller is DEFAULT_CONTROLLER:
        return None if is_gm else user

    # Explicitly unassigned sheets are GM-only.
    if controller is None:
        if not is_gm:
            raise PermissionDenied(
                "Only the GM can create an unassigned sheet."
            )
        return None

    # Both members and the GM can create sheets for themselves.
    if controller.pk == user.pk:
        return user

    # Assigning another user is GM-only.
    if not is_gm:
        raise PermissionDenied(
            "You can only create sheets that you control."
        )

    # The assigned user must belong to this campaign.
    if not CampaignMembership.objects.filter(
        campaign=campaign,
        user=controller,
    ).exists():
        raise ValidationError(
            "The controller must be a member of this campaign."
        )

    return controller