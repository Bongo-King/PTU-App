from django.conf import settings
from django.db import models

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator

from reference.choices import Type, CapabilityKind, AbilityTier
from .choices import CapabilityChangeOperation, Nature




class StatSheet(models.Model):
    #information found on the sheet of either a Character or Pokémon

    #the associated campaign
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="sheets",
    )

    #the sheet's controller (user)
    controller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="controlled_sheets",
    )

    #kind can be either "character" or "pokemon". it defines what the type of sheet is.
    class Kind(models.TextChoices):
        CHARACTER = "character", "Character"
        POKEMON = "pokemon", "Pokémon"

    kind = models.CharField(
        max_length=10,
        choices=Kind.choices,
    )

    token_image_override = models.ImageField(
        upload_to="tokens/sheets/",
        blank=True,
    )

    #generic character info
    name = models.CharField(blank=True, max_length=50)
    gender = models.CharField(blank=True, max_length= 15)
    level = models.PositiveSmallIntegerField(default=1)
    xp = models.PositiveSmallIntegerField(default=0)
    height = models.CharField(blank=True, max_length=10)
    weight = models.CharField(blank=True, max_length=10)
    weight_class = models.PositiveSmallIntegerField(blank=True, null=True,)
    notes = models.TextField(blank=True)


#COMBAT RELEVANT INFORMATION
    current_hit_points = models.SmallIntegerField(default=0)
    temp_hit_points = models.PositiveSmallIntegerField(default=0)
    injuries = models.PositiveSmallIntegerField(default=0)

    # Individual base stats.
    # For Pokémon, initially copied from the chosen reference base form.
    hp_base = models.PositiveSmallIntegerField(default=0)
    atk_base = models.PositiveSmallIntegerField(default=0)
    def_base = models.PositiveSmallIntegerField(default=0)
    sp_atk_base = models.PositiveSmallIntegerField(default=0)
    sp_def_base = models.PositiveSmallIntegerField(default=0)
    speed_base = models.PositiveSmallIntegerField(default=0)

    #allocated Stats
    hp_alloc = models.SmallIntegerField(default=0)
    atk_alloc = models.SmallIntegerField(default=0)
    def_alloc = models.SmallIntegerField(default=0)
    sp_atk_alloc = models.SmallIntegerField(default=0)
    sp_def_alloc = models.SmallIntegerField(default=0)
    speed_alloc = models.SmallIntegerField(default=0)

    #manual bonus stats
    hp_bonus = models.SmallIntegerField(default=0)
    atk_bonus = models.SmallIntegerField(default=0)
    def_bonus = models.SmallIntegerField(default=0)
    sp_atk_bonus = models.SmallIntegerField(default=0)
    sp_def_bonus = models.SmallIntegerField(default=0)
    speed_bonus = models.SmallIntegerField(default=0)
    accuracy_bonus = models.SmallIntegerField(default=0)
    physical_evasion_bonus = models.SmallIntegerField(default=0)
    special_evasion_bonus = models.SmallIntegerField(default=0)
    speed_evasion_bonus = models.SmallIntegerField(default=0)
    damage_bonus = models.SmallIntegerField(default=0)
    damage_resistance_bonus = models.SmallIntegerField(default=0)
    critical_range_bonus = models.SmallIntegerField(default=0)
    initiative_bonus = models.SmallIntegerField(default=0)

    #combat stages
    atk_cs = models.SmallIntegerField(default=0)
    def_cs = models.SmallIntegerField(default=0)
    sp_atk_cs = models.SmallIntegerField(default=0)
    sp_def_cs = models.SmallIntegerField(default=0)
    speed_cs = models.SmallIntegerField(default=0)
    accuracy_cs = models.SmallIntegerField(default=0)
    evasion_cs = models.SmallIntegerField(default=0)


