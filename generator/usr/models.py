from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.

class User(AbstractUser):
    username = None
    email = models.EmailField('email address', unique=True)  # Make email unique
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

