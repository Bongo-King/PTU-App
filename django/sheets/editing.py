"""Validated local edits shared by HTML and future React clients."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from .constants import STAT_NAMES, SKILL_NAMES
from .models import StatSheet, PokemonProfile, SheetCapability, PokemonFormCapabilityChange
from .permissions import accessible_sheets

# Bounds are enforced by the service as well as the browser.
EDITABLE_FIELDS = {
    "current_hit_points": (-32768, 32767),
    "temp_hit_points": (0, 32767), "injuries": (0, 32767),
    **{f"{s}_base": (1, 32767) for s in STAT_NAMES},
    **{f"{s}_alloc": (0, 32767) for s in STAT_NAMES},
    **{f"{s}_bonus": (-32768, 32767) for s in STAT_NAMES},
    **{f"{s}_cs": (-6, 6) for s in (*STAT_NAMES[1:], "accuracy", "evasion")},
    **{f"{s}_rank": (1, 6) for s in SKILL_NAMES},
    **{f"{s}_bonus": (-32768, 32767) for s in SKILL_NAMES},
    **{f"{s}_bonus": (-32768, 32767) for s in (
        "physical_evasion", "special_evasion", "speed_evasion", "accuracy",
        "initiative", "damage", "damage_resistance", "critical_range",
    )},
}


class EditConflict(Exception):
    """The field or active form changed since the client last read it."""


def _integer(value, bounds):
    if type(value) is not int or not bounds[0] <= value <= bounds[1]:
        raise ValidationError(f"Enter a whole number from {bounds[0]} to {bounds[1]}.")


@transaction.atomic
def update_sheet_value(*, user, sheet_id, target, value, expected, active_form_id):
    """Update one allowlisted field, rejecting stale writes and foreign records.

    target is a sheet field name, 'capability:<local entry id>', or
    'form_capability:<local change id>'. Only local data can be changed.
    expected is the previously displayed value (optimistic concurrency check).
    """
    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")
    sheet = StatSheet.objects.select_for_update().get(pk=sheet_id)
    pokemon = None
    if sheet.kind == StatSheet.Kind.POKEMON:
        pokemon = PokemonProfile.objects.select_for_update().filter(sheet=sheet).first()
    actual_form = pokemon.active_form_id if pokemon else None
    if active_form_id != actual_form:
        raise EditConflict("The active form changed. Reload the sheet before editing.")
    if not isinstance(target, str):
        raise ValidationError("Select an editable field.")
    if target in EDITABLE_FIELDS:
        _integer(value, EDITABLE_FIELDS[target])
        instance, field = sheet, target
    elif target.startswith(("capability:", "form_capability:")):
        scope, raw_id = target.split(":", 1)
        if not raw_id.isdecimal() or len(raw_id) > 18:
            raise ValidationError("Invalid capability entry.")
        if scope == "capability":
            instance = SheetCapability.objects.select_for_update().filter(pk=int(raw_id), sheet=sheet).first()
        else:
            instance = PokemonFormCapabilityChange.objects.select_for_update().filter(
                pk=int(raw_id), form_id=actual_form, form__pokemon=pokemon,
            ).first() if pokemon and actual_form else None
        if instance is None or instance.capability.value_kind != "Numeric":
            raise ValidationError("Select a numeric capability on this sheet or active form.")
        if scope == "form_capability" and instance.operation == "Remove":
            raise ValidationError("Removed capabilities have no numeric value.")
        minimum = -2147483648 if scope == "form_capability" and instance.operation == "Adjust" else 0
        _integer(value, (minimum, 2147483647))
        field = "value"
    else:
        raise ValidationError("This field is calculated or is not editable here.")
    if type(expected) is not int and expected is not None:
        raise ValidationError("Supply the previously displayed integer value.")
    if getattr(instance, field) != expected:
        raise EditConflict("This value changed elsewhere. Reload to see the latest value; your edit was not saved.")
    setattr(instance, field, value)
    if instance is sheet:
        # Validate the touched field without blocking repairs to unrelated legacy data.
        sheet._meta.get_field(field).clean(value, sheet)
        if field.rsplit("_", 1)[-1] in ("base", "alloc", "bonus", "cs"):
            stat = field.rsplit("_", 1)[0]
            if stat in STAT_NAMES:
                sheet.get_stat_breakdown(stat)
        if field.endswith(("_rank", "_bonus")):
            skill = field.rsplit("_", 1)[0]
            if skill in SKILL_NAMES:
                sheet.get_effective_skill(skill)
    else:
        instance.full_clean()
    instance.save(update_fields=[field])
    if instance is not sheet and pokemon and actual_form:
        # Failure rolls back the capability write too.
        pokemon.get_effective_capabilities()
    return sheet
