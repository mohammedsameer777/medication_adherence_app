from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import random


class Doctor(models.Model):
    """
    Doctor model - stores doctor information
    Links to Django's built-in User model for authentication
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='doctor_profile')
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=15, unique=True)
    specialization = models.CharField(max_length=100)
    hospital_name = models.CharField(max_length=200)
    registration_number = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Dr. {self.full_name}"

    class Meta:
        db_table = 'doctors'
        ordering = ['-created_at']


class Patient(models.Model):
    """
    Patient model - stores patient information
    Each patient is linked to a doctor
    """
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='patients')
    full_name = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=15, unique=True)
    age = models.IntegerField()
    gender = models.CharField(max_length=10, choices=[
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ])
    disease_type = models.CharField(max_length=200)
    
    # Authentication fields
    is_verified = models.BooleanField(default=False)
    last_login = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.full_name} - {self.disease_type}"

    class Meta:
        db_table = 'patients'
        ordering = ['-created_at']


class OTP(models.Model):
    """
    OTP model - stores one-time passwords for patient login
    OTPs expire after 10 minutes
    """
    phone_number = models.CharField(max_length=15)
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        # Generate 6-digit OTP
        if not self.otp_code:
            self.otp_code = str(random.randint(100000, 999999))
        
        # Set expiry to 10 minutes from now
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        
        super().save(*args, **kwargs)

    def is_valid(self):
        """Check if OTP is still valid"""
        return timezone.now() < self.expires_at and not self.is_verified

    def __str__(self):
        return f"OTP for {self.phone_number} - {self.otp_code}"

    class Meta:
        db_table = 'otp_codes'
        ordering = ['-created_at']