"""
Operations that create or update multiple sheet records.
"""

from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction

from reference.models import SpeciesForm, Feature, Edge
from .models import SheetFeature, SheetEdge, StatSheet, CharacterProfile
from .permissions import DEFAULT_CONTROLLER, resolve_creation_controller, accessible_sheets

from .choices import CapabilityChangeOperation
from .constants import BASELINE_FIELDS, STAT_NAMES, SKILL_NAMES

from .editing import update_sheet_value
from .models import (
    StatSheet,
    PokemonProfile,
    CharacterProfile,
    PokemonForm,
    SheetCapability,
    SheetAbility,
    SheetMove,
    PokemonFormCapabilityChange,
    PokemonFormAbilityGrant,
)

def _save_validated(instance):
    """Validate and save an instance, then return it."""
    instance.full_clean()
    instance.save()
    return instance


def _reference_capabilities(form):
    """Return validated reference capability entries keyed by capability ID."""
    entries = {}

    for entry in form.capabilities.select_related("capability"):
        entry.full_clean()
        entries[entry.capability_id] = entry

    return entries









@transaction.atomic
def add_pokemon_form(*, pokemon, source_form, name=None, ability_replacements=None,):
    """
    Create a local form using differences between reference forms.

    ability_replacements maps a reference grant's ability ID to an
    alternative Ability instance, for duplicate-grant fallback selections.

    This creates the form but does not activate it.
    """
    if pokemon.pk is None or source_form.pk is None:
        raise ValidationError("Save the Pokémon and reference form first.")

    pokemon.full_clean()

    # Read current reference records when taking this snapshot.
    source = SpeciesForm.objects.get(pk=source_form.pk)
    base = SpeciesForm.objects.get(pk=pokemon.base_form_id)

    if source.species_id != pokemon.species_id:
        raise ValidationError(
            "The source form must belong to this Pokémon's species."
        )

    if pokemon.forms.filter(source_form=source).exists():
        raise ValidationError(
            "This Pokémon already has a local copy of that reference form."
        )

    is_base = source.pk == base.pk
    values = {}

    # Reference hp_base becomes local hp_delta, etc.
    for stat in STAT_NAMES:
        if stat == "hp":
            continue

        field = f"{stat}_base"
        values[f"{stat}_delta"] = (
            getattr(source, field) - getattr(base, field)
        )

    for skill in SKILL_NAMES:
        for suffix in ("rank", "bonus"):
            field = f"{skill}_{suffix}"
            values[f"{field}_delta"] = (
                getattr(source, field) - getattr(base, field)
            )

    local_form = _save_validated(
        PokemonForm(
            pokemon=pokemon,
            source_form=source,
            name=source.name if name is None else name,
            type_primary=source.type_primary,
            type_secondary=source.type_secondary,
            token_image=source.token_image.name or "",
            size=source.size,

            # Empty means use the editable sheet measurement.
            height=(
                source.height
                if not is_base and source.height != base.height
                else ""
            ),
            weight=(
                source.weight
                if not is_base and source.weight != base.weight
                else ""
            ),
            weight_class=(
                source.weight_class
                if not is_base
                and source.weight_class != base.weight_class
                else None
            ),
            **values,
        )
    )

    base_caps = _reference_capabilities(base)
    source_caps = _reference_capabilities(source)

    for capability_id in sorted(base_caps.keys() | source_caps.keys()):
        before = base_caps.get(capability_id)
        after = source_caps.get(capability_id)

        if before is None:
            operation = CapabilityChangeOperation.GRANT
            value = after.value

        elif after is None:
            operation = CapabilityChangeOperation.REMOVE
            value = None

        elif before.value != after.value:
            # Matching numeric capabilities get a signed difference.
            if before.value is None or after.value is None:
                raise ValidationError(
                    "Inconsistent reference capability values."
                )

            operation = CapabilityChangeOperation.ADJUST
            value = after.value - before.value

        else:
            continue

        _save_validated(
            PokemonFormCapabilityChange(
                form=local_form,
                capability_id=capability_id,
                operation=operation,
                value=value,
            )
        )

    # Copy this form's ability grants into local records.
    replacements = dict(ability_replacements or {})
    grants = list(source.ability_grants.select_related("ability"))
    grant_ids = {grant.ability_id for grant in grants}

    if set(replacements) - grant_ids:
        raise ValidationError(
            "A replacement was supplied for an ability this form does not grant."
        )

    owned_ids = set(
        pokemon.sheet.abilities.values_list("ability_id", flat=True)
    )
    natural_ids = set(
        pokemon.species.ability_slots.values_list("ability_id", flat=True)
    )
    selected_ids = set()

    for grant in grants:
        chosen = grant.ability

        if grant.ability_id in replacements:
            if grant.ability_id not in owned_ids:
                raise ValidationError(
                    "A fallback is only needed when the granted ability "
                    "is already known."
                )

            chosen = replacements[grant.ability_id]

            if chosen.pk not in natural_ids:
                raise ValidationError(
                    "The fallback must be a naturally available species ability."
                )

        if chosen.pk in owned_ids:
            raise ValidationError(
                f"{chosen.name} is already known. Select an eligible "
                "alternative with ability_replacements."
            )

        if chosen.pk in selected_ids:
            raise ValidationError(
                "Two form grants cannot resolve to the same ability."
            )

        _save_validated(
            PokemonFormAbilityGrant(
                form=local_form,
                ability=chosen,
            )
        )
        selected_ids.add(chosen.pk)

    return local_form











