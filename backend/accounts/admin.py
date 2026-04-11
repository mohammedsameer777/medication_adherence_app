from django.contrib import admin
from .models import Doctor, Patient, OTP


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone_number', 'specialization', 'hospital_name', 'is_active', 'created_at']
    list_filter = ['is_active', 'specialization', 'created_at']
    search_fields = ['full_name', 'phone_number', 'registration_number']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'phone_number', 'age', 'disease_type', 'doctor', 'is_verified', 'created_at']
    list_filter = ['is_verified', 'is_active', 'gender', 'disease_type', 'created_at']
    search_fields = ['full_name', 'phone_number', 'disease_type']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'otp_code', 'is_verified', 'created_at', 'expires_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['phone_number', 'otp_code']
    readonly_fields = ['created_at']