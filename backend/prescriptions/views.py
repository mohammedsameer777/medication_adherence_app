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
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _parse_doses(frequency_str):
    if not frequency_str:
        return 1
    freq = str(frequency_str).strip().lower()
    word_map = {
        'once': 1, 'one': 1, 'od': 1,
        'twice': 2, 'two': 2, 'bd': 2, 'bid': 2,
        'thrice': 3, 'three': 3, 'tds': 3, 'tid': 3,
        'four': 4, 'qid': 4, 'qds': 4,
    }
    for word, val in word_map.items():
        if word in freq:
            return val
    m = re.search(r'(\d+)', freq)
    if m:
        return max(1, min(int(m.group(1)), 10))
    return 1


def _timing_booleans(doses_per_day):
    """Auto-generate morning/afternoon/evening/night booleans from dose count."""
    if doses_per_day == 1:
        return True, False, False, False   # morning only
    if doses_per_day == 2:
        return True, False, False, True    # morning + night
    if doses_per_day == 3:
        return True, True, False, True     # morning + afternoon + night
    return True, True, True, True


def _timing_label(doses_per_day):
    """Auto-generate timing label from dose count."""
    labels = {
        1: 'Morning',
        2: 'Morning & Night',
        3: 'Morning, Afternoon & Night',
        4: 'Morning, Afternoon, Evening & Night',
    }
    return labels.get(doses_per_day, f'{doses_per_day} times daily')


def _timing_booleans_from_label(timing_label):
    """
    Convert a doctor-selected timing label to
    morning/afternoon/evening/night booleans.
    """
    t = (timing_label or '').lower()
    morning   = 'morning'   in t
    afternoon = 'afternoon' in t
    evening   = 'evening'   in t or 'afternoon' in t
    night     = 'night'     in t or 'bedtime'   in t
    return morning, afternoon, evening, night


def _create_medicines_from_data(prescription, medicines_data):
    """
    Create Medicine objects from OCR or manual data.
    Respects the 'timing' field if provided by the doctor.
    Falls back to auto-generating timing from frequency if not.
    Returns list of created Medicine objects.
    """
    created = []
    for med_data in medicines_data:
        if not isinstance(med_data, dict):
            continue
        name = str(med_data.get('name', '')).strip()
        if not name:
            continue

        frequency_str = str(med_data.get('frequency', '1 times daily'))
        doses         = _parse_doses(frequency_str)

        # Use doctor-provided timing if present; else auto-generate
        provided_timing = str(med_data.get('timing', '')).strip()
        if provided_timing:
            timing_label = provided_timing
            morning, afternoon, evening, night = _timing_booleans_from_label(timing_label)
        else:
            morning, afternoon, evening, night = _timing_booleans(doses)
            timing_label = _timing_label(doses)

        med = Medicine.objects.create(
            prescription        = prescription,
            medicine_name       = name,
            dosage              = str(med_data.get('dosage', '1 tablet')).strip() or '1 tablet',
            frequency           = frequency_str,
            timing              = timing_label,
            duration_days       = int(med_data.get('duration_days') or 7),
            morning             = morning,
            afternoon           = afternoon,
            evening             = evening,
            night               = night,
            total_doses_per_day = doses,
        )
        created.append(med)
    return created


def _cancel_old_reminders(prescription):
    """Cancel all pending reminders for this prescription's patient."""
    try:
        from notifications.models import SMSReminder
        SMSReminder.objects.filter(
            patient=prescription.patient,
            status='scheduled',
        ).update(status='cancelled')
    except Exception as e:
        print(f"⚠️  Could not cancel old reminders: {e}")


def _schedule_reminders(prescription):
    """Schedule SMS reminders. Returns count."""
    try:
        from notifications.sms_service import sms_service
        reminders = sms_service.schedule_reminders_for_prescription(prescription)
        return len(reminders)
    except Exception as sms_err:
        print(f"⚠️  SMS scheduling failed (non-fatal): {sms_err}")
        return 0


