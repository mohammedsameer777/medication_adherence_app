from django.db import models
from accounts.models import Patient
from prescriptions.models import Prescription


class AdherencePrediction(models.Model):
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='predictions'
    )
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='adherence_predictions'
    )

    age                     = models.IntegerField()
    num_medicines           = models.IntegerField()
    total_doses_per_day     = models.IntegerField()
    treatment_duration_days = models.IntegerField()
    disease_type            = models.CharField(max_length=200)

    adherence_score = models.FloatField()
    risk_level      = models.CharField(max_length=20, choices=[
        ('low',    'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high',   'High Risk')
    ])

    model_used     = models.CharField(max_length=50)
    model_accuracy = models.FloatField(null=True, blank=True)

    recommendation = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient.full_name} - {self.risk_level} ({self.adherence_score:.2f})"

    class Meta:
        db_table = 'adherence_predictions'
        ordering = ['-created_at']


class MLModel(models.Model):
    model_name = models.CharField(max_length=100)
    model_type = models.CharField(max_length=50, choices=[
        ('logistic',      'Logistic Regression'),
        ('random_forest', 'Random Forest'),
        ('svm',           'Support Vector Machine'),
        ('xgboost',       'XGBoost'),
        ('deep_learning', 'Deep Learning'),
        ('other',         'Other'),
    ])

    accuracy  = models.FloatField()
    precision = models.FloatField()
    recall    = models.FloatField()
    f1_score  = models.FloatField()

    model_file_path = models.CharField(max_length=500)
    is_active       = models.BooleanField(default=False)

    training_date = models.DateTimeField(auto_now_add=True)
    notes         = models.TextField(blank=True)

    def __str__(self):
        return f"{self.model_name} - Accuracy: {self.accuracy:.2f}%"

    class Meta:
        db_table = 'ml_models'
        ordering = ['-accuracy']