#SKILLS
    #base skill ranks
    acrobatics_rank = models.SmallIntegerField(default=0)
    athletics_rank = models.SmallIntegerField(default=0)
    combat_rank = models.SmallIntegerField(default=0)
    stealth_rank = models.SmallIntegerField(default=0)
    survival_rank = models.SmallIntegerField(default=0)
    gen_ed_rank = models.SmallIntegerField(default=0)
    med_ed_rank = models.SmallIntegerField(default=0)
    occ_ed_rank = models.SmallIntegerField(default=0)
    poke_ed_rank = models.SmallIntegerField(default=0)
    tech_ed_rank = models.SmallIntegerField(default=0)
    guile_rank = models.SmallIntegerField(default=0)
    charm_rank = models.SmallIntegerField(default=0)
    intimidate_rank = models.SmallIntegerField(default=0)
    command_rank = models.SmallIntegerField(default=0)
    intuition_rank = models.SmallIntegerField(default=0)
    perception_rank = models.SmallIntegerField(default=0)
    focus_rank = models.SmallIntegerField(default=0)

    #skill modifiers
    acrobatics_bonus = models.SmallIntegerField(default=0)
    athletics_bonus = models.SmallIntegerField(default=0)
    combat_bonus = models.SmallIntegerField(default=0)
    stealth_bonus = models.SmallIntegerField(default=0)
    survival_bonus = models.SmallIntegerField(default=0)
    gen_ed_bonus = models.SmallIntegerField(default=0)
    med_ed_bonus = models.SmallIntegerField(default=0)
    occ_ed_bonus = models.SmallIntegerField(default=0)
    poke_ed_bonus = models.SmallIntegerField(default=0)
    tech_ed_bonus = models.SmallIntegerField(default=0)
    guile_bonus = models.SmallIntegerField(default=0)
    charm_bonus = models.SmallIntegerField(default=0)
    intimidate_bonus = models.SmallIntegerField(default=0)
    command_bonus = models.SmallIntegerField(default=0)
    intuition_bonus = models.SmallIntegerField(default=0)
    perception_bonus = models.SmallIntegerField(default=0)
    focus_bonus = models.SmallIntegerField(default=0)

    def __str__(self):
        return (
            f"{self.campaign.name} — {self.name} "
            f"(controller: {self.controller})"
        )

class SheetAccess(models.Model):
    sheet = models.ForeignKey(
        StatSheet,
        on_delete=models.CASCADE,
        related_name="access_grants",
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sheet_access_grants",
    )

    #this is a unique relationship. A given user and sheet cannot be associated multiple times.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "user"],
                name="unique_sheet_access",
            )
        ]

    def __str__(self):
        return f"{self.sheet.name} — {self.user}"


#==================================== Pokemon Profile Sheet ================================
#===========================================================================================


class PokemonProfile(models.Model):
    """Information specific to one individual Pokémon."""

    sheet = models.OneToOneField(
        "StatSheet",
        on_delete=models.CASCADE,
        related_name="pokemon_profile",
    )

    species = models.ForeignKey(
        "reference.Species",
        on_delete=models.PROTECT,
        related_name="pokemon_profiles",
    )

    # Reference form originally used to populate the individual baseline.
    base_form = models.ForeignKey(
        "reference.SpeciesForm",
        on_delete=models.PROTECT,
        related_name="base_for_pokemon",
    )

    # The individual's currently selected LOCAL form.
    active_form = models.ForeignKey(
        "PokemonForm",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="active_for_profiles",
    )

    # The nature of the pokemon
    nature = models.CharField(
        max_length=12,
        choices=Nature.choices,
        blank=True,
    )

    associated_character = models.ForeignKey(
        "CharacterProfile",
        on_delete=models.SET_NULL,
        related_name="pokemon_companions",
        blank=True,
        null=True,
    )



    def clean(self):
        """Validate the sheet, species, trainer, and active form."""
        super().clean()
        errors = {}

        # A Pokémon profile must belong to a Pokémon sheet.
        if self.sheet_id:
            if self.sheet.kind != StatSheet.Kind.POKEMON:
                errors["sheet"] = (
                    "A Pokémon profile must belong to a Pokémon sheet."
                )

        # Its reference base form must belong to its species.
        if self.base_form_id and self.species_id:
            if self.base_form.species_id != self.species_id:
                errors["base_form"] = (
                    "The base form must belong to the selected species."
                )

        # Its active LOCAL form must belong to this individual.
        if self.active_form_id:
            if (
                self.pk is None
                or self.active_form.pokemon_id != self.pk
            ):
                errors["active_form"] = (
                    "The active form must belong to this Pokémon."
                )

        # Its associated character must be in the same campaign.
        if self.associated_character_id and self.sheet_id:
            character_sheet = self.associated_character.sheet

            if character_sheet.campaign_id != self.sheet.campaign_id:
                errors["associated_character"] = (
                    "The associated character must be in the same campaign."
                )

        if errors:
            raise ValidationError(errors)

        

    def __str__(self):
        return f"{self.sheet.name} — {self.species.name}"



    

