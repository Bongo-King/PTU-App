"""Run with python manage.py test sheets; all fixtures use the test database."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from campaigns.models import Campaign, CampaignMembership
from reference.models import Ability, Capability, FormAbilityGrant, FormCapability, Move, Species, SpeciesAbility, SpeciesForm
from . import calculations as calc
from .choices import Nature
from .constants import SKILL_NAMES, STAT_NAMES
from .models import CharacterProfile, PokemonForm, PokemonProfile, SheetAccess, StatSheet
from .services import add_pokemon_form, create_pokemon


class CalculationTests(SimpleTestCase):
    def test_every_nature_has_a_mapping(self):
        for nature in Nature.values:
            for stat in STAT_NAMES:
                with self.subTest(nature=nature, stat=stat):
                    self.assertIsInstance(calc.nature_modifier(nature, stat), int)

    def test_nature_floor_and_neutral(self):
        self.assertEqual(calc.apply_nature(2, Nature.CUDDLY, "atk"), 1)
        self.assertEqual(calc.apply_nature(5, Nature.CUDDLY, "hp"), 6)
        self.assertEqual(calc.apply_nature(1, Nature.HARDY, "atk"), 1)

    def test_stages_can_reduce_stat_to_zero(self):
        self.assertEqual(calc.calculate_stat(stat="atk", base=1, stage=-6)["final"], 0)

    def test_percentages_are_additive(self):
        self.assertEqual(calc.apply_percent_modifiers(20, (20, 30)), 30)
        self.assertEqual(calc.calculate_stat(stat="atk", base=21, stage=2, percent_modifiers=(20,))["final"], 33)

    def test_stage_rounding_and_limits(self):
        for stage, expected in ((1, 13), (-1, 9), (6, 24), (-6, 4)):
            with self.subTest(stage=stage):
                self.assertEqual(calc.calculate_stat(stat="atk", base=11, stage=stage)["final"], expected)
        for stage in (-7, 7):
            with self.assertRaises(ValueError):
                calc.calculate_stat(stat="atk", base=10, stage=stage)

    def test_hp_and_injury_rounding(self):
        self.assertEqual(calc.real_max_hit_points(kind="pokemon", level=10, hp_stat=10), 50)
        self.assertEqual(calc.real_max_hit_points(kind="character", level=10, hp_stat=10), 60)
        self.assertEqual(calc.injury_healing_limit(51, 3), 35)
        self.assertEqual(calc.injury_healing_limit(50, 10), 0)

    def test_evasion_caps(self):
        self.assertEqual(calc.calculate_evasion(40, bonus=5),
                         {"stat_contribution": 6, "total": 11, "accuracy_check_increase": 9})
        self.assertEqual(calc.calculate_evasion(1, evasion_stage=-6)["total"], 0)

    def test_trainer_thresholds(self):
        self.assertEqual(calc.max_action_points(10), 7)
        self.assertEqual(calc.trainer_power(3, 4), 6)
        self.assertEqual(calc.trainer_high_jump(6), 2)
        self.assertEqual(calc.trainer_high_jump(6, running_start=True), 3)
        self.assertEqual(calc.trainer_overland(2, 2), 5)
        self.assertEqual(calc.trainer_long_jump(3), 1)

    def test_movement_floor_and_negative_halves(self):
        for value, stage, expected in ((5, -1, 4), (5, -6, 2), (1, -6, 1), (5, 6, 8), (None, 6, None)):
            with self.subTest(value=value, stage=stage):
                self.assertEqual(calc.apply_speed_stage_to_movement(value, stage), expected)


class PokemonFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        user = get_user_model()
        cls.gm = user.objects.create_user(username="gm")
        cls.owner = user.objects.create_user(username="owner")
        cls.viewer = user.objects.create_user(username="viewer")
        cls.outsider = user.objects.create_user(username="outsider")
        cls.campaign = Campaign.objects.create(name="North", gm=cls.gm)
        CampaignMembership.objects.create(campaign=cls.campaign, user=cls.owner,)
        cls.species = Species.objects.create(name="Test species")
        values = {f"{stat}_base": 10 for stat in STAT_NAMES}
        values.update({f"{skill}_rank": 2 for skill in SKILL_NAMES})
        cls.base = SpeciesForm.objects.create(species=cls.species, name="Standard", type_primary="Fire", **values)
        values.update(atk_base=15, speed_base=14, combat_rank=4, combat_bonus=1)
        cls.alternate = SpeciesForm.objects.create(species=cls.species, name="Special", type_primary="Ice", **values)
        cls.movement = Capability.objects.create(name="Overland", value_kind="Numeric", description="Movement", is_movement_speed=True)
        cls.descriptive = Capability.objects.create(name="Special capability", value_kind="Description", description="Form only")
        cls.removed = Capability.objects.create(name="Base capability", value_kind="Description", description="Base only")
        FormCapability.objects.create(form=cls.base, capability=cls.movement, value=5)
        FormCapability.objects.create(form=cls.alternate, capability=cls.movement, value=7)
        FormCapability.objects.create(form=cls.alternate, capability=cls.descriptive)
        FormCapability.objects.create(form=cls.base, capability=cls.removed)
        cls.ability = Ability.objects.create(name="Normal ability", frequency="Static", effect="Always available")
        cls.grant = Ability.objects.create(name="Form ability", frequency="Static", effect="Only while active")
        cls.selection = SpeciesAbility.objects.create(species=cls.species, ability=cls.ability, tier="Basic", slot=1)
        FormAbilityGrant.objects.create(form=cls.alternate, ability=cls.grant)
        cls.pokemon = create_pokemon(user=cls.gm, campaign=cls.campaign, base_form=cls.base, name="Test Pokémon",
                                     controller=cls.owner, level=10, nature=Nature.ADAMANT, natural_abilities=[cls.selection])
        # Creation initializes full HP. These tests need a damaged Pokémon, so we damage it post-initialization.
        cls.pokemon.sheet.current_hit_points = 45
        cls.pokemon.sheet.save(update_fields=["current_hit_points"])
        cls.local_base = cls.pokemon.active_form
        cls.local_alt = add_pokemon_form(pokemon=cls.pokemon, source_form=cls.alternate)

    def activate(self, form):
        self.pokemon.active_form = form
        self.pokemon.save(update_fields=["active_form"])
        # Retrieve afresh to exercise the same relationship caching as an HTTP request.
        self.pokemon = PokemonProfile.objects.select_related("sheet", "active_form").get(pk=self.pokemon.pk)


class PokemonServiceTests(PokemonFixture):
    def test_creation_copies_selected_ability_and_baseline(self):
        self.assertEqual(self.pokemon.sheet.atk_base, 10)
        self.assertEqual(list(self.pokemon.sheet.abilities.values_list("ability_id", flat=True)), [self.ability.pk])
        self.assertEqual(self.pokemon.active_form_id, self.local_base.pk)

    def test_local_changes_survive_form_switches(self):
        sheet = self.pokemon.sheet
        sheet.combat_rank = 3
        sheet.atk_alloc = 3
        sheet.atk_bonus = 1
        sheet.save()
        for _ in range(3):
            self.activate(self.local_alt)
            self.assertEqual(self.pokemon.get_effective_skill("combat"), {"rank": 5, "bonus": 1})
            self.assertEqual(self.pokemon.get_effective_stat("atk"), 21)
            self.activate(self.local_base)
            self.assertEqual(self.pokemon.get_effective_stat("atk"), 16)
        sheet.refresh_from_db()
        self.assertEqual(sheet.atk_base, 10)
        self.assertEqual(sheet.combat_rank, 3)

    def test_reference_edits_do_not_change_existing_local_values(self):
        self.alternate.atk_base = 99
        self.alternate.save()
        self.base.atk_base = 99
        self.base.save()
        self.activate(self.local_alt)
        self.assertEqual(self.pokemon.get_effective_stat("atk"), 17)

    def test_capabilities_grant_adjust_remove_and_revert(self):
        before = dict(self.pokemon.sheet.capabilities.values_list("capability_id", "value"))
        self.activate(self.local_alt)
        caps = self.pokemon.get_effective_capabilities()
        self.assertEqual(caps[self.movement.pk]["value"], 7)
        self.assertIn(self.descriptive.pk, caps)
        self.assertNotIn(self.removed.pk, caps)
        self.activate(self.local_base)
        caps = self.pokemon.get_effective_capabilities()
        self.assertEqual(caps[self.movement.pk]["value"], 5)
        self.assertNotIn(self.descriptive.pk, caps)
        self.assertIn(self.removed.pk, caps)
        self.assertEqual(dict(self.pokemon.sheet.capabilities.values_list("capability_id", "value")), before)

    def test_abilities_and_types_follow_active_form(self):
        self.activate(self.local_alt)
        self.assertEqual({a.pk for a in self.pokemon.get_effective_abilities()}, {self.ability.pk, self.grant.pk})
        self.assertEqual(self.pokemon.get_effective_types(), ["Ice"])
        self.activate(self.local_base)
        self.assertEqual([a.pk for a in self.pokemon.get_effective_abilities()], [self.ability.pk])

    def test_hp_reads_never_rewrite_current_hp(self):
        sheet = self.pokemon.sheet
        sheet.injuries = 3
        sheet.save()
        for form in (self.local_base, self.local_alt):
            self.activate(form)
            self.assertEqual(self.pokemon.sheet.get_real_max_hit_points(), 50)
            self.assertEqual(self.pokemon.sheet.get_healing_limit(), 35)
        sheet.refresh_from_db()
        self.assertEqual(sheet.current_hit_points, 45)

    def test_failed_creation_is_atomic(self):
        models = (StatSheet, PokemonProfile, PokemonForm)
        counts = [model.objects.count() for model in models]

        with self.assertRaises(ValidationError):
            create_pokemon(
                user=self.gm,
                campaign=self.campaign,
                base_form=self.base,
                name="Bad",
                nature="Invalid",
            )

        self.assertEqual(
            [model.objects.count() for model in models],
            counts,
        )

    def test_duplicate_source_form_rejected(self):
        with self.assertRaises(ValidationError):
            add_pokemon_form(pokemon=self.pokemon, source_form=self.alternate)

    def test_other_species_form_rejected(self):
        other = Species.objects.create(name="Other")
        form = SpeciesForm.objects.create(species=other, name="Other", type_primary="Normal")
        with self.assertRaises(ValidationError):
            add_pokemon_form(pokemon=self.pokemon, source_form=form)

    def test_staged_stats_initiative_and_movement(self):
        sheet = self.pokemon.sheet
        sheet.atk_alloc = 3
        sheet.atk_bonus = 1
        sheet.atk_cs = 2
        sheet.speed_cs = 1
        sheet.initiative_bonus = 2
        sheet.save()
        self.activate(self.local_alt)
        self.assertEqual(self.pokemon.get_effective_stat("atk"), 29)
        self.assertEqual(self.pokemon.get_effective_stat("atk", percent_modifiers=(20,)), 33)
        self.assertEqual(self.pokemon.sheet.get_initiative(), 18)
        sheet.speed_cs = -3
        sheet.save()
        self.activate(self.local_alt)
        self.assertEqual(self.pokemon.get_effective_capabilities()[self.movement.pk]["value"], 5)

    def test_ability_conflict_rolls_back_form_then_accepts_fallback(self):
        source = SpeciesForm.objects.create(species=self.species, name="Conflict", type_primary="Fire")
        FormAbilityGrant.objects.create(form=source, ability=self.ability)
        count = self.pokemon.forms.count()
        with self.assertRaises(ValidationError):
            add_pokemon_form(pokemon=self.pokemon, source_form=source)
        self.assertEqual(self.pokemon.forms.count(), count)
        SpeciesAbility.objects.create(species=self.species, ability=self.grant, tier="Advanced", slot=1)
        local = add_pokemon_form(pokemon=self.pokemon, source_form=source,
                                 ability_replacements={self.ability.pk: self.grant})
        self.assertEqual(local.ability_grants.get().ability_id, self.grant.pk)

    def test_other_campaign_move_rolls_back_creation(self):
        other = Campaign.objects.create(
            name="Other campaign",
            gm=self.gm,
        )

        move = Move.objects.create(
            campaign=other,
            name="Private move",
            type="Normal",
            category="Status",
            frequency="At-Will",
            range="Self",
        )

        models = (StatSheet, PokemonProfile, PokemonForm)
        counts = [model.objects.count() for model in models]

        with self.assertRaises(ValidationError):
            create_pokemon(
                user=self.gm,
                campaign=self.campaign,
                base_form=self.base,
                name="Bad move",
                moves=[move],
            )

        self.assertEqual(
            [model.objects.count() for model in models],
            counts,
        )

    def test_shared_move_can_be_selected(self):
        move = Move.objects.create(
            name="Shared move",
            type="Normal",
            category="Status",
            frequency="At-Will",
            range="Self",
        )

        pokemon = create_pokemon(
            user=self.gm,
            campaign=self.campaign,
            base_form=self.base,
            name="With move",
            moves=[move],
        )

        self.assertEqual(
            pokemon.sheet.moves.get().move_id,
            move.pk,
        )


class SheetPageTests(PokemonFixture):
    def setUp(self):
        self.url = reverse("sheets:detail", args=[self.pokemon.sheet_id])

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("login") + "?next=" + self.url)

    def test_gm_controller_and_granted_user_can_view(self):
        SheetAccess.objects.create(sheet=self.pokemon.sheet, user=self.viewer)
        for user in (self.gm, self.owner, self.viewer):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                self.assertContains(self.client.get(self.url), "Test Pokémon")

    def test_membership_alone_does_not_grant_access(self):
        CampaignMembership.objects.create(campaign=self.campaign, user=self.outsider)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)
        self.assertNotContains(self.client.get(reverse("sheets:list")), "Test Pokémon")

    def test_access_revocation(self):
        grant = SheetAccess.objects.create(sheet=self.pokemon.sheet, user=self.viewer)
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        grant.delete()
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_post_cannot_mutate_sheet(self):
        self.client.force_login(self.owner)
        self.assertEqual(self.client.post(self.url, {"current_hit_points": 0}).status_code, 405)
        self.pokemon.sheet.refresh_from_db()
        self.assertEqual(self.pokemon.sheet.current_hit_points, 45)

    def test_page_uses_effective_values_without_writes(self):
        self.activate(self.local_alt)
        self.client.force_login(self.owner)
        before = StatSheet.objects.values().get(pk=self.pokemon.sheet_id)
        response = self.client.get(self.url)
        self.assertContains(response, "Form ability")
        self.assertEqual(response.context["stats"][1][1]["final"], 17)
        self.assertEqual(before, StatSheet.objects.values().get(pk=self.pokemon.sheet_id))

    def test_notes_are_escaped(self):
        sheet = self.pokemon.sheet
        sheet.notes = "<script>alert(1)</script>"
        sheet.save()
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_missing_profile_is_displayed_without_server_error(self):
        sheet = StatSheet.objects.create(campaign=self.campaign, controller=self.owner, kind="pokemon", name="Incomplete")
        self.client.force_login(self.owner)
        self.assertContains(self.client.get(reverse("sheets:detail", args=[sheet.pk])), "Some values need attention")

    def test_character_page_and_ap(self):
        sheet = StatSheet.objects.create(campaign=self.campaign, controller=self.owner, kind="character", name="Trainer", level=10,
                                        **{f"{skill}_rank": 2 for skill in SKILL_NAMES})
        CharacterProfile.objects.create(sheet=sheet, current_ap=5)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("sheets:detail", args=[sheet.pk]))
        self.assertContains(response, "AP: 5 / 7")
        self.assertContains(response, "Standard trainer calculations")
