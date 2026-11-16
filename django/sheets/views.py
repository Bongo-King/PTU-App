"""Testing pages for sheet calculations and form switching."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST, require_safe

from .constants import SKILL_NAMES, STAT_NAMES
from .models import PokemonProfile, StatSheet
from .forms import PokemonFormSelectionForm
from .permissions import accessible_sheets
from .services import change_pokemon_form, update_sheet_value
from .live_values import sheet_values
from .editing import EditConflict
from django.http import JsonResponse
import json



@login_required
@require_safe
def sheet_list(request):
    """List only sheets the requesting user can access."""
    sheets = accessible_sheets(request.user).select_related("campaign").order_by("name", "pk")
    return render(request, "sheets/list.html", {"sheets": sheets})


@login_required
@require_safe
def sheet_detail(request, pk):
    """Present existing calculations without changing any saved values."""
    sheet = get_object_or_404(
        accessible_sheets(request.user).select_related("campaign", "controller"), pk=pk
    )
    warnings = []

    def read(label, function, default=None):
        try:
            return function()
        except (ValidationError, ValueError, ObjectDoesNotExist):
            warnings.append(f"{label} is unavailable. Check the sheet's profile, active form and saved values.")
            return default

    stats = [(name.upper().replace("_", " "), read(name, lambda n=name: sheet.get_stat_breakdown(n)))
             for name in STAT_NAMES]
    skills = [(name.replace("_", " ").title(), read(name, lambda n=name: sheet.get_effective_skill(n)))
              for name in SKILL_NAMES]
    context = {
        "sheet": sheet, "stats": stats, "skills": skills, "warnings": warnings,
        "real_hp": read("Maximum HP", sheet.get_real_max_hit_points),
        "healing_limit": read("Healing limit", sheet.get_healing_limit),
        "accuracy": read("Accuracy", sheet.get_accuracy),
        "initiative": read("Initiative", sheet.get_initiative),
        "evasions": [(kind.title(), read(kind, lambda k=kind: sheet.get_evasion_breakdown(k)))
                     for kind in ("physical", "special", "speed")],
        "moves": sheet.moves.select_related("move"),
    }
    if sheet.kind == StatSheet.Kind.POKEMON:
        profile = read("Pokémon profile", lambda: sheet.pokemon_profile)
        if profile:
            context.update({
                "profile": profile,
                "form_selection": PokemonFormSelectionForm(pokemon=profile),
                "types": read("Types", profile.get_effective_types, []),
                "abilities": read("Abilities", profile.get_effective_abilities, []),
                "capabilities": read("Capabilities", lambda: list(profile.get_effective_capabilities().values()), []),
            })
    else:
        context["abilities"] = [entry.ability for entry in sheet.abilities.select_related("ability")]
        context["capabilities"] = sheet.capabilities.select_related("capability")
        profile = read("Character profile", lambda: sheet.character_profile)
        if profile:
            context["max_ap"] = read("AP", profile.get_max_action_points)
            context["current_ap"] = profile.current_ap
            context["trainer_capabilities"] = read("Trainer capabilities", profile.get_derived_capabilities, {}).items()
    context["live_values"] = sheet_values(sheet)
    return render(request, "sheets/detail.html", context)


@login_required
@require_POST
def switch_form(request, pk):
    """Validate an HTML selection, call the service, then reload effective values."""
    sheet = get_object_or_404(accessible_sheets(request.user), pk=pk)
    pokemon = get_object_or_404(PokemonProfile, sheet=sheet)
    form = PokemonFormSelectionForm(request.POST, pokemon=pokemon)
    if form.is_valid():
        try:
            change_pokemon_form(
                user=request.user, sheet_id=sheet.pk,
                form_id=form.cleaned_data["active_form"].pk,
            )
        except ValidationError as error:
            form.add_error(None, error.messages)
        else:
            messages.success(request, "Active form updated.")
            return redirect("sheets:detail", pk=sheet.pk)
    return render(request, "sheets/change_form.html", {
        "sheet": sheet, "form_selection": form,
    }, status=400)


@login_required
@require_POST
def edit_value(request, pk):
    """Save one JSON edit and return freshly calculated values for the client."""
    get_object_or_404(accessible_sheets(request.user), pk=pk)
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or set(data) != {"target", "value", "expected", "active_form_id"}:
            raise ValidationError("Supply target, value, expected and active_form_id.")
        update_sheet_value(user=request.user, sheet_id=pk, **data)
    except EditConflict as error:
        return JsonResponse({"error": str(error)}, status=409)
    except (ValidationError, ValueError, UnicodeDecodeError) as error:
        errors = error.messages if isinstance(error, ValidationError) else ["Invalid JSON or field value."]
        return JsonResponse({"error": " ".join(errors)}, status=400)
    sheet = get_object_or_404(accessible_sheets(request.user), pk=pk)
    return JsonResponse(sheet_values(sheet))
