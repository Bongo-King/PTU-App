"""Field names shared by sheet creation and calculations."""

STAT_NAMES = (
    "hp",
    "atk",
    "def",
    "sp_atk",
    "sp_def",
    "speed",
)

SKILL_NAMES = (
    "acrobatics",
    "athletics",
    "combat",
    "stealth",
    "survival",
    "gen_ed",
    "med_ed",
    "occ_ed",
    "poke_ed",
    "tech_ed",
    "guile",
    "charm",
    "intimidate",
    "command",
    "intuition",
    "perception",
    "focus",
)

BASELINE_FIELDS = (
    tuple(f"{stat}_base" for stat in STAT_NAMES)
    + tuple(f"{skill}_rank" for skill in SKILL_NAMES)
    + tuple(f"{skill}_bonus" for skill in SKILL_NAMES)
)