@transaction.atomic
def create_pokemon(
    *,
    user,
    campaign,
    base_form,
    name,
    controller=DEFAULT_CONTROLLER,
    level=1,
    gender="",
    nature="",
    associated_character=None,
    natural_abilities=(),
    extra_abilities=(),
    moves=(),
    base_ability_replacements=None,
 
):
    """
    Create a Pokémon with its own editable baseline and local base form.

    natural_abilities: selected SpeciesAbility records.
    extra_abilities: selected Ability records without natural slot mapping.
    moves: selected Move records.

    Nature is stored but its stat effects are not applied here.
    Current HP is initialized to the calculated maximum after creation.
    """
    controller = resolve_creation_controller(
        user=user,
        campaign=campaign,
        controller=controller,
    )

    if base_form.pk is None:
        raise ValidationError("Save the reference base form first.")

    if level < 1:
        raise ValidationError("Level must be at least 1.")

    base = SpeciesForm.objects.get(pk=base_form.pk)

    baseline = {
        field: getattr(base, field)
        for field in BASELINE_FIELDS
    }

    sheet = _save_validated(
        StatSheet(
            campaign=campaign,
            controller=controller,
            kind=StatSheet.Kind.POKEMON,
            name=name,
            gender=gender,
            level=level,
            height=base.height,
            weight=base.weight,
            weight_class=base.weight_class,
            **baseline,
        )
    )

    pokemon = _save_validated(
        PokemonProfile(
            sheet=sheet,
            species=base.species,
            base_form=base,
            nature=nature,
            associated_character=associated_character,
        )
    )

    for entry in _reference_capabilities(base).values():
        _save_validated(
            SheetCapability(
                sheet=sheet,
                capability=entry.capability,
                value=entry.value,
            )
        )

    for selection in natural_abilities:
        selection.full_clean()

        if selection.species_id != pokemon.species_id:
            raise ValidationError(
                "A selected natural ability belongs to another species."
            )

        _save_validated(
            SheetAbility(
                sheet=sheet,
                ability=selection.ability,
                tier=selection.tier,
                slot=selection.slot,
            )
        )

    for ability in extra_abilities:
        _save_validated(
            SheetAbility(sheet=sheet, ability=ability)
        )

    for move in moves:
        _save_validated(
            SheetMove(sheet=sheet, move=move)
        )

    local_base = add_pokemon_form(
        pokemon=pokemon,
        source_form=base,
        ability_replacements=base_ability_replacements,
    )

    pokemon.active_form = local_base
    _save_validated(pokemon)

    sheet = pokemon.sheet
    sheet.current_hit_points = sheet.get_real_max_hit_points()
    sheet.full_clean()
    sheet.save(update_fields=["current_hit_points"])


    return pokemon

@transaction.atomic
def change_pokemon_form(*, user, sheet_id, form_id):
    """Activate an existing local form after checking access and ownership.

    This service is independent of HTTP and can also be called by a React API.
    Only active_form is persisted; baselines, abilities, moves and HP stay saved
    exactly as they were. Return a freshly loaded profile with its new form.
    """


    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")

    try:
        pokemon = PokemonProfile.objects.select_for_update().get(sheet_id=sheet_id)
    except PokemonProfile.DoesNotExist:
        raise ValidationError("This sheet does not have a Pokémon profile.") from None

    try:
        form = pokemon.forms.get(pk=form_id)
    except (PokemonForm.DoesNotExist, ValueError, TypeError, OverflowError):
        raise ValidationError("Select a local form belonging to this Pokémon.") from None

    form.full_clean()
    pokemon.active_form = form
    pokemon.full_clean()
    # An acquired ability may now conflict with a previously created form grant.
    # Validate the candidate before saving so a failed switch leaves the old form active.
    pokemon.get_effective_abilities()
    pokemon.get_effective_capabilities()
    pokemon.save(update_fields=["active_form"])
    return pokemon


#======================================= CHARACTER SHEET SERVICES ==================================
#===================================================================================================

