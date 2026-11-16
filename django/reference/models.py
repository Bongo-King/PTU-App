'''
reference/models.py
Description: Defines all the models relevant to permanent stored reference information in the db
'''

from django.db import models

#choices.py is where all the choices info is stored
from .choices import Type, MoveCategory, Frequency, Action, CapabilityKind, EdgeKind, AbilityTier, MoveLearnMethod
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError


#======================================== Core Sheet Reference Info ==================================

class Move(models.Model):
    '''
    A reusable definition of a move
    '''

    #ties custom-created moves to the campaign they were created for
    #setting campaign=None when making a move makes it a shared reference move
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="custom_moves",
        blank=True,
        null=True,
        default=None
    )

    name = models.CharField(max_length=100)

    #type is one of the elemental types defined in choices.py
    type = models.CharField(
        max_length=10,
        choices=Type.choices,
    )

    #Physical/Special/Status
    category = models.CharField(
        max_length=10,
        choices=MoveCategory.choices
    )

    #Frequency of Move
    frequency = models.CharField(
        max_length=15,
        choices=Frequency.choices
    )

    #A char field because keywords are classified in 'range' in PTU
    range = models.CharField(max_length=200)
    db = models.PositiveIntegerField(blank=True, null=True)
    ac = models.PositiveIntegerField(blank=True, null=True)
    effect = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Ability(models.Model):
    '''
    A reusable definition of an ability
    '''
    name = models.CharField(max_length=100)

    #Frequency of Ability
    frequency = models.CharField(
        max_length=15,
        choices= Frequency.choices
    )

    #What kind of action the ability uses
    action = models.CharField(
        max_length=20,
        choices= Action.choices,
        blank=True
    )
    #customizable text fields to describe other specifics
    trigger = models.TextField(blank=True)
    target = models.TextField(blank=True)
    effect = models.TextField()

    def __str__(self):
            return self.name
    


class Capability(models.Model):
    '''
    A reusable definition of a capability
    '''
    name = models.CharField(max_length=100)
    value_kind = models.CharField(
        max_length=12,
        choices= CapabilityKind.choices
    )
    is_movement_speed = models.BooleanField(default=False)
    description = models.TextField()

    def __str__(self):
            return self.name

    


class Feature(models.Model):
    '''
    A reusable definition of a feature
    '''
    name = models.CharField(max_length=100)
    prerequisites = models.TextField(blank=True)
    
    #Frequency of feature
    frequency = models.CharField(
        max_length=15,
        choices= Frequency.choices
    )

    #What kind of action the feature uses
    action = models.CharField(
        max_length=20,
        choices= Action.choices,
        blank=True
    )

    #customizable text fields to describe other specifics
    trigger = models.TextField(blank=True)
    target = models.TextField(blank=True)
    effect = models.TextField()
    tags = models.TextField(blank=True)

    def __str__(self):
            return self.name
    


class Edge(models.Model):
    '''
    A reusable definition of an edge
    '''
    name = models.CharField(max_length=100)
    prerequisites = models.TextField(blank=True)
    effect = models.TextField()
    kind = models.CharField(
        max_length=12,
        choices= EdgeKind.choices
    )

    def __str__(self):
            return self.name

#======================================= SPECIES INFO =======================================
#============================================================================================

class Species(models.Model):
    """
    A reusable species definition.

    Stores identity and biological information shared across its forms.
    Stats, types, and other form-dependent details belong to SpeciesForm.
    """

    name = models.CharField(max_length=100)

    # Optional so custom evolutions can exist without a Pokédex number.
    pokedex_number = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    # Descriptive text accommodates ratios and genderless species.
    gender_ratio = models.CharField(
        max_length=100,
        blank=True,
    )

    egg_groups = models.ManyToManyField(
        "EggGroup",
        related_name="species",
        blank=True,
    )

    # Text allows the value to include units or explanatory details.
    average_hatch_rate = models.CharField(
        max_length=100,
        blank=True,
    )

    diets = models.ManyToManyField(
        "Diet",
        related_name="species",
        blank=True,
    )

    habitats = models.ManyToManyField(
        "Habitat",
        related_name="species",
        blank=True,
    )

    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


class SpeciesEvolution(models.Model):
    """An evolution path and its requirements."""

    starting_species = models.ForeignKey(
        "Species",
        on_delete=models.CASCADE,
        related_name="evolutions",
    )

    resulting_species = models.ForeignKey(
        "Species",
        on_delete=models.CASCADE,
        related_name="pre_evolutions",
    )

    min_level = models.PositiveSmallIntegerField(
        blank=True,
        null=True,
    )

    conditions = models.TextField(blank=True)

    def __str__(self):
        return f"{self.starting_species} → {self.resulting_species}"