class PokemonForm(models.Model):
    '''
    Form-specific information for an individual pokemon.
     
    Stores LOCAL stat differences between the form and the base form, 
    type information, as well as any token override information and 
    size/weight classifications. Basically just SpeciesForm but for 
    specific instances of pokemon rather than the species as a whole.
    '''

    pokemon = models.ForeignKey(
        "PokemonProfile",
        on_delete=models.CASCADE,
        related_name="forms",
    )

    # Tracks which reference form supplied the original form data.
    source_form = models.ForeignKey(
        "reference.SpeciesForm",
        on_delete=models.PROTECT,
        related_name="local_forms",
    )

    name = models.CharField(max_length=100)
    height = models.CharField(max_length=100, blank=True)
    weight = models.CharField(max_length=100, blank=True)

    #form stat changes
    hp_delta = models.SmallIntegerField(default=0)
    atk_delta = models.SmallIntegerField(default=0)
    def_delta = models.SmallIntegerField(default=0)
    sp_atk_delta = models.SmallIntegerField(default=0)
    sp_def_delta = models.SmallIntegerField(default=0)
    speed_delta = models.SmallIntegerField(default=0)

    type_primary = models.CharField(
        max_length=10,
        choices=Type.choices,
    )
    type_secondary = models.CharField(
        max_length=10,
        choices=Type.choices,
        blank=True,
    )

    token_image = models.ImageField(
        upload_to="tokens/forms/",
        blank=True,
    )

    size = models.CharField(blank=True, max_length=15)
    weight_class = models.PositiveSmallIntegerField( blank=True, null=True,)

    #SKILLS
    #form base skill changes
    acrobatics_rank_delta = models.SmallIntegerField(default=0)
    athletics_rank_delta = models.SmallIntegerField(default=0)
    combat_rank_delta = models.SmallIntegerField(default=0)
    stealth_rank_delta = models.SmallIntegerField(default=0)
    survival_rank_delta = models.SmallIntegerField(default=0)
    gen_ed_rank_delta = models.SmallIntegerField(default=0)
    med_ed_rank_delta = models.SmallIntegerField(default=0)
    occ_ed_rank_delta = models.SmallIntegerField(default=0)
    poke_ed_rank_delta = models.SmallIntegerField(default=0)
    tech_ed_rank_delta = models.SmallIntegerField(default=0)
    guile_rank_delta = models.SmallIntegerField(default=0)
    charm_rank_delta = models.SmallIntegerField(default=0)
    intimidate_rank_delta = models.SmallIntegerField(default=0)
    command_rank_delta = models.SmallIntegerField(default=0)
    intuition_rank_delta = models.SmallIntegerField(default=0)
    perception_rank_delta = models.SmallIntegerField(default=0)
    focus_rank_delta = models.SmallIntegerField(default=0)

    #form skill modifier changes
    acrobatics_bonus_delta = models.SmallIntegerField(default=0)
    athletics_bonus_delta = models.SmallIntegerField(default=0)
    combat_bonus_delta = models.SmallIntegerField(default=0)
    stealth_bonus_delta = models.SmallIntegerField(default=0)
    survival_bonus_delta = models.SmallIntegerField(default=0)
    gen_ed_bonus_delta = models.SmallIntegerField(default=0)
    med_ed_bonus_delta = models.SmallIntegerField(default=0)
    occ_ed_bonus_delta = models.SmallIntegerField(default=0)
    poke_ed_bonus_delta = models.SmallIntegerField(default=0)
    tech_ed_bonus_delta = models.SmallIntegerField(default=0)
    guile_bonus_delta = models.SmallIntegerField(default=0)
    charm_bonus_delta = models.SmallIntegerField(default=0)
    intimidate_bonus_delta = models.SmallIntegerField(default=0)
    command_bonus_delta = models.SmallIntegerField(default=0)
    intuition_bonus_delta = models.SmallIntegerField(default=0)
    perception_bonus_delta = models.SmallIntegerField(default=0)
    focus_bonus_delta = models.SmallIntegerField(default=0)

    def clean(self):
        """Validate that the reference source matches the Pokémon's species."""
        super().clean()

        if self.pokemon_id and self.source_form_id:
            if self.source_form.species_id != self.pokemon.species_id:
                raise ValidationError({
                    "source_form": (
                        "The source form must belong to this Pokémon's species."
                    )
                })

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["pokemon", "name"],
                name="unique_pokemon_form_name",
            ),
        ]

    def __str__(self):
        return f"{self.pokemon.sheet.name} — {self.name}"



