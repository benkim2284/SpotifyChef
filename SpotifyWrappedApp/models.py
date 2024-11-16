from django.utils import timezone
from django.db import models
import uuid

# Create your models here.
class User(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    spotify_data = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f'{self.name}'

class SoloWraps(models.Model):
    unique_id = models.CharField(max_length=36, default=str(uuid.uuid4), editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='solo_wraps')
    wrap_data = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

