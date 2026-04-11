from django.contrib import admin
from .models import Prescription, Medicine, AwarenessMessage


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = ['patient', 'doctor', 'treatment_duration_days', 'total_medicines', 'ocr_status', 'created_at']
    list_filter = ['ocr_status', 'is_processed', 'created_at']
    search_fields = ['patient__full_name', 'doctor__full_name', 'disease_extracted']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ['medicine_name', 'dosage', 'frequency', 'duration_days', 'prescription']
    list_filter = ['morning', 'afternoon', 'evening', 'night']
    search_fields = ['medicine_name', 'prescription__patient__full_name']


@admin.register(AwarenessMessage)
class AwarenessMessageAdmin(admin.ModelAdmin):
    list_display = ['disease_type', 'message_title', 'message_type', 'is_active', 'created_at']
    list_filter = ['disease_type', 'message_type', 'is_active']
    search_fields = ['disease_type', 'message_title', 'message_content']