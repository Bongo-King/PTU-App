'''
sheets/choices.py
Description: Defines all the textChoices used primarily in reference
'''

from django.db import models

#defines the elemental type of a move/pokemon
class Type(models.TextChoices):
    NORMAL = "Normal", "Normal"
    FIRE = "Fire", "Fire"
    WATER = "Water", "Water"
    ELECTRIC = "Electric", "Electric"
    GRASS = "Grass", "Grass"
    ICE = "Ice", "Ice"
    FIGHTING = "Fighting", "Fighting"
    POISON = "Poison", "Poison"
    GROUND = "Ground", "Ground"
    FLYING = "Flying", "Flying"
    PSYCHIC = "Psychic", "Psychic"
    BUG = "Bug", "Bug"
    ROCK = "Rock", "Rock"
    GHOST = "Ghost", "Ghost"
    DRAGON = "Dragon", "Dragon"
    DARK = "Dark", "Dark"
    STEEL = "Steel", "Steel"
    FAIRY = "Fairy", "Fairy"

#The category of a Move
class MoveCategory(models.TextChoices):
    PHYSICAL = "Physical", "Physical"
    SPECIAL = "Special", "Special"
    STATUS = "Status", "Status"


#Move Frequency options
class Frequency(models.TextChoices):
    EOT = "EOT", "EOT"
    ATWILL = "At-Will", "At-Will"
    SCENE = "Scene", "Scene"
    TWOSCENE = "Scene x2", "Scene x2"
    DAILY = "Daily", "Daily"
    TWODAILY = "Daily x2", "Daily x2"
    STATIC = "Static", "Static"

#All the different action types
class Action(models.TextChoices):
    STANDARD = "Standard", "Standard Action"
    SHIFT = "Shift", "Shift Action"
    FREE = "Free", "Free Action"
    SWIFT = "Swift", "Swift Action"
    EXTENDED = "Extended", "Extended Action"
    FULL = "Full", "Full Action"

#If a capability has a number associated with it or is just a thing
class CapabilityKind(models.TextChoices):
    NUMERIC = "Numeric", "Numeric"
    DESCRIPTION = "Description", "Description"

#Skill Edge vs Non-Skill edge
class EdgeKind(models.TextChoices):
    SKILL = "Skill", "Skill Edge"
    OTHER = "Other", "Non Skill Edge"

#Tiers of pokemon ability
class AbilityTier(models.TextChoices):
    BASIC = "Basic", "Basic"
    ADVANCED = "Advanced", "Advanced"
    HIGH = "High", "High"

#Learn Methods for moves
class MoveLearnMethod(models.TextChoices):
    LEVEL_UP = "Level Up", "Level Up"
    MACHINE = "Machine", "TM/HM"
    EGG = "Egg", "Egg"
    TUTOR = "Tutor", "Tutor"
    OTHER = "Other", "Other"


