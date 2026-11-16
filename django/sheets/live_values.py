"""JSON-friendly inputs and calculated outputs for the sheet testing interface."""
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from .constants import STAT_NAMES, SKILL_NAMES
from .editing import EDITABLE_FIELDS


def sheet_values(sheet):
    """Build a fresh snapshot without writing calculated values to the database."""
    outputs, warnings, groups = {}, [], []

    def calculated(key, function):
        try:
            value = function()
        except (ObjectDoesNotExist, ValidationError, ValueError) as error:
            warnings.append(f"{key}: {'; '.join(error.messages) if isinstance(error, ValidationError) else str(error)}")
            value = None
        outputs[key] = value
        return value

    def editor(field, label=None):
        low, high = EDITABLE_FIELDS[field]
        return {"target": field, "label": label or field.replace('_', ' ').title(),
                "value": getattr(sheet, field), "min": low, "max": high,
                "stage": field.endswith('_cs')}

    def output(key, label):
        return {"output": key, "label": label, "value": outputs.get(key)}

    calculated('max_hp', sheet.get_real_max_hit_points)
    calculated('healing_limit', sheet.get_healing_limit)
    groups.append({"name": "Health", "fields": [
        editor('current_hit_points', 'Current HP'), output('max_hp', 'Max HP'),
        editor('temp_hit_points', 'Temporary HP'), editor('injuries'),
        output('healing_limit', 'Healing limit'),
    ]})
    for stat in STAT_NAMES:
        calculated(f'{stat}_effective', lambda s=stat: sheet.get_effective_stat(s))
        calculated(f'{stat}_before', lambda s=stat: sheet.get_stat_before_stages(s))
        fields = [editor(f'{stat}_{suffix}', suffix.title()) for suffix in ('base', 'alloc', 'bonus')]
        if stat != 'hp':
            fields.append(editor(f'{stat}_cs', 'Combat stage'))
        fields.extend([output(f'{stat}_before', 'Before stages'), output(f'{stat}_effective', 'Effective')])
        groups.append({"name": stat.upper().replace('_', ' '), "fields": fields})
    combat = [editor(field) for field in ('accuracy_cs', 'accuracy_bonus', 'evasion_cs', 'initiative_bonus', 'damage_bonus', 'damage_resistance_bonus', 'critical_range_bonus')]
    for category in ('physical', 'special', 'speed'):
        calculated(f'{category}_evasion', lambda c=category: sheet.get_evasion_breakdown(c)['total'])
        calculated(f'{category}_evasion_applied', lambda c=category: sheet.get_evasion_breakdown(c)['accuracy_check_increase'])
        combat.extend([editor(f'{category}_evasion_bonus'), output(f'{category}_evasion', f'{category.title()} evasion total'),
                       output(f'{category}_evasion_applied', f'{category.title()} evasion applied to AC')])
    calculated('accuracy', sheet.get_accuracy)
    calculated('initiative', sheet.get_initiative)
    combat.extend([output('accuracy', 'Accuracy total'), output('initiative', 'Initiative')])
    groups.append({"name": "Combat bonuses and evasion", "fields": combat})
    for skill in SKILL_NAMES:
        def roll(s=skill):
            result = sheet.get_effective_skill(s)
            return f"{result['rank']}d6 {result['bonus']:+d}"
        calculated(f'{skill}_roll', roll)
        groups.append({"name": skill.replace('_', ' ').title(), "fields": [
            editor(f'{skill}_rank', 'Local base rank'), editor(f'{skill}_bonus', 'Flat roll bonus'),
            output(f'{skill}_roll', 'Effective roll'),
        ]})
    capability_fields = []
    for entry in sheet.capabilities.select_related('capability'):
        if entry.capability.value_kind == 'Numeric':
            capability_fields.append({"target": f'capability:{entry.pk}', "label": f'{entry.capability.name} — local baseline',
                                      "value": entry.value, "min": 0, "max": 2147483647})
    profile = None
    if sheet.kind == 'pokemon':
        try:
            profile = sheet.pokemon_profile
        except ObjectDoesNotExist:
            pass
    effective_caps = []
    if profile and profile.active_form_id:
        for change in profile.active_form.capability_changes.select_related('capability'):
            if change.capability.value_kind == 'Numeric' and change.operation != 'Remove':
                capability_fields.append({"target": f'form_capability:{change.pk}',
                    "label": f'{change.capability.name} — active form {change.operation.lower()}',
                    "value": change.value, "min": -2147483648 if change.operation == 'Adjust' else 0, "max": 2147483647})
        result = calculated('capabilities', lambda: [
            {"name": entry['capability'].name, "value": entry['value']}
            for entry in profile.get_effective_capabilities().values()
        ])
        effective_caps = result or []
    else:
        effective_caps = [{"name": e.capability.name, "value": e.value} for e in sheet.capabilities.select_related('capability')]
        outputs['capabilities'] = effective_caps
    groups.append({"name": "Local capability values", "fields": capability_fields})
    trainer_caps = None
    if sheet.kind == 'character':
        trainer_caps = calculated('trainer_capabilities', lambda: sheet.character_profile.get_derived_capabilities())
    return {"groups": groups, "outputs": outputs, "warnings": warnings,
            "active_form_id": profile.active_form_id if profile else None,
            "effective_capabilities": effective_caps, "trainer_capabilities": trainer_caps}
