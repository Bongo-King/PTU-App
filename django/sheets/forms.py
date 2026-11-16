"""Input validation for the temporary HTML sheet interface."""
from django import forms
from .models import PokemonForm


class PokemonFormSelectionForm(forms.Form):
    active_form = forms.ModelChoiceField(
        queryset=PokemonForm.objects.none(), label="Form", empty_label=None
    )

    def __init__(self, *args, pokemon, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["active_form"].queryset = pokemon.forms.order_by("name", "pk")
        self.initial.setdefault("active_form", pokemon.active_form_id)
