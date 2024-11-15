from django.utils import timezone
from django.db import models

# Create your models here.
class User(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    spotify_data = models.JSONField()

    def __str__(self):
        return f'{self.name}'
