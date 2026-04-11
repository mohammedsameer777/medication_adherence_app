from rest_framework import serializers
from .models import Prescription, Medicine, AwarenessMessage
from accounts.models import Patient, Doctor


class MedicineSerializer(serializers.ModelSerializer):
    """Serializer for Medicine model"""
    
    class Meta:
        model = Medicine
        fields = ['id', 'medicine_name', 'dosage', 'frequency', 'timing', 
                  'duration_days', 'morning', 'afternoon', 'evening', 'night',
                  'total_doses_per_day', 'created_at']
        read_only_fields = ['id', 'created_at']


class PrescriptionSerializer(serializers.ModelSerializer):
    """Serializer for Prescription model"""
    medicines = MedicineSerializer(many=True, read_only=True)
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    doctor_name = serializers.CharField(source='doctor.full_name', read_only=True)
    
    class Meta:
        model = Prescription
        fields = ['id', 'patient', 'patient_name', 'doctor', 'doctor_name',
                  'prescription_image', 'extracted_text', 'patient_name_extracted',
                  'age_extracted', 'disease_extracted', 'treatment_duration_days',
                  'total_medicines', 'is_processed', 'ocr_status', 'medicines',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'extracted_text', 'patient_name_extracted',
                           'age_extracted', 'disease_extracted', 'treatment_duration_days',
                           'total_medicines', 'is_processed', 'ocr_status', 'created_at',
                           'updated_at']


class PrescriptionUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading prescription"""
    
    class Meta:
        model = Prescription
        fields = ['patient', 'doctor', 'prescription_image']
    
    def validate_prescription_image(self, value):
        # Validate file size (max 10MB)
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Image size should not exceed 10MB")
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Only JPEG and PNG images are allowed")
        
        return value


class AwarenessMessageSerializer(serializers.ModelSerializer):
    """Serializer for Awareness Messages"""
    
    class Meta:
        model = AwarenessMessage
        fields = ['id', 'disease_type', 'message_title', 'message_content',
                  'message_type', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']