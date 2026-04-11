from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from .models import SMSReminder, PushNotification
from accounts.models import Patient
from prescriptions.models import Prescription
from .sms_service import sms_service
from rest_framework import serializers


class SMSReminderSerializer(serializers.ModelSerializer):
    patient_name  = serializers.CharField(source='patient.full_name',      read_only=True)
    medicine_name = serializers.CharField(source='medicine.medicine_name', read_only=True)

    class Meta:
        model  = SMSReminder
        fields = [
            'id', 'patient', 'patient_name', 'medicine', 'medicine_name',
            'phone_number', 'message_content', 'scheduled_time', 'sent_time',
            'status', 'taken_at', 'error_message', 'created_at'
        ]
        read_only_fields = [
            'id', 'sent_time', 'status', 'taken_at', 'error_message', 'created_at'
        ]


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def schedule_prescription_reminders(request, prescription_id):
    prescription = get_object_or_404(Prescription, id=prescription_id)
    try:
        reminders = sms_service.schedule_reminders_for_prescription(prescription)
        return Response({
            'success': True,
            'message': f'Scheduled {len(reminders)} reminders',
            'data': {
                'total_reminders': len(reminders),
                'prescription_id': prescription.id,
                'patient_name':    prescription.patient.full_name
            }
        }, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({
            'success': False,
            'message': 'Failed to schedule reminders',
            'error':   str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_reminders(request, patient_id):
    """
    GET /api/notifications/patient/<id>/reminders/

    Query params:
      ?filter=today   → only today's reminders (DEFAULT)
      ?filter=all     → all reminders (for history view)
      ?filter=upcoming → next 3 days
    """
    patient     = get_object_or_404(Patient, id=patient_id)
    filter_type = request.query_params.get('filter', 'today')

    now        = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    if filter_type == 'today':
        # Show today's reminders + any overdue (missed) ones from past 2 days
        two_days_ago = today_start - timedelta(days=2)
        reminders = SMSReminder.objects.filter(
            patient=patient,
            scheduled_time__gte=two_days_ago,
            scheduled_time__lte=today_end,
        ).order_by('scheduled_time')

    elif filter_type == 'upcoming':
        # Next 3 days
        three_days = today_end + timedelta(days=3)
        reminders = SMSReminder.objects.filter(
            patient=patient,
            scheduled_time__gte=today_start,
            scheduled_time__lte=three_days,
        ).order_by('scheduled_time')

    else:
        # All reminders
        reminders = SMSReminder.objects.filter(
            patient=patient
        ).order_by('-scheduled_time')

    return Response({
        'success': True,
        'data': {
            'total_reminders': reminders.count(),
            'filter':          filter_type,
            'reminders':       SMSReminderSerializer(reminders, many=True).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_reminder_taken(request, reminder_id):
    """POST /api/notifications/reminder/<id>/taken/"""
    reminder = get_object_or_404(SMSReminder, id=reminder_id)
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
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_reminder_statistics(request):
    patient_id = request.query_params.get('patient_id')
    if patient_id:
        patient = get_object_or_404(Patient, id=patient_id)
        stats   = sms_service.get_reminder_statistics(patient)
    else:
        stats = sms_service.get_reminder_statistics()
    return Response({'success': True, 'data': stats}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_sms(request):
    phone_number = request.data.get('phone_number')
    if not phone_number:
        return Response({'success': False, 'message': 'Phone number required'},
                        status=status.HTTP_400_BAD_REQUEST)
    try:
        from accounts.models import Doctor
        from prescriptions.models import Medicine, Prescription
        patient, _ = Patient.objects.get_or_create(
            phone_number=phone_number,
            defaults={'full_name': 'Test', 'age': 30, 'gender': 'male',
                      'disease_type': 'Test', 'doctor': Doctor.objects.first()}
        )
        prescription = Prescription.objects.create(
            patient=patient, doctor=Doctor.objects.first())
        medicine = Medicine.objects.create(
            prescription=prescription, medicine_name='Test Medicine',
            dosage='1 tablet', frequency='Once daily')
        reminder, success = sms_service.send_medication_reminder(patient, medicine)
        return Response({
            'success': success,
            'data': {'reminder_id': reminder.id, 'status': reminder.status}
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'success': False, 'error': str(e)},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)