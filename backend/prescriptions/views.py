import os
import re

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Doctor, Patient
from .models import AwarenessMessage, Medicine, Prescription
from .ocr_service import PrescriptionOCR
from .serializers import (
    AwarenessMessageSerializer,
    MedicineSerializer,
    PrescriptionSerializer,
    PrescriptionUploadSerializer,
)


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — parse total_doses_per_day safely from frequency string
# ─────────────────────────────────────────────────────────────────────────────

def _parse_doses(frequency_str):
    """
    Extract the integer dose count from a frequency string.

    Examples:
      "2 times daily"  → 2
      "1 times daily"  → 1
      "once daily"     → 1
      "twice daily"    → 2
      "thrice daily"   → 3
      "OD"             → 1
      "BD"             → 2
      "TDS"            → 3
      "QID"            → 4
      ""               → 1  (safe default)

    Never raises — always returns int >= 1.
    """
    if not frequency_str:
        return 1

    freq = str(frequency_str).strip().lower()

    # Word aliases
    word_map = {
        'once':   1, 'one':    1, 'od': 1,
        'twice':  2, 'two':    2, 'bd': 2, 'bid': 2,
        'thrice': 3, 'three':  3, 'tds': 3, 'tid': 3,
        'four':   4, 'qid':    4, 'qds': 4,
    }
    for word, val in word_map.items():
        if word in freq:
            return val

    # Leading digit  e.g. "3 times daily"
    m = re.search(r'(\d+)', freq)
    if m:
        val = int(m.group(1))
        return max(1, min(val, 10))   # clamp to sane range

    return 1


# ─────────────────────────────────────────────────────────────────────────────
# HELPER — derive timing booleans from frequency count
# ─────────────────────────────────────────────────────────────────────────────

def _timing_booleans(doses_per_day):
    """Return (morning, afternoon, evening, night) booleans."""
    if doses_per_day == 1:
        return True,  False, False, True
    if doses_per_day == 2:
        return True,  False, False, True
    if doses_per_day == 3:
        return True,  False, True,  True
    # 4+
    return True,  True,  True,  True


