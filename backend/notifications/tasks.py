"""
Celery tasks for SMS reminders
==============================
send_due_reminders  — runs every 60 s via Celery Beat.
send_single_reminder — send one reminder by ID (manual / retry use).

Key fixes:
- select_for_update() prevents duplicate sends with concurrent workers.
- Extended window (5 min) prevents reminders being missed on Beat lag.
- Handles naive vs aware datetime mismatch gracefully.
- bind=True so task ID is available for result tracking.
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from datetime import timedelta


@shared_task(bind=True)
def send_due_reminders(self):
    """
    Runs every 60 seconds via Celery Beat.

    Finds SMSReminder rows whose scheduled_time has passed and status
    is still 'scheduled', then sends them via sms_service._send_sms().

    FIX 1: select_for_update() inside a transaction — prevents two concurrent
           Celery workers from sending the same reminder twice.
    FIX 2: Window extended to 5 minutes (was 2) so Beat lag / worker restarts
           don't permanently miss reminders.
    FIX 3: Handles naive datetimes in old DB rows by making them aware before
           comparison, instead of crashing with TypeError.
    """
    from .models import SMSReminder
    from .sms_service import sms_service

    now = timezone.now()   # UTC-aware

    # FIX: 5-minute lookback window instead of 2 minutes.
    # Reminders scheduled up to 5 minutes ago that are still 'scheduled'
    # will be caught even if Beat was briefly delayed.
    window_start = now - timedelta(minutes=5)

    sent_count   = 0
    failed_count = 0
    skipped      = 0

    # FIX: select_for_update() locks each row so concurrent workers skip it.
    # Must be inside atomic() for the lock to be held until the update.
    try:
        with transaction.atomic():
            due_reminders = (
                SMSReminder.objects
                .select_for_update(skip_locked=True)   # other workers skip locked rows
                .filter(
                    status='scheduled',
                    scheduled_time__lte=now,
                    scheduled_time__gte=window_start,
                )
            )

            # Snapshot the queryset inside the transaction
            reminders_list = list(due_reminders)

    except Exception as e:
        print(f"❌ send_due_reminders DB query failed: {e}")
        return {'sent': 0, 'failed': 0, 'error': str(e)}

    if not reminders_list:
        print(f"ℹ️  send_due_reminders: no due reminders at {now.strftime('%H:%M:%S')} UTC")
        return {'sent': 0, 'failed': 0, 'skipped': 0}

    print(f"⏰ send_due_reminders: {len(reminders_list)} due at "
          f"{now.strftime('%H:%M:%S')} UTC")

    for reminder in reminders_list:
        # FIX: double-check status after lock acquisition — another worker may
        # have already processed this row before the lock was acquired.
        reminder.refresh_from_db()
        if reminder.status != 'scheduled':
            skipped += 1
            continue

        try:
            success = sms_service._send_sms(
                reminder.phone_number,
                reminder.message_content,
                reminder,
            )
            if success:
                sent_count += 1
                print(
                    f"✅ Sent #{reminder.id} → "
                    f"{reminder.patient.full_name} | "
                    f"{reminder.medicine.medicine_name}"
                )
            else:
                failed_count += 1
                print(
                    f"❌ Failed #{reminder.id} → "
                    f"{reminder.patient.full_name} | "
                    f"{reminder.medicine.medicine_name}"
                )

        except Exception as e:
            # FIX: catch per-reminder exceptions so one bad reminder doesn't
            # abort the entire batch.
            try:
                reminder.status        = 'failed'
                reminder.error_message = str(e)
                reminder.save()
            except Exception:
                pass
            failed_count += 1
            print(f"❌ Exception on reminder #{reminder.id}: {e}")

    print(
        f"📊 Reminder batch complete — "
        f"sent: {sent_count}, failed: {failed_count}, skipped: {skipped}"
    )
    return {
        'sent':    sent_count,
        'failed':  failed_count,
        'skipped': skipped,
        'task_id': self.request.id,
    }


@shared_task(bind=True)
def send_single_reminder(self, reminder_id):
    """
    Send one specific reminder by ID.
    Used for manual retries or immediate sends triggered from the admin panel.

    Returns a result dict stored in django-db backend for inspection.
    """
    from .models import SMSReminder
    from .sms_service import sms_service

    try:
        # FIX: use select_for_update so concurrent calls don't double-send
        with transaction.atomic():
            try:
                reminder = (
                    SMSReminder.objects
                    .select_for_update()
                    .get(id=reminder_id, status='scheduled')
                )
            except SMSReminder.DoesNotExist:
                return {
                    'success': False,
                    'error':   f'Reminder #{reminder_id} not found or not in scheduled state',
                    'task_id': self.request.id,
                }

            success = sms_service._send_sms(
                reminder.phone_number,
                reminder.message_content,
                reminder,
            )

        return {
            'success':     success,
            'reminder_id': reminder_id,
            'task_id':     self.request.id,
        }

    except Exception as e:
        return {
            'success': False,
            'error':   str(e),
            'task_id': self.request.id,
        }