from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from campaigns.models import Campaign, CampaignMembership

from .constants import SKILL_NAMES, STAT_NAMES
from .models import CharacterProfile, StatSheet
from .services import create_character


class CharacterCreationTests(TestCase):
    """Test the starter template, creation permissions, and rollback."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.gm = User.objects.create_user(username="gm")
        cls.member = User.objects.create_user(username="member")
        cls.other_member = User.objects.create_user(username="other_member")
        cls.outsider = User.objects.create_user(username="outsider")

        cls.campaign = Campaign.objects.create(
            name="Test campaign",
            gm=cls.gm,
        )

        for user in (cls.member, cls.other_member):
            CampaignMembership.objects.create(
                campaign=cls.campaign,
                user=user,
            )

        # Deliberately don't add the GM as a member.
        # Being the campaign's GM should be sufficient.

    def test_starter_template(self):
        character = create_character(
            user=self.member,
            campaign=self.campaign,
        )

        # Read saved values, rather than only the returned Python objects.
        character.refresh_from_db()
        sheet = StatSheet.objects.get(pk=character.sheet_id)

        self.assertEqual(sheet.name, "New Trainer")
        self.assertEqual(sheet.kind, StatSheet.Kind.CHARACTER)
        self.assertEqual(sheet.campaign_id, self.campaign.pk)
        self.assertEqual(sheet.controller_id, self.member.pk)
        self.assertEqual(sheet.level, 1)
        self.assertEqual(sheet.xp, 0)

        for stat in STAT_NAMES:
            with self.subTest(stat=stat):
                expected_base = 10 if stat == "hp" else 5
                self.assertEqual(
                    getattr(sheet, f"{stat}_base"),
                    expected_base,
                )
                self.assertEqual(getattr(sheet, f"{stat}_alloc"), 0)
                self.assertEqual(getattr(sheet, f"{stat}_bonus"), 0)

        for skill in SKILL_NAMES:
            with self.subTest(skill=skill):
                self.assertEqual(getattr(sheet, f"{skill}_rank"), 2)
                self.assertEqual(getattr(sheet, f"{skill}_bonus"), 0)

        for field in (
            "atk_cs",
            "def_cs",
            "sp_atk_cs",
            "sp_def_cs",
            "speed_cs",
            "accuracy_cs",
            "evasion_cs",
            "accuracy_bonus",
            "physical_evasion_bonus",
            "special_evasion_bonus",
            "speed_evasion_bonus",
            "damage_bonus",
            "damage_resistance_bonus",
            "critical_range_bonus",
            "initiative_bonus",
            "injuries",
            "temp_hit_points",
        ):
            with self.subTest(field=field):
                self.assertEqual(getattr(sheet, field), 0)

        self.assertEqual(sheet.current_hit_points, 42)
        self.assertEqual(sheet.get_real_max_hit_points(), 42)
        self.assertEqual(sheet.get_healing_limit(), 42)
        self.assertEqual(character.current_ap, 5)
        self.assertEqual(character.get_max_action_points(), 5)

        self.assertEqual(StatSheet.objects.count(), 1)
        self.assertEqual(CharacterProfile.objects.count(), 1)
        self.assertEqual(sheet.character_profile.pk, character.pk)

    def test_custom_name(self):
        character = create_character(
            user=self.member,
            campaign=self.campaign,
            name="Borya",
        )

        self.assertEqual(character.sheet.name, "Borya")

    def test_member_can_explicitly_assign_themselves(self):
        character = create_character(
            user=self.member,
            campaign=self.campaign,
            controller=self.member,
        )

        self.assertEqual(character.sheet.controller_id, self.member.pk)

    def test_member_cannot_assign_someone_else_or_leave_unassigned(self):
        for controller in (self.other_member, self.gm, None):
            with self.subTest(controller=controller):
                with self.assertRaises(PermissionDenied):
                    create_character(
                        user=self.member,
                        campaign=self.campaign,
                        controller=controller,
                    )

        self.assertEqual(StatSheet.objects.count(), 0)
        self.assertEqual(CharacterProfile.objects.count(), 0)

    def test_gm_defaults_to_unassigned_without_membership(self):
        character = create_character(
            user=self.gm,
            campaign=self.campaign,
        )

        self.assertIsNone(character.sheet.controller_id)

    def test_gm_can_choose_self_member_or_unassigned(self):
        for controller in (self.gm, self.member, None):
            with self.subTest(controller=controller):
                character = create_character(
                    user=self.gm,
                    campaign=self.campaign,
                    controller=controller,
                )

                expected_id = controller.pk if controller is not None else None
                self.assertEqual(
                    character.sheet.controller_id,
                    expected_id,
                )

    def test_gm_cannot_assign_a_campaign_outsider(self):
        with self.assertRaises(ValidationError):
            create_character(
                user=self.gm,
                campaign=self.campaign,
                controller=self.outsider,
            )

        self.assertEqual(StatSheet.objects.count(), 0)
        self.assertEqual(CharacterProfile.objects.count(), 0)

    def test_outsider_and_anonymous_user_cannot_create(self):
        for user in (self.outsider, AnonymousUser()):
            with self.subTest(user=str(user)):
                with self.assertRaises(PermissionDenied):
                    create_character(
                        user=user,
                        campaign=self.campaign,
                    )

        self.assertEqual(StatSheet.objects.count(), 0)
        self.assertEqual(CharacterProfile.objects.count(), 0)

    def test_membership_in_another_campaign_is_not_enough(self):
        other_campaign = Campaign.objects.create(
            name="Another campaign",
            gm=self.gm,
        )
        CampaignMembership.objects.create(
            campaign=other_campaign,
            user=self.outsider,
        )

        with self.assertRaises(PermissionDenied):
            create_character(
                user=self.outsider,
                campaign=self.campaign,
            )

        self.assertEqual(StatSheet.objects.count(), 0)

    def test_invalid_sheet_does_not_leave_records(self):
        max_length = StatSheet._meta.get_field("name").max_length

        with self.assertRaises(ValidationError):
            create_character(
                user=self.member,
                campaign=self.campaign,
                name="X" * (max_length + 1),
            )

        self.assertEqual(StatSheet.objects.count(), 0)
        self.assertEqual(CharacterProfile.objects.count(), 0)

    def test_profile_failure_rolls_back_the_saved_sheet(self):
        # Force a failure after the service has saved the StatSheet.
        with patch(
            "sheets.services.CharacterProfile.full_clean",
            side_effect=ValidationError("Simulated profile failure"),
        ):
            with self.assertRaises(ValidationError):
                create_character(
                    user=self.member,
                    campaign=self.campaign,
                )

        self.assertEqual(StatSheet.objects.count(), 0)
        self.assertEqual(CharacterProfile.objects.count(), 0)