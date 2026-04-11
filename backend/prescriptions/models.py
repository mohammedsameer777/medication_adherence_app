from django.db import models
from accounts.models import Patient, Doctor


class Prescription(models.Model):
    """
    Prescription model - stores prescription information
    Links to patient and doctor
    """
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    doctor  = models.ForeignKey(Doctor,  on_delete=models.CASCADE, related_name='prescriptions')

    # Prescription image
    prescription_image = models.ImageField(upload_to='prescriptions/')

    # Extracted information from OCR
    extracted_text          = models.TextField(blank=True, null=True)
    patient_name_extracted  = models.CharField(max_length=200, blank=True, null=True)
    age_extracted           = models.IntegerField(blank=True, null=True)
    disease_extracted       = models.CharField(max_length=200, blank=True, null=True)

    # Treatment details
    treatment_duration_days = models.IntegerField(default=0)
    total_medicines         = models.IntegerField(default=0)

    # Processing status
    is_processed = models.BooleanField(default=False)
    ocr_status   = models.CharField(max_length=20, choices=[
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('completed',  'Completed'),
        ('failed',     'Failed')
    ], default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Prescription for {self.patient.full_name} - {self.created_at.date()}"

    class Meta:
        db_table = 'prescriptions'
        ordering = ['-created_at']


class Medicine(models.Model):
    """
    Medicine model - stores individual medicine details
    Multiple medicines can belong to one prescription
    """
    # FIX: related_name changed to 'medicines' (was 'adherence_predictions' which was wrong)
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        related_name='medicines'
    )

    medicine_name = models.CharField(max_length=200)
    dosage        = models.CharField(max_length=100)
    frequency     = models.CharField(max_length=100)
    timing        = models.CharField(max_length=100, blank=True)
    duration_days = models.IntegerField(default=0)

    # Extracted details
    morning   = models.BooleanField(default=False)
    afternoon = models.BooleanField(default=False)
    evening   = models.BooleanField(default=False)
    night     = models.BooleanField(default=False)

    total_doses_per_day = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.medicine_name} - {self.dosage}"

    class Meta:
        db_table = 'medicines'
        ordering = ['medicine_name']


class AwarenessMessage(models.Model):
    """
    Awareness messages for patients about their disease
    """
    disease_type    = models.CharField(max_length=200)
    message_title   = models.CharField(max_length=200)
    message_content = models.TextField()
    message_type    = models.CharField(max_length=20, choices=[
        ('tip',      'Health Tip'),
        ('warning',  'Warning'),
        ('info',     'Information'),
        ('reminder', 'Reminder')
    ], default='info')

    is_active  = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.disease_type} - {self.message_title}"

    class Meta:
        db_table = 'awareness_messages'
        ordering = ['-created_at']