def _build_medicine_summary(medicines):
    """Build a human-readable medicine list for the completion message."""
    if not medicines:
        return "No medicines extracted — please add manually."
    lines = []
    for i, med in enumerate(medicines, 1):
        name   = med.medicine_name if hasattr(med, 'medicine_name') else med.get('name', '')
        dosage = med.dosage if hasattr(med, 'dosage') else med.get('dosage', '')
        freq   = med.frequency if hasattr(med, 'frequency') else med.get('frequency', '')
        timing = med.timing if hasattr(med, 'timing') else med.get('timing', '')
        lines.append(f"{i}. {name} — {dosage} — {freq} [{timing}]")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_prescription(request):
    """
    Upload prescription image → OCR → save medicines → schedule SMS reminders.
    Response includes medicine list (with timing) so doctor can verify and edit.
    """
    serializer = PrescriptionUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Invalid data',
                         'errors': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    prescription = serializer.save()
    prescription.ocr_status = 'processing'
    prescription.save()

    try:
        image_path = prescription.prescription_image.path
        ocr        = PrescriptionOCR()
        result     = ocr.parse_prescription(image_path)

        if not result.get('success'):
            prescription.ocr_status = 'failed'
            prescription.save()
            return Response({'success': False, 'message': 'OCR failed',
                             'error': result.get('error', 'Unknown error')},
                            status=status.HTTP_400_BAD_REQUEST)

        prescription.extracted_text          = result.get('extracted_text') or ''
        prescription.patient_name_extracted  = result.get('patient_name')
        prescription.age_extracted           = result.get('age')
        prescription.disease_extracted       = result.get('disease')
        prescription.treatment_duration_days = result.get('treatment_duration_days') or 7
        prescription.is_processed            = True
        prescription.ocr_status              = 'completed'

        medicines_data    = result.get('medicines') or []
        created_medicines = _create_medicines_from_data(prescription, medicines_data)
        prescription.total_medicines = len(created_medicines)
        prescription.save()

        reminders_scheduled = _schedule_reminders(prescription) if created_medicines else 0
        medicine_summary    = _build_medicine_summary(created_medicines)

        return Response({
            'success': True,
            'message': 'Prescription uploaded and processed successfully',
            'data': {
                'prescription_id':         prescription.id,
                'reminders_scheduled':     reminders_scheduled,
                'total_medicines':         len(created_medicines),
                'extracted_medicines_list': medicine_summary,
                'prescription': PrescriptionSerializer(prescription).data,
            },
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        prescription.ocr_status = 'failed'
        prescription.save()
        return Response({'success': False, 'message': 'Error processing prescription',
                         'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_medicines_for_prescription(request, prescription_id):
    """
    POST /api/prescriptions/<id>/update-medicines/

    REPLACES all medicines for a prescription (deletes old ones, adds new ones).
    Used when doctor edits OCR-extracted medicines before finalising.

    Body:
    {
      "medicines": [
        {"name": "Metformin", "dosage": "500mg", "frequency": "2 times daily",
         "duration_days": 30, "timing": "Morning & Night"},
        ...
      ]
    }
    Also cancels old 'scheduled' reminders and reschedules with the new medicines.
    """
    prescription   = get_object_or_404(Prescription, id=prescription_id)
    medicines_data = request.data.get('medicines', [])

    if not isinstance(medicines_data, list) or not medicines_data:
        return Response({
            'success': False,
            'message': 'Please provide a list of medicines.',
        }, status=status.HTTP_400_BAD_REQUEST)

    # ── DELETE all existing medicines for this prescription ───────────────
    prescription.medicines.all().delete()

    # ── CREATE new medicines ───────────────────────────────────────────────
    created = _create_medicines_from_data(prescription, medicines_data)
    if not created:
        return Response({
            'success': False,
            'message': 'No valid medicines in request.',
        }, status=status.HTTP_400_BAD_REQUEST)

    prescription.total_medicines = len(created)
    prescription.save()

    # ── Cancel old pending reminders and reschedule ───────────────────────
    _cancel_old_reminders(prescription)
    reminders_scheduled = _schedule_reminders(prescription)
    medicine_summary    = _build_medicine_summary(created)

    return Response({
        'success': True,
        'message': f'{len(created)} medicine(s) saved and reminders rescheduled.',
        'data': {
            'prescription_id':       prescription.id,
            'medicines_saved':       len(created),
            'total_medicines':       prescription.total_medicines,
            'reminders_rescheduled': reminders_scheduled,
            'all_medicines_list':    medicine_summary,
            'medicines':             MedicineSerializer(created, many=True).data,
            'prescription':          PrescriptionSerializer(prescription).data,
        },
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_medicines_manually(request, prescription_id):
    """
    POST /api/prescriptions/<id>/add-medicines/

    Doctor manually APPENDS medicines (and timing) to a prescription.
    Body:
    {
      "medicines": [
        {"name": "Metformin", "dosage": "500mg", "frequency": "2 times daily",
         "duration_days": 30, "timing": "Morning & Night"},
        ...
      ]
    }
    Also cancels old 'scheduled' reminders and reschedules with new medicines.
    """
    prescription   = get_object_or_404(Prescription, id=prescription_id)
    medicines_data = request.data.get('medicines', [])

    if not isinstance(medicines_data, list) or not medicines_data:
        return Response({
            'success': False,
            'message': 'Please provide a list of medicines.',
        }, status=status.HTTP_400_BAD_REQUEST)

    created = _create_medicines_from_data(prescription, medicines_data)
    if not created:
        return Response({
            'success': False,
            'message': 'No valid medicines in request.',
        }, status=status.HTTP_400_BAD_REQUEST)

    prescription.total_medicines = prescription.medicines.count()
    prescription.save()

    # Cancel old pending reminders, then reschedule everything
    _cancel_old_reminders(prescription)
    reminders_scheduled = _schedule_reminders(prescription)
    medicine_summary    = _build_medicine_summary(prescription.medicines.all())

    return Response({
        'success': True,
        'message': f'{len(created)} medicine(s) added successfully.',
        'data': {
            'prescription_id':       prescription.id,
            'medicines_added':       len(created),
            'total_medicines':       prescription.total_medicines,
            'reminders_rescheduled': reminders_scheduled,
            'all_medicines_list':    medicine_summary,
            'new_medicines':         MedicineSerializer(created, many=True).data,
            'prescription':          PrescriptionSerializer(prescription).data,
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_manual_prescription(request):
    """
    POST /api/prescriptions/manual/

    Doctor creates a complete prescription manually without uploading an image.
    Body:
    {
      "patient": 5,
      "doctor": 2,
      "disease": "Diabetes",
      "treatment_duration_days": 30,
      "medicines": [
        {"name": "Metformin", "dosage": "500mg", "frequency": "2 times daily",
         "duration_days": 30, "timing": "Morning & Night"},
        {"name": "Glimepiride", "dosage": "1mg", "frequency": "1 times daily",
         "duration_days": 30, "timing": "Morning"}
      ]
    }
    """
    patient_id = request.data.get('patient')
    doctor_id  = request.data.get('doctor')

    if not patient_id or not doctor_id:
        return Response({'success': False, 'message': 'patient and doctor are required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    patient = get_object_or_404(Patient, id=patient_id)
    doctor  = get_object_or_404(Doctor, id=doctor_id)

    medicines_data = request.data.get('medicines', [])
    if not isinstance(medicines_data, list) or not medicines_data:
        return Response({'success': False, 'message': 'At least one medicine is required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    # Create prescription without image
    prescription = Prescription.objects.create(
        patient                 = patient,
        doctor                  = doctor,
        extracted_text          = 'Manual entry',
        patient_name_extracted  = request.data.get('patient_name', ''),
        age_extracted           = request.data.get('age'),
        disease_extracted       = request.data.get('disease', ''),
        treatment_duration_days = int(request.data.get('treatment_duration_days', 7)),
        is_processed            = True,
        ocr_status              = 'completed',
    )

    created = _create_medicines_from_data(prescription, medicines_data)
    prescription.total_medicines = len(created)
    prescription.save()

    reminders_scheduled = _schedule_reminders(prescription) if created else 0
    medicine_summary    = _build_medicine_summary(created)

    return Response({
        'success': True,
        'message': f'Manual prescription created with {len(created)} medicine(s).',
        'data': {
            'prescription_id':     prescription.id,
            'total_medicines':     len(created),
            'reminders_scheduled': reminders_scheduled,
            'medicines_list':      medicine_summary,
            'prescription':        PrescriptionSerializer(prescription).data,
        },
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_medicine(request, prescription_id, medicine_id):
    """
    DELETE /api/prescriptions/<prescription_id>/medicines/<medicine_id>/
    Doctor removes a wrongly extracted medicine.
    """
    prescription = get_object_or_404(Prescription, id=prescription_id)
    medicine     = get_object_or_404(Medicine, id=medicine_id, prescription=prescription)
    med_name     = medicine.medicine_name
    medicine.delete()
    prescription.total_medicines = prescription.medicines.count()
    prescription.save()
    return Response({
        'success': True,
        'message': f'{med_name} removed from prescription.',
        'total_medicines': prescription.total_medicines,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prescription(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    return Response({'success': True,
                     'data': {'prescription': PrescriptionSerializer(prescription).data}},
                    status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_prescriptions(request, patient_id):
    patient       = get_object_or_404(Patient, id=patient_id)
    prescriptions = Prescription.objects.filter(patient=patient).order_by('-created_at')
    return Response({'success': True,
                     'data': {'total_prescriptions': prescriptions.count(),
                              'prescriptions': PrescriptionSerializer(prescriptions, many=True).data}},
                    status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_doctor_prescriptions(request):
    try:
        doctor        = Doctor.objects.get(user=request.user)
        prescriptions = Prescription.objects.filter(doctor=doctor).order_by('-created_at')
        return Response({'success': True,
                         'data': {'total_prescriptions': prescriptions.count(),
                                  'prescriptions': PrescriptionSerializer(prescriptions, many=True).data}},
                        status=status.HTTP_200_OK)
    except Doctor.DoesNotExist:
        return Response({'success': False, 'message': 'Only doctors can access this endpoint.'},
                        status=status.HTTP_403_FORBIDDEN)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_awareness_messages(request, disease_type):
    messages = AwarenessMessage.objects.filter(
        disease_type__icontains=disease_type, is_active=True).order_by('-created_at')
    return Response({'success': True,
                     'data': {'total_messages': messages.count(),
                              'messages': AwarenessMessageSerializer(messages, many=True).data}},
                    status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_awareness_message(request):
    serializer = AwarenessMessageSerializer(data=request.data)
    if serializer.is_valid():
        message = serializer.save()
        return Response({'success': True, 'message': 'Awareness message created.',
                         'data': {'message': AwarenessMessageSerializer(message).data}},
                        status=status.HTTP_201_CREATED)
    return Response({'success': False, 'message': 'Invalid data.', 'errors': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST)