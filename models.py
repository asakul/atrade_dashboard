from django.db import models

class RobotInstance(models.Model):
    instanceId = models.CharField(max_length=255)

class Trade(models.Model):
    account = models.CharField(max_length=256)
    security = models.CharField(max_length=256)
    price = models.DecimalField(max_digits=20, decimal_places=10)
    quantity = models.IntegerField()
    volume = models.DecimalField(max_digits=25, decimal_places=10)
    volumeCurrency = models.CharField(max_length=10)
    strategyId = models.CharField(max_length=64)
    signalId = models.CharField(max_length=64)
    comment = models.CharField(max_length=256)
    timestamp = models.DateTimeField()
    balanced = models.BooleanField(default=False)

class ClosedTrade(models.Model):
    LONG = 'long'
    SHORT = 'short'
    DIRECTION_CHOICES = (
                (LONG, 'long'),
                (SHORT, 'short')
            )
    account = models.CharField(max_length=256)
    security = models.CharField(max_length=256)
    entryTime = models.DateTimeField()
    exitTime = models.DateTimeField()
    profit = models.DecimalField(max_digits=25, decimal_places=10)
    profitCurrency = models.CharField(max_length=10)
    strategyId = models.CharField(max_length=64)
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES)
