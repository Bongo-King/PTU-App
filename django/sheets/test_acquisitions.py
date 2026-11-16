from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from campaigns.models import Campaign
from reference.models import Edge, Feature

from .models import SheetAccess, SheetEdge, SheetFeature, StatSheet
from .services import (
    add_sheet_edge,
    add_sheet_feature,
    update_sheet_edge,
    update_sheet_feature,
    remove_sheet_edge,
    remove_sheet_feature,
)


class SheetAcquisitionTests(TestCase):
    """Test edge and feature acquisitions independently of the frontend."""

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.gm = User.objects.create_user(username="gm")
        cls.owner = User.objects.create_user(username="owner")
        cls.granted_user = User.objects.create_user(username="granted")
        cls.outsider = User.objects.create_user(username="outsider")

        cls.campaign = Campaign.objects.create(
            name="Test campaign",
            gm=cls.gm,
        )

        cls.sheet = StatSheet.objects.create(
            campaign=cls.campaign,
            controller=cls.owner,
            kind=StatSheet.Kind.CHARACTER,
            name="Test trainer",
        )

        # The same owner can access both sheets. This lets us test
        # acquisition ownership separately from user permissions.
        cls.other_sheet = StatSheet.objects.create(
            campaign=cls.campaign,
            controller=cls.owner,
            kind=StatSheet.Kind.CHARACTER,
            name="Another trainer",
        )

        SheetAccess.objects.create(
            sheet=cls.sheet,
            user=cls.granted_user,
        )

        cls.feature = Feature.objects.create(
            name="Test feature",
            frequency="Static",
            effect="Reference feature effect.",
        )

        cls.edge = Edge.objects.create(
            name="Test edge",
            kind="Other",
            effect="Reference edge effect.",
        )

    def acquisition_cases(self):
        """Run the same behavioral checks against both acquisition types."""
        return [
            (
                "feature",
                self.feature,
                SheetFeature,
                add_sheet_feature,
                update_sheet_feature,
                remove_sheet_feature,
            ),
            (
                "edge",
                self.edge,
                SheetEdge,
                add_sheet_edge,
                update_sheet_edge,
                remove_sheet_edge,
            ),
        ]

    def test_add_creates_acquisition_with_notes(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                entry = add(
                    self.owner,
                    self.sheet.pk,
                    reference.pk,
                    notes="First selection",
                )

                saved = model.objects.get(pk=entry.pk)

                self.assertEqual(saved.sheet_id, self.sheet.pk)
                self.assertEqual(
                    getattr(saved, f"{kind}_id"),
                    reference.pk,
                )
                self.assertEqual(saved.notes, "First selection")

    def test_repeated_acquisitions_are_separate(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                first = add(
                    self.owner,
                    self.sheet.pk,
                    reference.pk,
                    notes="Selection one",
                )
                second = add(
                    self.owner,
                    self.sheet.pk,
                    reference.pk,
                    notes="Selection two",
                )

                self.assertNotEqual(first.pk, second.pk)
                self.assertEqual(
                    model.objects.filter(sheet=self.sheet).count(),
                    2,
                )

    def test_update_changes_only_selected_acquisition(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                first = add(
                    self.owner,
                    self.sheet.pk,
                    reference.pk,
                    notes="Original",
                )
                second = add(
                    self.owner,
                    self.sheet.pk,
                    reference.pk,
                    notes="Keep this",
                )

                update(
                    self.owner,
                    self.sheet.pk,
                    first.pk,
                    notes="Updated",
                )

                first.refresh_from_db()
                second.refresh_from_db()

                self.assertEqual(first.notes, "Updated")
                self.assertEqual(second.notes, "Keep this")

                # Explicitly passing empty text should clear the notes.
                update(
                    self.owner,
                    self.sheet.pk,
                    first.pk,
                    notes="",
                )
                first.refresh_from_db()
                self.assertEqual(first.notes, "")

    def test_remove_preserves_other_acquisitions_and_reference(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                first = add(self.owner, self.sheet.pk, reference.pk)
                second = add(self.owner, self.sheet.pk, reference.pk)
                first_id = first.pk

                remove(self.owner, self.sheet.pk, first_id)

                self.assertFalse(model.objects.filter(pk=first_id).exists())
                self.assertTrue(model.objects.filter(pk=second.pk).exists())
                self.assertTrue(
                    type(reference).objects.filter(pk=reference.pk).exists()
                )

    def test_gm_controller_and_granted_user_can_manage_acquisitions(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            for user in (self.gm, self.owner, self.granted_user):
                with self.subTest(kind=kind, user=user.username):
                    entry = add(user, self.sheet.pk, reference.pk)

                    update(
                        user,
                        self.sheet.pk,
                        entry.pk,
                        notes="Allowed",
                    )
                    entry.refresh_from_db()
                    self.assertEqual(entry.notes, "Allowed")

                    entry_id = entry.pk
                    remove(user, self.sheet.pk, entry_id)

                    self.assertFalse(
                        model.objects.filter(pk=entry_id).exists()
                    )

    def test_outsider_cannot_add_update_or_remove(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                entry = add(
                    self.owner,
                    self.sheet.pk,
                    reference.pk,
                    notes="Unchanged",
                )

                with self.assertRaises(PermissionDenied):
                    add(self.outsider, self.sheet.pk, reference.pk)

                with self.assertRaises(PermissionDenied):
                    update(
                        self.outsider,
                        self.sheet.pk,
                        entry.pk,
                        notes="Unauthorized change",
                    )

                with self.assertRaises(PermissionDenied):
                    remove(self.outsider, self.sheet.pk, entry.pk)

                entry.refresh_from_db()
                self.assertEqual(entry.notes, "Unchanged")
                self.assertEqual(
                    model.objects.filter(sheet=self.sheet).count(),
                    1,
                )

    def test_acquisition_must_belong_to_selected_sheet(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                entry = add(
                    self.owner,
                    self.other_sheet.pk,
                    reference.pk,
                    notes="Other sheet",
                )

                with self.assertRaises(ValidationError):
                    update(
                        self.owner,
                        self.sheet.pk,
                        entry.pk,
                        notes="Wrong sheet",
                    )

                with self.assertRaises(ValidationError):
                    remove(self.owner, self.sheet.pk, entry.pk)

                entry.refresh_from_db()
                self.assertEqual(entry.notes, "Other sheet")

    def test_missing_reference_does_not_create_acquisition(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                missing_id = reference.pk
                reference.delete()

                with self.assertRaises(ValidationError):
                    add(self.owner, self.sheet.pk, missing_id)

                self.assertFalse(
                    model.objects.filter(sheet=self.sheet).exists()
                )

    def test_deleted_acquisition_cannot_be_updated_or_removed_again(self):
        for kind, reference, model, add, update, remove in self.acquisition_cases():
            with self.subTest(kind=kind):
                entry = add(self.owner, self.sheet.pk, reference.pk)
                entry_id = entry.pk
                remove(self.owner, self.sheet.pk, entry_id)

                with self.assertRaises(ValidationError):
                    update(
                        self.owner,
                        self.sheet.pk,
                        entry_id,
                        notes="No longer exists",
                    )

                with self.assertRaises(ValidationError):
                    remove(self.owner, self.sheet.pk, entry_id)