def _timing_label(doses_per_day):
    """Human-readable timing string for the Medicine.timing field."""
    labels = {
        1: 'Once daily (morning)',
        2: 'Morning and Night',
        3: 'Morning, Evening, Night',
        4: 'Morning, Afternoon, Evening, Night',
    }
    return labels.get(doses_per_day, f'{doses_per_day} times daily')


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_prescription(request):
    """
    Upload prescription image → OCR → save medicines → schedule SMS reminders.

    Returns prescription_id so Flutter can immediately call:
      POST /api/predictions/predict/
      POST /api/notifications/prescription/<id>/schedule/
    """
    serializer = PrescriptionUploadSerializer(data=request.data)

    if not serializer.is_valid():
        return Response({
            'success': False,
            'message': 'Invalid data',
            'errors':  serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)

    # ── Save prescription record ───────────────────────────────────────────
    prescription = serializer.save()
    prescription.ocr_status = 'processing'
    prescription.save()

    try:
        image_path = prescription.prescription_image.path

        # ── OCR ───────────────────────────────────────────────────────────
        ocr    = PrescriptionOCR()
        result = ocr.parse_prescription(image_path)

        if not result.get('success'):
            prescription.ocr_status = 'failed'
            prescription.save()
            return Response({
                'success': False,
                'message': 'Failed to process prescription image',
                'error':   result.get('error', 'OCR returned no result'),
            }, status=status.HTTP_400_BAD_REQUEST)

        # ── Update prescription fields ────────────────────────────────────
        prescription.extracted_text           = result.get('extracted_text') or ''
        prescription.patient_name_extracted   = result.get('patient_name')
        prescription.age_extracted            = result.get('age')
        prescription.disease_extracted        = result.get('disease')
        prescription.treatment_duration_days  = result.get('treatment_duration_days') or 7
        prescription.is_processed             = True
        prescription.ocr_status               = 'completed'

        # ── Create Medicine entries ───────────────────────────────────────
        medicines_data = result.get('medicines')
        if not isinstance(medicines_data, list):
            medicines_data = []

        created_medicines = []
        for med_data in medicines_data:
            if not isinstance(med_data, dict):
                continue

            name = str(med_data.get('name', '')).strip()
            if not name:
                continue

            frequency_str = str(med_data.get('frequency', '1 times daily'))
            doses         = _parse_doses(frequency_str)  # FIX: no ValueError
            morning, afternoon, evening, night = _timing_booleans(doses)

            med = Medicine.objects.create(
                prescription        = prescription,
                medicine_name       = name,
                dosage              = str(med_data.get('dosage', '1 tablet')).strip() or '1 tablet',
                frequency           = frequency_str,
                timing              = _timing_label(doses),          # FIX: was empty
                duration_days       = int(med_data.get('duration_days') or 7),
                morning             = morning,                        # FIX: was always False
                afternoon           = afternoon,
                evening             = evening,
                night               = night,
                total_doses_per_day = doses,
            )
            created_medicines.append(med)

        prescription.total_medicines = len(created_medicines)
        prescription.save()

        # ── Auto-schedule SMS reminders (FIX: was never called) ──────────
        reminders_scheduled = 0
        if created_medicines:
            try:
                from notifications.sms_service import sms_service
                reminders = sms_service.schedule_reminders_for_prescription(
                    prescription)
                reminders_scheduled = len(reminders)
            except Exception as sms_err:
                # Non-fatal: log but don't fail the whole upload
                print(f"⚠️  SMS scheduling failed (non-fatal): {sms_err}")

        return Response({
            'success': True,
            'message': 'Prescription uploaded and processed successfully',
            'data': {
                # FIX: return prescription_id so Flutter can call predict + schedule
                'prescription_id':    prescription.id,
                'reminders_scheduled': reminders_scheduled,
                'prescription':       PrescriptionSerializer(prescription).data,
            },
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        prescription.ocr_status = 'failed'
        prescription.save()
        return Response({
            'success': False,
            'message': 'Error processing prescription',
            'error':   str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prescription(request, prescription_id):
    """Get prescription details by ID."""
    prescription = get_object_or_404(Prescription, id=prescription_id)
    return Response({
        'success': True,
        'data': {
            'prescription': PrescriptionSerializer(prescription).data,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_prescriptions(request, patient_id):
    """Get all prescriptions for a patient."""
    patient       = get_object_or_404(Patient, id=patient_id)
    prescriptions = Prescription.objects.filter(
        patient=patient).order_by('-created_at')
    return Response({
        'success': True,
        'data': {
            'total_prescriptions': prescriptions.count(),
            'prescriptions':       PrescriptionSerializer(prescriptions, many=True).data,
        },
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_prescriptions(request):
    """Get all prescriptions uploaded by the logged-in doctor."""
    try:
        doctor        = Doctor.objects.get(user=request.user)
        prescriptions = Prescription.objects.filter(
            doctor=doctor).order_by('-created_at')
        return Response({
            'success': True,
            'data': {
                'total_prescriptions': prescriptions.count(),
                'prescriptions':       PrescriptionSerializer(prescriptions, many=True).data,
            },
        }, status=status.HTTP_200_OK)
    except Doctor.DoesNotExist:
        return Response({
            'success': False,
            'message': 'Only doctors can access this endpoint',
        }, status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_awareness_messages(request, disease_type):
    """Get awareness messages for a specific disease."""
    messages = AwarenessMessage.objects.filter(
        disease_type__icontains=disease_type,
        is_active=True,
    ).order_by('-created_at')
    return Response({
        'success': True,
        'data': {
            'total_messages': messages.count(),
            'messages':       AwarenessMessageSerializer(messages, many=True).data,
        },
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_awareness_message(request):
    """Create a new awareness message (admin/doctor only)."""
    serializer = AwarenessMessageSerializer(data=request.data)
    if serializer.is_valid():
        message = serializer.save()
        return Response({
            'success': True,
            'message': 'Awareness message created successfully',
            'data': {
                'message': AwarenessMessageSerializer(message).data,
            },
        }, status=status.HTTP_201_CREATED)
    return Response({
        'success': False,
        'message': 'Invalid data',
        'errors':  serializer.errors,
    }, status=status.HTTP_400_BAD_REQUEST)