class SpeciesAbility(models.Model):
    """
    An ability a species can naturally gain, identified by tier and slot.
    Slots preserve ability correspondence during ordinary evolution.
    """

    species = models.ForeignKey(
        "Species",
        on_delete=models.CASCADE,
        related_name="ability_slots",
    )

    ability = models.ForeignKey(
        "Ability",
        on_delete=models.PROTECT,
        related_name="species_slots",
    )

    tier = models.CharField(
        max_length=10,
        choices=AbilityTier.choices,
    )

    slot = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["species", "tier", "slot"],
                name="unique_species_ability_slot",
            ),
        ]

    def __str__(self):
        return (
            f"{self.species} — {self.get_tier_display()} "
            f"{self.slot}: {self.ability}"
        )


class SpeciesMove(models.Model):
    """
    A species' learnset entry, shared by all its forms.
    Records how a move is learned and any associated level or machine.
    """

    species = models.ForeignKey(
        "Species",
        on_delete=models.CASCADE,
        related_name="learnset",
    )

    move = models.ForeignKey(
        "Move",
        on_delete=models.PROTECT,
        related_name="learnset_entries",
    )

    method = models.CharField(
        max_length=10,
        choices=MoveLearnMethod.choices,
    )

    # Used for level-up entries; empty for other methods.
    level = models.PositiveSmallIntegerField(blank=True, null=True)

    # For example, "TM24" or "HM03"; empty for other methods.
    machine = models.CharField(
        max_length=20,
        blank=True,
    )

    def __str__(self):
        details = self.get_method_display()

        if self.level is not None:
            details += f", level {self.level}"

        if self.machine:
            details += f", {self.machine}"

        return f"{self.species} — {self.move} ({details})"

#-------------------------------- Form Info ----------------------------------------

class SpeciesForm(models.Model):
    '''
    Form-specific information for a species.
     
    Stores base stats and type information as well as any token 
    override information and size/weight classifications.
    '''
    species = models.ForeignKey(
        "Species",
        on_delete=models.CASCADE,
        related_name="forms",
    )
    name = models.CharField(max_length=100)
    height = models.CharField(max_length=100, blank=True)
    weight = models.CharField(max_length=100, blank=True)

    #base stats
    hp_base = models.PositiveSmallIntegerField(default=0)
    atk_base = models.PositiveSmallIntegerField(default=0)
    def_base = models.PositiveSmallIntegerField(default=0)
    sp_atk_base = models.PositiveSmallIntegerField(default=0)
    sp_def_base = models.PositiveSmallIntegerField(default=0)
    speed_base = models.PositiveSmallIntegerField(default=0)

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
    #base skills
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

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["species", "name"],
                name="unique_species_form_name",
            ),
        ]

    def __str__(self):
        return f"{self.species.name} — {self.name}"




class FormCapability(models.Model):
    """
    Associates a capability with a species form.

    Numeric capabilities have a value.
    Descriptive capabilities are represented by their presence alone.
    """

    form = models.ForeignKey(
        "SpeciesForm",
        on_delete=models.CASCADE,
        related_name="capabilities",
    )

    capability = models.ForeignKey(
        "Capability",
        on_delete=models.PROTECT,
        related_name="form_entries",
    )

    value = models.PositiveIntegerField(
        blank=True,
        null=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "capability"],
                name="unique_form_capability",
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
            return f"{self.form} — {self.capability}"

        return f"{self.form} — {self.capability}: {self.value}"    
    


class FormAbilityGrant(models.Model):
    """
    An additional ability granted by a form.
    This does not replace an existing ability.
    """

    form = models.ForeignKey(
        "SpeciesForm",
        on_delete=models.CASCADE,
        related_name="ability_grants",
    )

    ability = models.ForeignKey(
        "Ability",
        on_delete=models.PROTECT,
        related_name="form_grants",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["form", "ability"],
                name="unique_form_ability_grant",
            ),
        ]

    def __str__(self):
        return f"{self.form} — grants {self.ability}"


    


#===================================== MISC EXTRA REFERENCES ======================================

class EggGroup(models.Model):
    """An egg group to which a species can belong."""

    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Diet(models.Model):
    """A dietary classification, such as Herbivore or Carnivore."""

    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Habitat(models.Model):
    """A habitat in which a species can be found."""

    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name




