from rest_framework import serializers
from .models import AdherencePrediction, MLModel
from accounts.models import Patient
from prescriptions.models import Prescription


class AdherencePredictionSerializer(serializers.ModelSerializer):
    """Serializer for Adherence Prediction"""
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    
    class Meta:
        model = AdherencePrediction
        fields = ['id', 'patient', 'patient_name', 'prescription', 'age', 
                  'num_medicines', 'total_doses_per_day', 'treatment_duration_days',
                  'disease_type', 'adherence_score', 'risk_level', 'model_used',
                  'model_accuracy', 'recommendation', 'created_at']
        read_only_fields = ['id', 'adherence_score', 'risk_level', 'model_used',
                           'model_accuracy', 'recommendation', 'created_at']


class PredictionRequestSerializer(serializers.Serializer):
    """Serializer for prediction request"""
    patient_id = serializers.IntegerField()
    prescription_id = serializers.IntegerField()
    
    def validate_patient_id(self, value):
        try:
            Patient.objects.get(id=value)
        except Patient.DoesNotExist:
            raise serializers.ValidationError("Patient not found")
        return value
    
    def validate_prescription_id(self, value):
        try:
            Prescription.objects.get(id=value)
        except Prescription.DoesNotExist:
            raise serializers.ValidationError("Prescription not found")
        return value


class MLModelSerializer(serializers.ModelSerializer):
    """Serializer for ML Model"""
    
    class Meta:
        model = MLModel
        fields = ['id', 'model_name', 'model_type', 'accuracy', 'precision',
                  'recall', 'f1_score', 'is_active', 'training_date', 'notes']
        read_only_fields = ['id', 'training_date']