from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def send_due_reminders():
    """
    Runs every 60 seconds via Celery Beat.
    Finds reminders whose scheduled_time has arrived and sends SMS.
    Skips reminders already sent, taken, cancelled, or failed.
    """
    from .models import SMSReminder
    from .sms_service import sms_service

    now = timezone.now()

    # Find reminders due in the past 2 minutes that are still 'scheduled'
    due_reminders = SMSReminder.objects.filter(
        status='scheduled',
        scheduled_time__lte=now,
        scheduled_time__gte=now - timedelta(minutes=2),
    )

    sent_count   = 0
    failed_count = 0

    for reminder in due_reminders:
        try:
            success = sms_service._send_sms(
                reminder.phone_number,
                reminder.message_content,
                reminder,
            )
            if success:
                sent_count += 1
                print(f"✅ Sent reminder #{reminder.id} → {reminder.patient.full_name} | {reminder.medicine.medicine_name}")
            else:
                failed_count += 1
        except Exception as e:
            reminder.status        = 'failed'
            reminder.error_message = str(e)
            reminder.save()
            failed_count += 1
            print(f"❌ Failed reminder #{reminder.id}: {e}")

    print(f"📊 Reminder batch: {sent_count} sent, {failed_count} failed")
    return {'sent': sent_count, 'failed': failed_count}


@shared_task
def send_single_reminder(reminder_id):
    """
    Send one specific reminder by ID.
    Can be called manually if needed.
    """
    from .models import SMSReminder
    from .sms_service import sms_service

    try:
        reminder = SMSReminder.objects.get(id=reminder_id, status='scheduled')
        sms_service._send_sms(
            reminder.phone_number,
            reminder.message_content,
            reminder,
        )
        return {'success': True, 'reminder_id': reminder_id}
    except SMSReminder.DoesNotExist:
        return {'success': False, 'error': 'Reminder not found or already processed'}
    except Exception as e:
        return {'success': False, 'error': str(e)}