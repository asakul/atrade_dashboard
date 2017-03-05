from django.db import models

class RobotInstance(models.Model):
    instanceId = models.CharField(max_length=255)
