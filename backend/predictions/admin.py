from django.contrib import admin
from .models import AdherencePrediction, MLModel


@admin.register(AdherencePrediction)
class AdherencePredictionAdmin(admin.ModelAdmin):
    list_display = ['patient', 'risk_level', 'adherence_score', 'model_used', 'created_at']
    list_filter = ['risk_level', 'model_used', 'created_at']
    search_fields = ['patient__full_name', 'disease_type']
    readonly_fields = ['created_at']


@admin.register(MLModel)
class MLModelAdmin(admin.ModelAdmin):
    list_display = ['model_name', 'model_type', 'accuracy', 'f1_score', 'is_active', 'training_date']
    list_filter = ['model_type', 'is_active', 'training_date']
    search_fields = ['model_name']
    readonly_fields = ['training_date']