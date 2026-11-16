"""
calculations.py

Pure calculations for character and Pokémon sheets.

These functions do not modify models or save database records.
Percentage inputs use whole percentage points: 20 means +20%.
"""

from .choices import Nature
from .constants import STAT_NAMES


# Each tuple contains (raised stat, lowered stat).
NATURE_STATS = {
    Nature.CUDDLY: ("hp", "atk"),
    Nature.DISTRACTED: ("hp", "def"),
    Nature.PROUD: ("hp", "sp_atk"),
    Nature.DECISIVE: ("hp", "sp_def"),
    Nature.PATIENT: ("hp", "speed"),

    Nature.DESPERATE: ("atk", "hp"),
    Nature.LONELY: ("atk", "def"),
    Nature.ADAMANT: ("atk", "sp_atk"),
    Nature.NAUGHTY: ("atk", "sp_def"),
    Nature.BRAVE: ("atk", "speed"),

    Nature.STARK: ("def", "hp"),
    Nature.BOLD: ("def", "atk"),
    Nature.IMPISH: ("def", "sp_atk"),
    Nature.LAX: ("def", "sp_def"),
    Nature.RELAXED: ("def", "speed"),

    Nature.CURIOUS: ("sp_atk", "hp"),
    Nature.MODEST: ("sp_atk", "atk"),
    Nature.MILD: ("sp_atk", "def"),
    Nature.RASH: ("sp_atk", "sp_def"),
    Nature.QUIET: ("sp_atk", "speed"),

    Nature.DREAMY: ("sp_def", "hp"),
    Nature.CALM: ("sp_def", "atk"),
    Nature.GENTLE: ("sp_def", "def"),
    Nature.CAREFUL: ("sp_def", "sp_atk"),
    Nature.SASSY: ("sp_def", "speed"),

    Nature.SKITTISH: ("speed", "hp"),
    Nature.TIMID: ("speed", "atk"),
    Nature.HASTY: ("speed", "def"),
    Nature.JOLLY: ("speed", "sp_atk"),
    Nature.NAIVE: ("speed", "sp_def"),

    Nature.COMPOSED: ("hp", "hp"),
    Nature.HARDY: ("atk", "atk"),
    Nature.DOCILE: ("def", "def"),
    Nature.BASHFUL: ("sp_atk", "sp_atk"),
    Nature.QUIRKY: ("sp_def", "sp_def"),
    Nature.SERIOUS: ("speed", "speed"),
}


