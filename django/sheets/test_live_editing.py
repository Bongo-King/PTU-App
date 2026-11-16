"""Local edits and their recalculated JSON responses use an isolated test DB."""
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from campaigns.models import Campaign, CampaignMembership
from reference.models import Capability, FormCapability, Species, SpeciesForm
from .constants import STAT_NAMES, SKILL_NAMES
from .editing import EditConflict
from .models import CharacterProfile, SheetAccess, SheetCapability, StatSheet
from .services import create_pokemon, add_pokemon_form, change_pokemon_form, update_sheet_value


class LiveEditingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner, cls.gm, cls.guest, cls.outsider = [users.objects.create_user(username=n) for n in ('owner', 'gm', 'guest', 'outsider')]
        cls.campaign = Campaign.objects.create(name='Campaign', gm=cls.gm)
        CampaignMembership.objects.create(
            campaign=cls.campaign,
            user=cls.owner,
        )
        species = Species.objects.create(name='Species')
        values = {f'{s}_base': 10 for s in STAT_NAMES}
        values.update({f'{s}_rank': 2 for s in SKILL_NAMES})
        cls.source = SpeciesForm.objects.create(species=species, name='Base', type_primary='Normal', **values)
        values.update(atk_base=15, combat_rank=4)
        alternate = SpeciesForm.objects.create(species=species, name='Alternate', type_primary='Fire', **values)
        cls.numeric = Capability.objects.create(name='Overland', value_kind='Numeric', description='Movement', is_movement_speed=True)
        cls.description = Capability.objects.create(name='Descriptive', value_kind='Description', description='No number')
        FormCapability.objects.create(form=cls.source, capability=cls.numeric, value=5)
        FormCapability.objects.create(form=alternate, capability=cls.numeric, value=7)
        cls.pokemon = create_pokemon(
            user=cls.gm,
            campaign=cls.campaign,
            base_form=cls.source,
            controller=cls.owner,
            name="Local",
            level=10,
        )

        cls.sheet = cls.pokemon.sheet
        cls.sheet.current_hit_points = 45
        cls.sheet.save(update_fields=["current_hit_points"])
        cls.base_id = cls.pokemon.active_form_id
        cls.alt = add_pokemon_form(pokemon=cls.pokemon, source_form=alternate)
        cls.cap_entry = cls.sheet.capabilities.get(capability=cls.numeric)
        cls.desc_entry = SheetCapability.objects.create(sheet=cls.sheet, capability=cls.description)
        SheetAccess.objects.create(sheet=cls.sheet, user=cls.guest)
        cls.url = reverse('sheets:edit_value', args=[cls.sheet.pk])
        cls.detail = reverse('sheets:detail', args=[cls.sheet.pk])

    def edit(self, target, value, expected, **kwargs):
        return update_sheet_value(user=kwargs.pop('user', self.owner), sheet_id=self.sheet.pk,
                                  target=target, value=value, expected=expected,
                                  active_form_id=kwargs.pop('active_form_id', self.base_id), **kwargs)

    def post(self, target, value, expected, **kwargs):
        self.client.force_login(self.owner)
        return self.client.post(self.url, json.dumps(dict(target=target, value=value, expected=expected,
                                active_form_id=kwargs.get('active_form_id', self.base_id))), content_type='application/json')

    def test_health_independent_and_limits_derived(self):
        self.edit('current_hit_points', -5, 45)
        self.edit('temp_hit_points', 12, 0)
        response = self.post('injuries', 3, 0)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['outputs']['max_hp'], 50)
        self.assertEqual(response.json()['outputs']['healing_limit'], 35)
        self.sheet.refresh_from_db()
        self.assertEqual((self.sheet.current_hit_points, self.sheet.temp_hit_points), (-5, 12))

    def test_base_hp_updates_limits_without_clamping_current(self):
        response = self.post('hp_base', 1, 10)
        self.assertEqual(response.json()['outputs']['max_hp'], 23)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.current_hit_points, 45)

    def test_derived_and_privileged_fields_cannot_be_written(self):
        for field in ('max_hp', 'healing_limit', 'physical_evasion', 'controller_id', 'campaign_id', 'kind', 'hp_cs'):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self.edit(field, 5, 0)

    def test_stage_limits_and_integer_only(self):
        for value in (-7, 7, 1.5, True, '2', None, 999999999999999999):
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.edit('atk_cs', value, 0)
        self.edit('atk_cs', 6, 0)
        self.edit('atk_cs', -6, 6)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.atk_cs, -6)

    def test_negative_temp_hp_injuries_and_allocation_rejected(self):
        for field in ('temp_hit_points', 'injuries', 'atk_alloc'):
            with self.assertRaises(ValidationError):
                self.edit(field, -1, 0)

    def test_stats_edit_locally_and_respect_form_differences(self):
        self.edit('atk_base', 12, 10)
        self.edit('atk_alloc', 3, 0)
        self.edit('atk_bonus', 1, 0)
        self.edit('atk_cs', 2, 0)
        profile = change_pokemon_form(user=self.owner, sheet_id=self.sheet.pk, form_id=self.alt.pk)
        self.assertEqual(profile.get_effective_stat('atk'), 29)
        self.source.refresh_from_db()
        self.assertEqual(self.source.atk_base, 10)

    def test_skill_rank_and_flat_bonus_recalculate(self):
        self.edit('combat_rank', 3, 2)
        response = self.post('combat_bonus', 2, 0)
        self.assertEqual(response.json()['outputs']['combat_roll'], '3d6 +2')
        profile = change_pokemon_form(user=self.owner, sheet_id=self.sheet.pk, form_id=self.alt.pk)
        self.assertEqual(profile.get_effective_skill('combat'), {'rank': 5, 'bonus': 2})
        for value in (0, 7):
            with self.assertRaises(ValidationError):
                self.edit('combat_rank', value, 3, active_form_id=self.alt.pk)

    def test_evasion_bonus_changes_total_not_stat_cap(self):
        response = self.post('physical_evasion_bonus', 10, 0)
        self.assertEqual(response.json()['outputs']['physical_evasion'], 12)
        self.assertEqual(response.json()['outputs']['physical_evasion_applied'], 9)

    def test_baseline_numeric_capability_edit(self):
        self.edit(f'capability:{self.cap_entry.pk}', 8, 5)
        profile = change_pokemon_form(user=self.owner, sheet_id=self.sheet.pk, form_id=self.alt.pk)
        self.assertEqual(profile.get_effective_capabilities()[self.numeric.pk]['value'], 10)
        self.assertEqual(self.source.capabilities.get(capability=self.numeric).value, 5)

    def test_active_form_numeric_adjustment_edit(self):
        change_pokemon_form(user=self.owner, sheet_id=self.sheet.pk, form_id=self.alt.pk)
        change = self.alt.capability_changes.get(capability=self.numeric)
        response = self.post(f'form_capability:{change.pk}', 4, 2, active_form_id=self.alt.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['effective_capabilities'][0]['value'], 9)
        self.cap_entry.refresh_from_db()
        self.assertEqual(self.cap_entry.value, 5)

    def test_invalid_capability_edit_rolls_back(self):
        change_pokemon_form(user=self.owner, sheet_id=self.sheet.pk, form_id=self.alt.pk)
        change = self.alt.capability_changes.get(capability=self.numeric)
        with self.assertRaises(ValidationError):
            self.edit(f'form_capability:{change.pk}', -20, 2, active_form_id=self.alt.pk)
        change.refresh_from_db()
        self.assertEqual(change.value, 2)

    def test_descriptive_and_inactive_form_capabilities_rejected(self):
        for target in (f'capability:{self.desc_entry.pk}', f'form_capability:{self.alt.capability_changes.get().pk}'):
            with self.assertRaises(ValidationError):
                self.edit(target, 2, None)

    def test_foreign_capability_id_cannot_be_edited(self):
        sheet = StatSheet.objects.create(campaign=self.campaign, kind='character')
        entry = SheetCapability.objects.create(sheet=sheet, capability=self.numeric, value=5)
        with self.assertRaises(ValidationError):
            self.edit(f'capability:{entry.pk}', 9, 5)
        entry.refresh_from_db()
        self.assertEqual(entry.value, 5)

    def test_stale_field_rejected(self):
        self.edit('injuries', 2, 0)
        response = self.post('injuries', 3, 0)
        self.assertEqual(response.status_code, 409)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.injuries, 2)

    def test_stale_form_rejected(self):
        change_pokemon_form(user=self.owner, sheet_id=self.sheet.pk, form_id=self.alt.pk)
        response = self.post('injuries', 1, 0)
        self.assertEqual(response.status_code, 409)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.injuries, 0)

    def test_access_grants_and_gm_may_edit(self):
        self.edit('injuries', 1, 0, user=self.gm)
        self.edit('injuries', 2, 1, user=self.guest)

    def test_outsider_cannot_edit(self):
        with self.assertRaises(PermissionDenied):
            self.edit('injuries', 1, 0, user=self.outsider)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.url, '{}', content_type='application/json').status_code, 404)

    def test_revoked_grant_cannot_edit(self):
        SheetAccess.objects.filter(sheet=self.sheet, user=self.guest).delete()
        with self.assertRaises(PermissionDenied):
            self.edit('injuries', 1, 0, user=self.guest)

    def test_endpoint_requires_post_and_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.get(self.url).status_code, 405)
        data = dict(target='injuries', value=1, expected=0, active_form_id=self.base_id)
        self.assertEqual(client.post(self.url, data, content_type='application/json').status_code, 403)
        client.get(self.detail)
        self.assertEqual(client.post(self.url, data, content_type='application/json', HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value).status_code, 200)

    def test_invalid_json_and_payload(self):
        self.client.force_login(self.owner)
        for data in ('{', '[]', '{}', 'null', '{"target":"injuries"}'):
            self.assertEqual(self.client.post(self.url, data, content_type='application/json').status_code, 400)

    def test_calculation_failure_leaves_previous_value(self):
        with self.assertRaises(ValueError):
            self.edit('atk_bonus', -100, 0)
        self.sheet.refresh_from_db()
        self.assertEqual(self.sheet.atk_bonus, 0)

    def test_character_edits_recompute_trainer_capabilities(self):
        sheet = StatSheet.objects.create(campaign=self.campaign, controller=self.owner, kind='character', name='Trainer',
                    **{f'{s}_rank': 2 for s in SKILL_NAMES}, **{f'{s}_base': 10 for s in STAT_NAMES})
        CharacterProfile.objects.create(sheet=sheet)
        update_sheet_value(user=self.owner, sheet_id=sheet.pk, target='athletics_rank', value=4, expected=2, active_form_id=None)
        sheet.refresh_from_db()
        self.assertEqual(sheet.character_profile.get_derived_capabilities()['overland'], 6)

    def test_editor_renders_separate_health_outputs_and_inputs(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.detail)
        for field in ('current_hit_points', 'temp_hit_points', 'injuries', 'atk_base', 'atk_alloc', 'atk_bonus', 'atk_cs', 'combat_rank', 'combat_bonus'):
            self.assertContains(response, f'data-target="{field}"')
        for field in ('max_hp', 'healing_limit', 'physical_evasion'):
            self.assertContains(response, f'data-output="{field}"')
            self.assertNotContains(response, f'data-target="{field}"')
        self.assertContains(response, '<select id="edit-atk_cs"')
        self.assertNotContains(response, 'data-target="hp_cs"')
