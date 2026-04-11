from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import Prescription, Medicine, AwarenessMessage
from accounts.models import Doctor, Patient
from .serializers import (
    PrescriptionSerializer, PrescriptionUploadSerializer,
    MedicineSerializer, AwarenessMessageSerializer
)
from .ocr_service import PrescriptionOCR
import os


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_prescription(request):
    """
    Upload prescription image and process with OCR
    """
    serializer = PrescriptionUploadSerializer(data=request.data)
    
    if serializer.is_valid():
        # Save prescription
        prescription = serializer.save()
        prescription.ocr_status = 'processing'
        prescription.save()
        
        try:
            # Get image path
            image_path = prescription.prescription_image.path
            
            # Initialize OCR service
            ocr = PrescriptionOCR()
            
            # Parse prescription
            result = ocr.parse_prescription(image_path)
            
            if result['success']:
                # Update prescription with extracted data
                prescription.extracted_text = result['extracted_text']
                prescription.patient_name_extracted = result.get('patient_name')
                prescription.age_extracted = result.get('age')
                prescription.disease_extracted = result.get('disease')
                prescription.treatment_duration_days = result.get('treatment_duration_days', 7)
                prescription.total_medicines = result.get('total_medicines', 0)
                prescription.is_processed = True
                prescription.ocr_status = 'completed'
                prescription.save()
                
                # Create medicine entries
                for med_data in result.get('medicines', []):
                    Medicine.objects.create(
                        prescription=prescription,
                        medicine_name=med_data['name'],
                        dosage=med_data['dosage'],
                        frequency=med_data['frequency'],
                        duration_days=med_data['duration_days'],
                        total_doses_per_day=int(med_data['frequency'].split()[0])
                    )
                
                return Response({
                    'success': True,
                    'message': 'Prescription uploaded and processed successfully',
                    'data': {
                        'prescription': PrescriptionSerializer(prescription).data
                    }
                }, status=status.HTTP_201_CREATED)
            else:
                prescription.ocr_status = 'failed'
                prescription.save()
                
                return Response({
                    'success': False,
                    'message': 'Failed to process prescription image',
                    'error': result.get('error')
                }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            prescription.ocr_status = 'failed'
            prescription.save()
            
            return Response({
                'success': False,
                'message': 'Error processing prescription',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return Response({
        'success': False,
        'message': 'Invalid data',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prescription(request, prescription_id):
    """
    Get prescription details by ID
    """
    prescription = get_object_or_404(Prescription, id=prescription_id)
    
    return Response({
        'success': True,
        'data': {
            'prescription': PrescriptionSerializer(prescription).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_prescriptions(request, patient_id):
    """
    Get all prescriptions for a patient
    """
    patient = get_object_or_404(Patient, id=patient_id)
    prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')
    
    return Response({
        'success': True,
        'data': {
            'total_prescriptions': prescriptions.count(),
            'prescriptions': PrescriptionSerializer(prescriptions, many=True).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_prescriptions(request):
    """
    Get all prescriptions uploaded by logged-in doctor
    """
    try:
        doctor = Doctor.objects.get(user=request.user)
        prescriptions = Prescription.objects.filter(doctor=doctor).order_by('-created_at')
        
        return Response({
            'success': True,
            'data': {
                'total_prescriptions': prescriptions.count(),
                'prescriptions': PrescriptionSerializer(prescriptions, many=True).data
            }
        }, status=status.HTTP_200_OK)
    except Doctor.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Only doctors can access this endpoint'
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_awareness_messages(request, disease_type):
    """
    Get awareness messages for a specific disease
    """
    messages = AwarenessMessage.objects.filter(
        disease_type__icontains=disease_type,
        is_active=True
    ).order_by('-created_at')
    
    return Response({
        'success': True,
        'data': {
            'total_messages': messages.count(),
            'messages': AwarenessMessageSerializer(messages, many=True).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_awareness_message(request):
    """
    Create a new awareness message (admin/doctor only)
    """
    serializer = AwarenessMessageSerializer(data=request.data)
    
    if serializer.is_valid():
        message = serializer.save()
        
        return Response({
            'success': True,
            'message': 'Awareness message created successfully',
            'data': {
                'message': AwarenessMessageSerializer(message).data
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response({
        'success': False,
        'message': 'Invalid data',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)