@transaction.atomic
def create_character(
    *,
    user,
    campaign,
    name="New Trainer",
    controller=DEFAULT_CONTROLLER,
):
    """Create a starter trainer sheet with full HP and AP."""

    # 1. Check creation permissions and choose the controller.
    controller = resolve_creation_controller(
        user=user,
        campaign=campaign,
        controller=controller,
    )

    # 2. Start every skill at Untrained.
    skill_defaults = {
        f"{skill}_rank": 2
        for skill in SKILL_NAMES
    }

    # 3. Build the local sheet from our starter template.
    # Other fields use their existing model defaults:
    # zero allocations, bonuses, stages, injuries, and temporary HP.
    sheet = StatSheet(
        campaign=campaign,
        controller=controller,
        kind=StatSheet.Kind.CHARACTER,
        name=name,
        level=1,
        hp_base=10,
        atk_base=5,
        def_base=5,
        sp_atk_base=5,
        sp_def_base=5,
        speed_base=5,
        **skill_defaults,
    )

    # Initialize current HP using the existing calculation.
    sheet.current_hit_points = sheet.get_real_max_hit_points()
    sheet.full_clean()
    sheet.save()

    # 4. Create the linked trainer profile with full AP.
    character = CharacterProfile(sheet=sheet)
    character.current_ap = character.get_max_action_points()
    character.full_clean()
    character.save()

    return character



#======================================= ADD FEATURES/EDGES ==================================



@transaction.atomic
def add_sheet_feature(user, sheet_id, feature_id, *, notes=""):
    """Add one feature acquisition to a sheet the user can edit."""

    # 1. Check permission to edit this sheet.
    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")

    # 2. Retrieve the reusable reference definition.
    try:
        feature = Feature.objects.get(pk=feature_id)
    except Feature.DoesNotExist:
        raise ValidationError("The selected feature does not exist.") from None

    # 3. Construct the individual acquisition.
    entry = SheetFeature(
        sheet_id=sheet_id,
        feature=feature,
        notes=notes,
    )

    # 4. Validate its fields and any model-level rules.
    entry.full_clean()

    # 5. Save and return the new acquisition.
    entry.save()
    return entry

@transaction.atomic
def add_sheet_edge(user, sheet_id, edge_id, *, notes=""):
    """Add one feature acquisition to a sheet the user can edit."""

    # 1. Check permission to edit this sheet.
    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")

    # 2. Retrieve the reusable reference definition.
    try:
        edge = Edge.objects.get(pk=edge_id)
    except Edge.DoesNotExist:
        raise ValidationError("The selected edge does not exist.") from None

    # 3. Construct the individual acquisition.
    entry = SheetEdge(
        sheet_id=sheet_id,
        edge=edge,
        notes=notes,
    )

    # 4. Validate its fields and any model-level rules.
    entry.full_clean()

    # 5. Save and return the new acquisition.
    entry.save()
    return entry

@transaction.atomic
def update_sheet_feature(user, sheet_id, entry_id, *, notes):
    """Update the notes for one feature acquisition on a sheet."""

    # 1. Check permission to edit this sheet.
    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")

    # 2. Retrieve this acquisition, restricted to this sheet.
    try:
        entry = SheetFeature.objects.select_for_update().get(
            pk=entry_id,
            sheet_id=sheet_id,
        )
    except SheetFeature.DoesNotExist:
        raise ValidationError(
            "The selected feature acquisition does not exist on this sheet."
        ) from None

    # 3. Apply and validate the change.
    entry.notes = notes
    entry.full_clean()

    # 4. Save only the field we intended to change.
    entry.save(update_fields=["notes"])
    return entry


@transaction.atomic
def update_sheet_edge(user, sheet_id, entry_id, *, notes=""):

    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet."
                               
    )

    try:
        entry = SheetEdge.objects.get(
            pk=entry_id,
            sheet_id=sheet_id,
        )
    except SheetEdge.DoesNotExist:
        raise ValidationError("The selected edge does not exist.") from None

    entry.notes = notes
    entry.full_clean()

    # 4. Save only the field we intended to change.
    entry.save(update_fields=["notes"])
    return entry


@transaction.atomic
def remove_sheet_feature(user, sheet_id, entry_id):
    """Remove one feature acquisition from a sheet."""

    # 1. Check permission to edit this sheet.
    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")

    # 2. Retrieve the acquisition belonging to this sheet.
    try:
        entry = SheetFeature.objects.select_for_update().get(
            pk=entry_id,
            sheet_id=sheet_id,
        )
    except SheetFeature.DoesNotExist:
        raise ValidationError(
            "The selected feature acquisition does not exist on this sheet."
        ) from None

    # 3. Delete this acquisition.
    entry.delete()


@transaction.atomic
def remove_sheet_edge(user, sheet_id, entry_id):
    """Remove one edge acquisition from a sheet."""

    # 1. Check permission to edit this sheet.
    if not accessible_sheets(user).filter(pk=sheet_id).exists():
        raise PermissionDenied("You do not have access to this sheet.")

    # 2. Retrieve the acquisition belonging to this sheet.
    try:
        entry = SheetEdge.objects.select_for_update().get(
            pk=entry_id,
            sheet_id=sheet_id,
        )
    except SheetEdge.DoesNotExist:
        raise ValidationError(
            "The selected edge acquisition does not exist on this sheet."
        ) from None

    # 3. Delete this acquisition.
    entry.delete()



    
