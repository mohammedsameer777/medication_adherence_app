"""
NEW FILE: backend/accounts/patient_monitoring_views.py

Add this URL to backend/accounts/urls.py:
    path('patient/<int:patient_id>/monitoring/', monitoring_views.get_patient_monitoring, name='patient_monitoring'),
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta, date
from .models import Doctor, Patient
from prescriptions.models import Prescription, Medicine
from notifications.models import SMSReminder


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_monitoring(request, patient_id):
    """
    GET /api/auth/patient/<id>/monitoring/

    Returns everything a doctor needs to monitor a patient's medication status:
    - Today's medicines: taken / missed / pending
    - Total medicines left (across all active prescriptions)
    - Overall adherence % (last 7 days)
    - Active prescriptions summary
    - Last activity timestamp
    """
    try:
        doctor = Doctor.objects.get(user=request.user)
    except Doctor.DoesNotExist:
        return Response({'success': False, 'message': 'Doctor profile not found.'},
                        status=status.HTTP_403_FORBIDDEN)

    patient = get_object_or_404(Patient, id=patient_id, doctor=doctor)

    now         = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    # ── Today's reminders ─────────────────────────────────────────────────────
    todays_reminders = SMSReminder.objects.filter(
        patient=patient,
        scheduled_time__gte=today_start,
        scheduled_time__lte=today_end,
    ).select_related('medicine').order_by('scheduled_time')

    taken_today   = todays_reminders.filter(status='taken').count()
    missed_today  = todays_reminders.filter(
        status__in=['scheduled', 'sent', 'failed'],
        scheduled_time__lt=now,
    ).count()
    pending_today = todays_reminders.filter(
        status='scheduled',
        scheduled_time__gte=now,
    ).count()
    total_today   = todays_reminders.count()

    today_medicines = []
    seen_medicines  = set()  # avoid duplicates from multiple reminders

    for reminder in todays_reminders:
        med_key = reminder.medicine_id
        if med_key in seen_medicines:
            continue
        seen_medicines.add(med_key)

        medicine = reminder.medicine

        # Find all reminders for this medicine today
        med_reminders_today = todays_reminders.filter(medicine=medicine)
        med_taken           = med_reminders_today.filter(status='taken').count()
        med_total           = med_reminders_today.count()
        is_overdue          = (
            reminder.scheduled_time < now and
            reminder.status in ['scheduled', 'sent', 'failed']
        )

        today_medicines.append({
            'medicine_id':         medicine.id,
            'medicine_name':       medicine.medicine_name,
            'dosage':              medicine.dosage,
            'frequency':           medicine.frequency,
            'doses_taken_today':   med_taken,
            'doses_total_today':   med_total,
            'is_fully_taken':      med_taken >= med_total and med_total > 0,
            'is_overdue':          is_overdue,
            'next_reminder_time':  _format_time(reminder.scheduled_time),
            'status':              'taken' if med_taken >= med_total and med_total > 0
                                   else ('overdue' if is_overdue else 'pending'),
        })

    # ── 7-day adherence ───────────────────────────────────────────────────────
    seven_days_ago = now - timedelta(days=7)
    last_7_reminders = SMSReminder.objects.filter(
        patient=patient,
        scheduled_time__gte=seven_days_ago,
        scheduled_time__lte=now,
    )
    total_7   = last_7_reminders.count()
    taken_7   = last_7_reminders.filter(status='taken').count()
    adherence_7_days = round((taken_7 / total_7 * 100), 1) if total_7 > 0 else 0.0

    # ── Active prescriptions & medicines left ─────────────────────────────────
    active_prescriptions = Prescription.objects.filter(
        patient=patient,
        is_processed=True,
    ).prefetch_related('medicines').order_by('-created_at')[:5]   # last 5

    prescriptions_data     = []
    total_medicines_left   = 0
    total_doses_remaining  = 0

    for rx in active_prescriptions:
        medicines_in_rx = rx.medicines.all()
        rx_medicines    = []

        for med in medicines_in_rx:
            # Count how many doses are still scheduled (not yet taken/missed)
            remaining_reminders = SMSReminder.objects.filter(
                patient=patient,
                medicine=med,
                status='scheduled',
                scheduled_time__gte=now,
            ).count()

            total_reminders_for_med = SMSReminder.objects.filter(
                patient=patient,
                medicine=med,
            ).count()

            taken_reminders = SMSReminder.objects.filter(
                patient=patient,
                medicine=med,
                status='taken',
            ).count()

            # Estimate tablets left = remaining scheduled doses
            doses_left = remaining_reminders
            total_doses_remaining += doses_left

            if doses_left > 0:
                total_medicines_left += 1

            rx_medicines.append({
                'medicine_id':   med.id,
                'medicine_name': med.medicine_name,
                'dosage':        med.dosage,
                'frequency':     med.frequency,
                'duration_days': med.duration_days,
                'doses_taken':   taken_reminders,
                'doses_total':   total_reminders_for_med,
                'doses_left':    doses_left,
                'adherence_pct': round(taken_reminders / total_reminders_for_med * 100, 1)
                                 if total_reminders_for_med > 0 else 0.0,
            })

        prescriptions_data.append({
            'prescription_id':       rx.id,
            'date_uploaded':         rx.created_at.strftime('%d %b %Y'),
            'disease':               rx.disease_extracted or patient.disease_type,
            'treatment_duration':    rx.treatment_duration_days,
            'total_medicines':       rx.total_medicines,
            'ocr_status':            rx.ocr_status,
            'medicines':             rx_medicines,
        })

    # ── Last medicine activity ─────────────────────────────────────────────────
    last_taken = SMSReminder.objects.filter(
        patient=patient, status='taken'
    ).order_by('-taken_at').first()

    last_activity = last_taken.taken_at.strftime('%d %b %Y, %I:%M %p') \
                    if last_taken and last_taken.taken_at else 'No activity yet'

    # ── Adherence status label ────────────────────────────────────────────────
    if adherence_7_days >= 80:
        adherence_label = 'Good'
        adherence_color = 'green'
    elif adherence_7_days >= 50:
        adherence_label = 'Moderate'
        adherence_color = 'orange'
    else:
        adherence_label = 'Poor'
        adherence_color = 'red'

    return Response({
        'success': True,
        'data': {
            'patient': {
                'id':           patient.id,
                'full_name':    patient.full_name,
                'age':          patient.age,
                'gender':       patient.gender,
                'disease_type': patient.disease_type,
                'phone_number': patient.phone_number,
            },

            # Today's medicine status
            'today': {
                'date':           now.strftime('%A, %d %b %Y'),
                'total_doses':    total_today,
                'taken':          taken_today,
                'missed':         missed_today,
                'pending':        pending_today,
                'completion_pct': round(taken_today / total_today * 100, 1)
                                  if total_today > 0 else 0.0,
                'medicines':      today_medicines,
            },

            # Overall medicines remaining
            'medicines_summary': {
                'active_medicines_count': total_medicines_left,
                'total_doses_remaining':  total_doses_remaining,
                'active_prescriptions':   len(prescriptions_data),
            },

            # 7-day adherence
            'adherence': {
                'last_7_days_pct':   adherence_7_days,
                'last_7_days_taken': taken_7,
                'last_7_days_total': total_7,
                'label':             adherence_label,
                'color':             adherence_color,
            },

            'last_activity':    last_activity,
            'prescriptions':    prescriptions_data,
        }
    }, status=status.HTTP_200_OK)


def _format_time(dt):
    if dt is None:
        return None
    return dt.strftime('%I:%M %p')