'''
campaigns/models.py
Description: Defines all the models relevant to campaign organization and membership
'''

from django.conf import settings
from django.db import models

class Campaign(models.Model):
    #a campaign itself

    #name of campaign
    name = models.CharField(max_length=100)

    #description if you want
    description = models.TextField(blank=True)

    #there is one assigned user to be gm for a given campaign 
    gm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_campaigns",
    )

    def __str__(self) :
        '''return a string representation of this model'''
        return f'{self.name}'



class CampaignMembership(models.Model):
    #associates users with a campaign 

    #the campaign that the user belongs to
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    #the user to be associated with the campaign
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaign_memberships",
    )

    #this is a unique relationship. A given user and campaign cannot be associated multiple times.
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "user"],
                name="unique_campaign_membership",
            )
        ]

    def __str__(self) :
        '''return a string representation of this model'''
        return f'{self.campaign.name, self.user}'






