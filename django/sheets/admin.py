from django.contrib import admin

# Register your models here.
from .models import *


from django.contrib import admin
from .models import (
    StatSheet,
    SheetAccess,
    CharacterProfile,
    PokemonProfile,
    PokemonForm,
    SheetCapability,
    PokemonFormCapabilityChange,
    SheetAbility,
    PokemonFormAbilityGrant,
    SheetMove,
)

admin.site.register([
    StatSheet,
    SheetAccess,
    CharacterProfile,
    PokemonProfile,
    PokemonForm,
    SheetCapability,
    PokemonFormCapabilityChange,
    SheetAbility,
    PokemonFormAbilityGrant,
    SheetMove,
])
