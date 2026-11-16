"""Form-switching regression tests, independent of the existing tests.py."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from reference.models import Ability, Capability, FormAbilityGrant, FormCapability, Species, SpeciesForm
from .constants import SKILL_NAMES, STAT_NAMES
from .models import SheetAbility, SheetAccess, StatSheet
from .services import add_pokemon_form, change_pokemon_form, create_pokemon


class FormChangeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()

        cls.owner, cls.gm, cls.granted, cls.outsider = [
            users.objects.create_user(username=name)
            for name in ("owner", "gm", "granted", "outsider")
        ]

        campaign = Campaign.objects.create(
            name="Test campaign",
            gm=cls.gm,
        )

        # The owner must belong to the campaign to receive a new sheet.
        CampaignMembership.objects.create(
            campaign=campaign,
            user=cls.owner,
        )

        # This user belongs to the campaign but has no sheet access.
        # Keep this membership: several tests deliberately check that distinction.
        CampaignMembership.objects.create(
            campaign=campaign,
            user=cls.outsider,
        )

        species = Species.objects.create(name="Test species")

        values = {
            f"{stat}_base": 10
            for stat in STAT_NAMES
        }
        values.update({
            f"{skill}_rank": 2
            for skill in SKILL_NAMES
        })

        base = SpeciesForm.objects.create(
            species=species,
            name="Base",
            type_primary="Fire",
            **values,
        )

        values.update(
            atk_base=15,
            combat_rank=4,
            combat_bonus=1,
        )

        alternate = SpeciesForm.objects.create(
            species=species,
            name="Alternate",
            type_primary="Ice",
            **values,
        )

        cls.ability = Ability.objects.create(
            name="Form grant",
            frequency="Static",
            effect="Form effect",
        )

        FormAbilityGrant.objects.create(
            form=alternate,
            ability=cls.ability,
        )

        cls.capability = Capability.objects.create(
            name="Overland",
            description="Movement",
            value_kind="Numeric",
            is_movement_speed=True,
        )

        FormCapability.objects.create(
            form=base,
            capability=cls.capability,
            value=5,
        )

        FormCapability.objects.create(
            form=alternate,
            capability=cls.capability,
            value=7,
        )

        # The GM explicitly assigns this sheet to a campaign member.
        cls.pokemon = create_pokemon(
            user=cls.gm,
            campaign=campaign,
            base_form=base,
            name="Test Pokémon",
            controller=cls.owner,
        )

        # Creation starts at full HP. Set up the damaged state afterward.
        cls.pokemon.sheet.current_hit_points = 31
        cls.pokemon.sheet.save(update_fields=["current_hit_points"])

        cls.base_id = cls.pokemon.active_form_id

        cls.alternate = add_pokemon_form(
            pokemon=cls.pokemon,
            source_form=alternate,
        )

        cls.other = create_pokemon(
            user=cls.gm,
            campaign=campaign,
            base_form=base,
            name="Other Pokémon",
            controller=cls.owner,
        )

        cls.other.sheet.current_hit_points = 20
        cls.other.sheet.save(update_fields=["current_hit_points"])

        SheetAccess.objects.create(
            sheet=cls.pokemon.sheet,
            user=cls.granted,
        )

        cls.url = reverse(
            "sheets:switch_form",
            args=[cls.pokemon.sheet_id],
        )

        cls.detail_url = reverse(
            "sheets:detail",
            args=[cls.pokemon.sheet_id],
        )

    def switch(self, form_id):
        return change_pokemon_form(user=self.owner, sheet_id=self.pokemon.sheet_id, form_id=form_id)

    def assert_base_active(self):
        self.pokemon.refresh_from_db()
        self.assertEqual(self.pokemon.active_form_id, self.base_id)

    def test_switch_and_revert_preserve_local_edits(self):
        sheet = self.pokemon.sheet
        sheet.combat_rank, sheet.atk_bonus, sheet.injuries, sheet.atk_cs = 3, 1, 2, 1
        sheet.save()
        baseline = StatSheet.objects.values().get(pk=sheet.pk)
        saved = [list(manager.values()) for manager in (sheet.capabilities, sheet.abilities, sheet.moves)]
        for _ in range(3):
            alternate = self.switch(self.alternate.pk)
            self.assertEqual(alternate.get_effective_skill('combat'), {'rank': 5, 'bonus': 1})
            self.assertEqual(alternate.get_effective_stat('atk'), 19)
            self.assertEqual(alternate.get_effective_types(), ['Ice'])
            self.assertEqual(alternate.get_effective_capabilities()[self.capability.pk]['value'], 7)
            self.assertEqual([a.pk for a in alternate.get_effective_abilities()], [self.ability.pk])
            base = self.switch(self.base_id)
            self.assertEqual(base.get_effective_skill('combat')['rank'], 3)
            self.assertEqual(base.get_effective_stat('atk'), 13)
            self.assertEqual(base.get_effective_abilities(), [])
        self.assertEqual(StatSheet.objects.values().get(pk=sheet.pk), baseline)
        self.assertEqual([list(manager.values()) for manager in (sheet.capabilities, sheet.abilities, sheet.moves)], saved)

    def test_only_active_form_is_written(self):
        with CaptureQueriesContext(connection) as queries:
            self.switch(self.alternate.pk)
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(('UPDATE ', 'INSERT ', 'DELETE '))]
        self.assertEqual(len(writes), 1)
        self.assertIn('"active_form_id"', writes[0])
        self.assertIn('"sheets_pokemonprofile"', writes[0])

    def test_same_form_is_safe(self):
        self.switch(self.base_id)
        self.assert_base_active()

    def test_service_checks_access(self):
        for user in (self.owner, self.gm, self.granted):
            result = change_pokemon_form(user=user, sheet_id=self.pokemon.sheet_id, form_id=self.alternate.pk)
            self.assertEqual(result.active_form_id, self.alternate.pk)
        for user in (self.outsider, AnonymousUser()):
            with self.assertRaises(PermissionDenied):
                change_pokemon_form(user=user, sheet_id=self.pokemon.sheet_id, form_id=self.base_id)

    def test_service_rejects_foreign_and_missing_forms(self):
        for form_id in (self.other.active_form_id, 9999999):
            with self.assertRaises(ValidationError):
                self.switch(form_id)
            self.assert_base_active()

    def test_selector_contains_only_owned_forms(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.detail_url)
        choices = response.context['form_selection'].fields['active_form'].queryset
        self.assertEqual(set(choices.values_list('pk', flat=True)), {self.base_id, self.alternate.pk})
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    def test_post_redirects_to_updated_values(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {'active_form': self.alternate.pk}, follow=True)
        self.assertRedirects(response, self.detail_url)
        self.assertContains(response, 'Active form updated.')
        self.assertContains(response, 'Form grant')
        self.assertEqual(response.context['types'], ['Ice'])

    def test_get_does_not_switch(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(self.url, {'active_form': self.alternate.pk}).status_code, 405)
        self.assert_base_active()

    def test_invalid_post_displays_errors_without_saving(self):
        self.client.force_login(self.owner)
        for value in ('', 'not-an-id', '9' * 100, self.other.active_form_id):
            with self.subTest(value=value):
                response = self.client.post(self.url, {'active_form': value})
                self.assertEqual(response.status_code, 400)
                self.assertTrue(response.context['form_selection'].errors)
                self.assert_base_active()

    def test_conflicting_ability_fails_service_and_renders_error(self):
        SheetAbility.objects.create(sheet=self.pokemon.sheet, ability=self.ability)
        with self.assertRaises(ValidationError):
            self.switch(self.alternate.pk)
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {'active_form': self.alternate.pk})
        self.assertContains(response, 'fallback selection', status_code=400)
        self.assert_base_active()

    def test_member_without_grant_cannot_post(self):
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(self.url, {'active_form': self.alternate.pk}).status_code, 404)
        self.assert_base_active()

    def test_revoked_access_is_checked_at_post_time(self):
        self.client.force_login(self.granted)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        SheetAccess.objects.filter(sheet=self.pokemon.sheet, user=self.granted).delete()
        self.assertEqual(self.client.post(self.url, {'active_form': self.alternate.pk}).status_code, 404)
        self.assert_base_active()

    def test_anonymous_post_redirects_to_login(self):
        self.assertRedirects(self.client.post(self.url, {'active_form': self.alternate.pk}), reverse('login') + '?next=' + self.url)
        self.assert_base_active()

    def test_csrf_required_and_valid_token_succeeds(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(self.url, {'active_form': self.alternate.pk}).status_code, 403)
        client.get(self.detail_url)
        response = client.post(self.url, {'active_form': self.alternate.pk, 'csrfmiddlewaretoken': client.cookies['csrftoken'].value})
        self.assertRedirects(response, self.detail_url)

    def test_character_cannot_switch(self):
        sheet = StatSheet.objects.create(campaign=self.pokemon.sheet.campaign, controller=self.owner, kind='character', name='Trainer')
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(reverse('sheets:switch_form', args=[sheet.pk]), {'active_form': self.alternate.pk}).status_code, 404)
        with self.assertRaises(ValidationError):
            change_pokemon_form(user=self.owner, sheet_id=sheet.pk, form_id=self.alternate.pk)

    def test_gm_created_pokemon_starts_full_and_unassigned(self):
        pokemon = create_pokemon(
            user=self.gm,
            campaign=self.pokemon.sheet.campaign,
            base_form=self.pokemon.base_form,
            name="New GM Pokémon",
            level=10,
        )

        sheet = StatSheet.objects.get(pk=pokemon.sheet_id)

        # Level 10 + (HP stat 10 × 3) + 10 = 50.
        self.assertEqual(sheet.current_hit_points, 50)
        self.assertEqual(
            sheet.current_hit_points,
            sheet.get_real_max_hit_points(),
        )
        self.assertIsNone(sheet.controller_id)


    def test_member_created_pokemon_defaults_to_member(self):
        pokemon = create_pokemon(
            user=self.owner,
            campaign=self.pokemon.sheet.campaign,
            base_form=self.pokemon.base_form,
            name="New member Pokémon",
        )

        sheet = StatSheet.objects.get(pk=pokemon.sheet_id)

        self.assertEqual(sheet.controller_id, self.owner.pk)
        self.assertEqual(sheet.current_hit_points, 41)
        self.assertEqual(
            sheet.current_hit_points,
            sheet.get_real_max_hit_points(),
        )