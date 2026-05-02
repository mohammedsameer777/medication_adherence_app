"""
Notifications views
===================
Endpoints for scheduling SMS reminders, querying them, marking as taken,
and sending test SMS messages.

URL prefix: /api/notifications/
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import Patient
from prescriptions.models import Prescription
from .models import SMSReminder, PushNotification
from .sms_service import sms_service


# ── Serializer (kept here — no separate serializers.py for notifications) ────

class SMSReminderSerializer(serializers.ModelSerializer):
    patient_name  = serializers.CharField(
        source='patient.full_name',      read_only=True)
    medicine_name = serializers.CharField(
        source='medicine.medicine_name', read_only=True)

    class Meta:
        model  = SMSReminder
        fields = [
            'id', 'patient', 'patient_name', 'medicine', 'medicine_name',
            'phone_number', 'message_content', 'scheduled_time', 'sent_time',
            'status', 'taken_at', 'error_message', 'created_at',
        ]
        read_only_fields = [
            'id', 'sent_time', 'status', 'taken_at',
            'error_message', 'created_at',
        ]


# ── Schedule reminders for a prescription ────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_prescription_reminders(request, prescription_id):
    """
    POST /api/notifications/prescription/<prescription_id>/schedule/

    Called by Flutter immediately after a successful prescription upload.
    Writes SMSReminder rows to the DB — Celery Beat sends them at the right time.
    """
    prescription = get_object_or_404(Prescription, id=prescription_id)

    # Guard: prescription must have medicines to schedule
    if not prescription.medicines.exists():
        return Response({
            'success': False,
            'message': 'No medicines found on this prescription. '
                       'OCR may not have extracted medicines yet.',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        reminders = sms_service.schedule_reminders_for_prescription(prescription)
        return Response({
            'success': True,
            'message': f'Scheduled {len(reminders)} reminders',
            'data': {
                'total_reminders': len(reminders),
                'prescription_id': prescription.id,
                'patient_name':    prescription.patient.full_name,
            },
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'success': False,
            'message': 'Failed to schedule reminders',
            'error':   str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Get reminders for a patient ───────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_reminders(request, patient_id):
    """
    GET /api/notifications/patient/<patient_id>/reminders/

    Query params:
      ?filter=today    → today + past 2 days overdue  (DEFAULT)
      ?filter=upcoming → next 3 days
      ?filter=all      → full history
    """
    patient     = get_object_or_404(Patient, id=patient_id)
    filter_type = request.query_params.get('filter', 'today')

    now         = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if filter_type == 'today':
        two_days_ago = today_start - timedelta(days=2)
        reminders = SMSReminder.objects.filter(
            patient=patient,
            scheduled_time__gte=two_days_ago,
            scheduled_time__lte=today_end,
        ).order_by('scheduled_time')

    elif filter_type == 'upcoming':
        three_days_later = today_end + timedelta(days=3)
        reminders = SMSReminder.objects.filter(
            patient=patient,
            scheduled_time__gte=today_start,
            scheduled_time__lte=three_days_later,
        ).order_by('scheduled_time')

    else:
        reminders = SMSReminder.objects.filter(
            patient=patient,
        ).order_by('-scheduled_time')

    return Response({
        'success': True,
        'data': {
            'total_reminders': reminders.count(),
            'filter':          filter_type,
            'reminders':       SMSReminderSerializer(reminders, many=True).data,
        },
    }, status=status.HTTP_200_OK)


# ── Mark reminder as taken ────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_reminder_taken(request, reminder_id):
    """POST /api/notifications/reminder/<reminder_id>/taken/"""
    reminder = get_object_or_404(SMSReminder, id=reminder_id)

    if reminder.status == 'taken':
        return Response({
            'success': True,
            'message': f'{reminder.medicine.medicine_name} already marked as taken.',
            'data': {
                'reminder_id':   reminder.id,
                'medicine_name': reminder.medicine.medicine_name,
                'taken_at':      reminder.taken_at,
                'status':        reminder.status,
            },
        }, status=status.HTTP_200_OK)

    reminder.status   = 'taken'
    reminder.taken_at = timezone.now()
    reminder.save()

    return Response({
        'success': True,
        'message': f'Marked {reminder.medicine.medicine_name} as taken.',
        'data': {
            'reminder_id':   reminder.id,
            'medicine_name': reminder.medicine.medicine_name,
            'taken_at':      reminder.taken_at,
            'status':        reminder.status,
        },
    }, status=status.HTTP_200_OK)


# ── Reminder statistics ───────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_reminder_statistics(request):
    """
    GET /api/notifications/stats/
    Optional: ?patient_id=<id>
    """
    # FIX: guard against non-integer patient_id crashing with ValueError
    patient_id = request.query_params.get('patient_id')
    if patient_id is not None:
        try:
            patient_id = int(patient_id)
        except ValueError:
            return Response({
                'success': False,
                'message': 'patient_id must be an integer',
            }, status=status.HTTP_400_BAD_REQUEST)

        patient = get_object_or_404(Patient, id=patient_id)
        stats   = sms_service.get_reminder_statistics(patient)
    else:
        stats = sms_service.get_reminder_statistics()

    return Response({'success': True, 'data': stats}, status=status.HTTP_200_OK)


# ── Test SMS endpoint ─────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_sms(request):
    """
    POST /api/notifications/test-sms/
    Body: { "phone_number": "9876543210" }

    FIX: no longer creates orphan Prescription/Patient rows.
    Sends directly using the patient's existing record, or uses a
    lightweight direct SMS call when no patient record exists.
    """
    phone_number = request.data.get('phone_number', '').strip()
    if not phone_number:
        return Response({
            'success': False,
            'message': 'phone_number is required',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Try to find an existing patient with this phone number
        patient = Patient.objects.filter(phone_number=phone_number).first()

        if patient and patient.prescriptions.exists():
            # Use the patient's most recent medicine for the test
            latest_prescription = patient.prescriptions.order_by(
                '-created_at').first()
            medicine = latest_prescription.medicines.first()

            if medicine:
                reminder, success = sms_service.send_medication_reminder(
                    patient, medicine, send_now=True)
                return Response({
                    'success': success,
                    'message': 'Test SMS sent via patient record',
                    'data': {
                        'reminder_id': reminder.id,
                        'status':      reminder.status,
                        'phone':       phone_number,
                    },
                }, status=status.HTTP_200_OK)

        # FIX: no patient or no medicine — send a plain SMS without
        # creating any DB records that would violate constraints.
        test_message = (
            f"Medication Adherence App — Test SMS\n\n"
            f"This is a test message sent to {phone_number}.\n"
            f"Your SMS notifications are working correctly!"
        )

        # Use _send_sms-equivalent logic but without a DB row
        if sms_service.use_twilio and sms_service.client:
            formatted = sms_service._format_phone(phone_number)
            msg = sms_service.client.messages.create(
                body  = test_message,
                from_ = sms_service.twilio_number,
                to    = formatted,
            )
            return Response({
                'success': True,
                'message': 'Test SMS sent via Twilio',
                'data': {'twilio_sid': msg.sid, 'phone': phone_number},
            }, status=status.HTTP_200_OK)
        else:
            print(f"\n📱 MOCK TEST SMS → {phone_number}\n{test_message}\n")
            return Response({
                'success': True,
                'message': 'Test SMS sent (MOCK mode)',
                'data': {'phone': phone_number, 'mode': 'mock'},
            }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'error': str(e),
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)