class PokemonFormCapabilityChange(models.Model):
    """
    A capability change applied while an individual's Pokémon form is active.

    Changes affect the effective capability list, not the saved base list.
    """

    form = models.ForeignKey(
        "PokemonForm",
        on_delete=models.CASCADE,
        related_name="capability_changes",
    )

    capability = models.ForeignKey(
        "reference.Capability",
        on_delete=models.PROTECT,
        related_name="pokemon_form_changes",
    )

    operation = models.CharField(
        max_length=10,
        choices=CapabilityChangeOperation.choices,
    )

    # ADJUST: signed difference, such as +2 or -1.
    # GRANT: starting numeric value, or None for descriptive capabilities.
    # REMOVE: None.
    value = models.SmallIntegerField(
        blank=True,
        null=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "capability"],
                name="unique_pokemon_form_cap_change",
            ),
        ]

    def clean(self):
        """Validate the operation and its associated value."""
        super().clean()

        if not self.capability_id:
            return

        is_numeric = (
            self.capability.value_kind == CapabilityKind.NUMERIC
        )

        if self.operation == CapabilityChangeOperation.ADJUST:
            if not is_numeric:
                raise ValidationError({
                    "operation": (
                        "Only numeric capabilities can be adjusted."
                    )
                })

            if self.value is None:
                raise ValidationError({
                    "value": "Enter a signed adjustment, such as 2 or -1."
                })

        elif self.operation == CapabilityChangeOperation.GRANT:
            if is_numeric:
                if self.value is None or self.value < 0:
                    raise ValidationError({
                        "value": (
                            "A numeric capability grant requires "
                            "a value of zero or greater."
                        )
                    })

            elif self.value is not None:
                raise ValidationError({
                    "value": (
                        "A descriptive capability grant has no numeric value."
                    )
                })

        elif self.operation == CapabilityChangeOperation.REMOVE:
            if self.value is not None:
                raise ValidationError({
                    "value": "A removal should have no numeric value."
                })

    def __str__(self):
        if (
            self.operation == CapabilityChangeOperation.ADJUST
            and self.value is not None
        ):
            change = f"adjust by {self.value:+d}"

        elif (
            self.operation == CapabilityChangeOperation.GRANT
            and self.value is not None
        ):
            change = f"grant at {self.value}"

        else:
            change = self.get_operation_display()

        return f"{self.form} — {self.capability}: {change}" 


class PokemonFormAbilityGrant(models.Model):
    """An additional ability granted while a local Pokémon form is active."""

    form = models.ForeignKey(
        "PokemonForm",
        on_delete=models.CASCADE,
        related_name="ability_grants",
    )

    ability = models.ForeignKey(
        "reference.Ability",
        on_delete=models.PROTECT,
        related_name="pokemon_form_grants",
    )

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "ability"],
                name="unique_pokemon_form_ability",
            ),
        ]

    def __str__(self):
        return f"{self.form} — grants {self.ability}"

#==================================== Trainer Profile Sheet ================================
#===========================================================================================

class CharacterProfile(models.Model):
    """Information specific to one individual Character."""

    sheet = models.OneToOneField(
        "StatSheet",
        on_delete=models.CASCADE,
        related_name="character_profile",
    )

    current_ap = models.PositiveSmallIntegerField(default=0)
    age = models.PositiveSmallIntegerField(default=0)

    def clean(self):
        """Validate that this profile belongs to a character sheet."""
        super().clean()

        if self.sheet_id:
            if self.sheet.kind != StatSheet.Kind.CHARACTER:
                raise ValidationError({
                    "sheet": (
                        "A character profile must belong to a character sheet."
                    )
                })

    def __str__(self):
        return f"Character sheet — {self.sheet.name}"

#================= Sheet Capabilities/Abilities/Edges/Moves/Features ==========================

    

class SheetCapability(models.Model):
    """
    Associates a capability with a sheet

    Numeric capabilities have a value.
    Descriptive capabilities are represented by their presence alone.
    """

    sheet = models.ForeignKey(
        "StatSheet",
        on_delete=models.CASCADE,
        related_name="capabilities",
    )

    capability = models.ForeignKey(
        "reference.Capability",
        on_delete=models.PROTECT,
        related_name="sheet_entries",
    )

    value = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "capability"],
                name="unique_sheet_capability",
            ),
        ]

    def clean(self):
        """Check that the value matches the capability's kind."""
        super().clean()

        if not self.capability_id:
            return

        if self.capability.value_kind == CapabilityKind.NUMERIC:
            if self.value is None:
                raise ValidationError({
                    "value": "A numeric capability requires a value."
                })

        elif self.value is not None:
            raise ValidationError({
                "value": "A descriptive capability should have no numeric value."
            })

    def __str__(self):
        if self.value is None:
            return f"{self.sheet.name} — {self.capability}"

        return (
            f"{self.sheet.name} — "
            f"{self.capability}: {self.value}"
        )  




class SheetAbility(models.Model):
    """An ability an individual has independently of its active form."""

    sheet = models.ForeignKey(
        "StatSheet",
        on_delete=models.CASCADE,
        related_name="abilities",
    )

    ability = models.ForeignKey(
        "reference.Ability",
        on_delete=models.PROTECT,
        related_name="sheet_entries",
    )

    # Optional natural ability slot, used during ordinary evolution.
    tier = models.CharField(
        max_length=10,
        choices=AbilityTier.choices,
        blank=True,
    )

    slot = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
        validators=[MinValueValidator(1)],
    )

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "ability"],
                name="unique_sheet_ability",
            ),
            models.UniqueConstraint(
                fields=["sheet", "tier", "slot"],
                condition=models.Q(slot__isnull=False),
                name="unique_sheet_ability_slot",
            ),
        ]

    def clean(self):
        """Require tier and slot to be supplied together."""
        super().clean()

        if self.tier and self.slot is None:
            raise ValidationError({
                "slot": "Provide a slot when selecting an ability tier."
            })

        if self.slot is not None and not self.tier:
            raise ValidationError({
                "tier": "Select a tier when providing an ability slot."
            })

    def __str__(self):
        return f"{self.sheet.name} — {self.ability}"



class SheetMove(models.Model):
    """A move known by an individual, shared across its forms."""

    sheet = models.ForeignKey(
        "StatSheet",
        on_delete=models.CASCADE,
        related_name="moves",
    )

    move = models.ForeignKey(
        "reference.Move",
        on_delete=models.PROTECT,
        related_name="sheet_entries",
    )

    notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sheet", "move"],
                name="unique_sheet_move",
            ),
        ]

    def clean(self):
        """Keep campaign-specific moves within their own campaign."""
        super().clean()

        if not self.sheet_id or not self.move_id:
            return

        if (
            self.move.campaign_id is not None
            and self.move.campaign_id != self.sheet.campaign_id
        ):
            raise ValidationError({
                "move": "This move belongs to a different campaign."
            })

    def __str__(self):
        return f"{self.sheet.name} — {self.move}"