def _require_integer(value, name, minimum=None, maximum=None):
    """Reject invalid inputs rather than silently correcting stored mistakes."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer.")

    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be at least {minimum}.")

    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be at most {maximum}.")


def _validate_stat(stat):
    if stat not in STAT_NAMES:
        raise ValueError(f"Unknown stat: {stat}")


def _validate_stage(stage):
    _require_integer(stage, "Combat stage", minimum=-6, maximum=6)


def nature_modifier(nature, stat):
    """Return the flat nature modifier for one stat."""
    _validate_stat(stat)

    # Characters and Pokémon with no selected nature receive no modifier.
    if nature is None or nature == "":
        return 0

    if nature not in NATURE_STATS:
        raise ValueError(f"Unknown nature: {nature}")

    raised, lowered = NATURE_STATS[nature]

    # Neutral natures must not trigger intermediate minimum-value clamping.
    if raised == lowered:
        return 0

    amount = 1 if stat == "hp" else 2

    if stat == raised:
        return amount

    if stat == lowered:
        return -amount

    return 0


def apply_nature(base_value, nature, stat):
    """Apply nature to a base stat, with a minimum result of 1."""
    _require_integer(base_value, "Base stat", minimum=0)
    return max(1, base_value + nature_modifier(nature, stat))


def apply_percent_modifiers(value, modifiers=()):
    """
    Add percentage modifiers, apply them once, and round down.

    Example: modifiers=(20, 30) produces a total +50% adjustment.
    Only combine effects that apply to the same underlying value.
    """
    _require_integer(value, "Value", minimum=0)

    modifiers = tuple(modifiers)
    for modifier in modifiers:
        _require_integer(modifier, "Percentage modifier")

    multiplier_percent = 100 + sum(modifiers)

    if multiplier_percent < 0:
        raise ValueError("Percentage modifiers would produce a negative value.")

    return value * multiplier_percent // 100


def combat_stage_percent(stage):
    """Convert a combat stage to its additive percentage modifier."""
    _validate_stage(stage)

    if stage >= 0:
        return 20 * stage

    return 10 * stage


def calculate_stat(
    *,
    stat,
    base,
    form_delta=0,
    nature="",
    allocated=0,
    flat_bonus=0,
    stage=0,
    percent_modifiers=(),
):
    """
    Return a stat breakdown.

    Flat bonuses are applied before stages.
    Additional percentages are combined with the stage percentage.
    """
    _validate_stat(stat)
    _require_integer(base, "Base stat", minimum=0)
    _require_integer(form_delta, "Form difference")
    _require_integer(allocated, "Allocated points")
    _require_integer(flat_bonus, "Flat bonus")
    _validate_stage(stage)

    if stat == "hp" and (form_delta != 0 or stage != 0):
        raise ValueError("HP cannot have form differences or combat stages.")

    form_adjusted_base = base + form_delta

    if form_adjusted_base < 0:
        raise ValueError("The form-adjusted base stat cannot be negative.")

    adjusted_base = apply_nature(form_adjusted_base, nature, stat)
    before_percentages = adjusted_base + allocated + flat_bonus

    if before_percentages < 0:
        raise ValueError("The stat before percentage modifiers cannot be negative.")

    extra_percentages = tuple(percent_modifiers)
    stage_percent = combat_stage_percent(stage)

    final = apply_percent_modifiers(
        before_percentages,
        (stage_percent,) + extra_percentages,
    )

    return {
        "base": base,
        "form_delta": form_delta,
        "form_adjusted_base": form_adjusted_base,
        "nature_modifier": nature_modifier(nature, stat),
        "nature_adjusted_base": adjusted_base,
        "allocated": allocated,
        "flat_bonus": flat_bonus,
        "before_percentages": before_percentages,
        "stage": stage,
        "stage_percent": stage_percent,
        "extra_percent": sum(extra_percentages),
        "final": final,
    }


def real_max_hit_points(*, kind, level, hp_stat):
    """Calculate real maximum HP, unaffected by injuries."""
    _require_integer(level, "Level", minimum=1)
    _require_integer(hp_stat, "HP stat", minimum=0)

    if kind == "pokemon":
        level_contribution = level
    elif kind == "character":
        level_contribution = level * 2
    else:
        raise ValueError(f"Unknown sheet kind: {kind}")

    return level_contribution + hp_stat * 3 + 10


def injury_healing_limit(real_max_hp, injuries):
    """
    Calculate the injury-adjusted healing limit.

    Does not alter current HP. Returns zero at ten or more injuries;
    this does not implement any separate death/incapacitation rules.
    """
    _require_integer(real_max_hp, "Real maximum HP", minimum=0)
    _require_integer(injuries, "Injuries", minimum=0)

    remaining_tenths = max(0, 10 - injuries)
    return real_max_hp * remaining_tenths // 10


def calculate_evasion(combat_stat, *, bonus=0, evasion_stage=0):
    """Return stat contribution, total evasion, and the usable AC increase."""
    _require_integer(combat_stat, "Combat stat", minimum=0)
    _require_integer(bonus, "Evasion bonus")
    _validate_stage(evasion_stage)

    stat_contribution = min(6, combat_stat // 5)
    total = max(0, stat_contribution + bonus + evasion_stage)

    return {
        "stat_contribution": stat_contribution,
        "total": total,
        "accuracy_check_increase": min(9, total),
    }


def calculate_accuracy(*, bonus=0, stage=0):
    """Calculate the accuracy modifier; only the stage is capped at ±6."""
    _require_integer(bonus, "Accuracy bonus")
    _validate_stage(stage)
    return bonus + stage


def calculate_initiative(speed, bonus=0):
    """Use current Speed after stages, plus the initiative bonus."""
    _require_integer(speed, "Speed", minimum=0)
    _require_integer(bonus, "Initiative bonus")
    return speed + bonus


def max_action_points(level):
    """Calculate a character's maximum AP without changing current AP."""
    _require_integer(level, "Level", minimum=1)
    return 5 + level // 5


def trainer_power(athletics_rank, combat_rank):
    """Calculate Power from the applicable skill ranks."""
    _require_integer(athletics_rank, "Athletics rank", minimum=1)
    _require_integer(combat_rank, "Combat rank", minimum=1)

    return 4 + int(athletics_rank >= 3) + int(combat_rank >= 4)


def trainer_high_jump(acrobatics_rank, *, running_start=False):
    """Calculate High Jump, including an optional situational running start."""
    _require_integer(acrobatics_rank, "Acrobatics rank", minimum=1)

    return (
        int(acrobatics_rank >= 4)
        + int(acrobatics_rank >= 6)
        + int(running_start)
    )


def trainer_long_jump(acrobatics_rank):
    _require_integer(acrobatics_rank, "Acrobatics rank", minimum=1)
    return acrobatics_rank // 2


def trainer_overland(athletics_rank, acrobatics_rank):
    """Calculate Overland before Speed-stage adjustments."""
    _require_integer(athletics_rank, "Athletics rank", minimum=1)
    _require_integer(acrobatics_rank, "Acrobatics rank", minimum=1)

    return 3 + (athletics_rank + acrobatics_rank) // 2


def trainer_swim(overland_before_speed_stages):
    """Use unadjusted Overland so Speed stages aren't counted twice."""
    _require_integer(
        overland_before_speed_stages, "Unadjusted Overland", minimum=0
    )
    return overland_before_speed_stages // 2


def trainer_throwing_range(athletics_rank):
    _require_integer(athletics_rank, "Athletics rank", minimum=1)
    return 4 + athletics_rank


def apply_speed_stage_to_movement(movement, speed_stage):
    """
    Apply Speed stages to an existing movement capability.

    None means the movement mode is absent.
    A penalty never raises a baseline that was already below 2.
    """
    _validate_stage(speed_stage)

    if movement is None:
        return None

    _require_integer(movement, "Movement speed", minimum=0)
    adjustment = speed_stage // 2

    if adjustment < 0:
        return max(min(movement, 2), movement + adjustment)

    return movement + adjustment