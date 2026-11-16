'''
sheets/choices.py
Description: Defines all the textChoices used primarily in sheets
'''

from django.db import models


class CapabilityChangeOperation(models.TextChoices):
    ADJUST = "Adjust", "Adjust numeric value"
    GRANT = "Grant", "Grant capability"
    REMOVE = "Remove", "Remove capability"


class Nature(models.TextChoices):
    CUDDLY = "Cuddly", "Cuddly"
    RASH = "Rash", "Rash"
    DISTRACTED = "Distracted", "Distracted"
    QUIET = "Quiet", "Quiet"
    PROUD = "Proud", "Proud"
    DREAMY = "Dreamy", "Dreamy"
    DECISIVE = "Decisive", "Decisive"
    CALM = "Calm", "Calm"
    PATIENT = "Patient", "Patient"
    GENTLE = "Gentle", "Gentle"
    DESPERATE = "Desperate", "Desperate"
    CAREFUL = "Careful", "Careful"
    LONELY = "Lonely", "Lonely"
    SASSY = "Sassy", "Sassy"
    ADAMANT = "Adamant", "Adamant"
    SKITTISH = "Skittish", "Skittish"
    NAUGHTY = "Naughty", "Naughty"
    TIMID = "Timid", "Timid"
    BRAVE = "Brave", "Brave"
    HASTY = "Hasty", "Hasty"
    STARK = "Stark", "Stark"
    JOLLY = "Jolly", "Jolly"
    BOLD = "Bold", "Bold"
    NAIVE = "Naive", "Naive"
    IMPISH = "Impish", "Impish"
    COMPOSED = "Composed", "Composed"
    LAX = "Lax", "Lax"
    HARDY = "Hardy", "Hardy"
    RELAXED = "Relaxed", "Relaxed"
    DOCILE = "Docile", "Docile"
    CURIOUS = "Curious", "Curious"
    BASHFUL = "Bashful", "Bashful"
    MODEST = "Modest", "Modest"
    QUIRKY = "Quirky", "Quirky"
    MILD = "Mild", "Mild"
    SERIOUS = "Serious", "Serious" 