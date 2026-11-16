from django.test import TestCase
from sheets.calculations import *
from sheets.choices import Nature

def check_calculations():
    # Nature amounts and minimum.
    assert apply_nature(5, Nature.CUDDLY, "hp") == 6
    assert apply_nature(2, Nature.CUDDLY, "atk") == 1
    assert apply_nature(1, Nature.HARDY, "atk") == 1

    # Add percentages before applying them.
    assert apply_percent_modifiers(20, (20, 30)) == 30

    # Stage limits and rounding.
    assert calculate_stat(stat="atk", base=11, stage=1)["final"] == 13
    assert calculate_stat(stat="atk", base=11, stage=-1)["final"] == 9
    assert calculate_stat(stat="atk", base=10, stage=6)["final"] == 22
    assert calculate_stat(stat="atk", base=10, stage=-6)["final"] == 4

    # Real HP and injury limit remain separate.
    assert real_max_hit_points(kind="pokemon", level=10, hp_stat=10) == 50
    assert real_max_hit_points(kind="character", level=10, hp_stat=10) == 60
    assert injury_healing_limit(50, 3) == 35
    assert injury_healing_limit(51, 3) == 35

    # Evasion caps apply at different points.
    evasion = calculate_evasion(40, bonus=5)
    assert evasion["stat_contribution"] == 6
    assert evasion["total"] == 11
    assert evasion["accuracy_check_increase"] == 9

    assert max_action_points(10) == 7
    assert trainer_power(3, 4) == 6
    assert trainer_high_jump(6) == 2
    assert trainer_overland(2, 2) == 5

    # Negative halves round downward.
    assert apply_speed_stage_to_movement(5, -1) == 4
    assert apply_speed_stage_to_movement(5, -6) == 2
    assert apply_speed_stage_to_movement(1, -6) == 1
    assert apply_speed_stage_to_movement(None, 6) is None

    print("All calculation checks passed.")

check_calculations()