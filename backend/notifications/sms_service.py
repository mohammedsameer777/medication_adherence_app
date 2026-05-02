"""
SMS Reminder Service
====================
Wraps Twilio (or mock mode) for medication reminders and OTP delivery.

Key design decisions:
- SMSReminderService.__init__() NEVER raises — import-time crash prevention.
- schedule_reminders_for_prescription() only writes DB rows; Celery sends them.
- _send_sms() is the single send path used by the Celery task.
- send_medication_reminder() supports send_now=True (test/immediate) or
  send_now=False (schedule only — default).
"""

from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import SMSReminder


class SMSReminderService:

    def __init__(self):
        # FIX: wrap entire __init__ in try/except so a bad Twilio credential
        # never crashes Django startup or Celery worker import.
        self.use_twilio    = False
        self.client        = None
        self.twilio_number = None

        try:
            self._init_twilio()
        except Exception as e:
            print(f"⚠️  SMSReminderService init error (falling back to MOCK): {e}")
            self.use_twilio = False
            self.client     = None

    def _init_twilio(self):
        """Initialise Twilio client. Called only from __init__ inside try/except."""
        use_twilio = getattr(settings, 'USE_TWILIO', False)
        if not use_twilio:
            print("📱 SMS Service running in MOCK mode (USE_TWILIO=False)")
            return

        account_sid  = getattr(settings, 'TWILIO_ACCOUNT_SID',  None)
        auth_token   = getattr(settings, 'TWILIO_AUTH_TOKEN',   None)
        phone_number = getattr(settings, 'TWILIO_PHONE_NUMBER', None)

        if not all([account_sid, auth_token, phone_number]):
            print("⚠️  Twilio credentials incomplete — running in MOCK mode")
            return

        # FIX: import inside method so a missing twilio package does not crash
        # the module at import time on machines where twilio is not installed.
        try:
            from twilio.rest import Client
            self.client        = Client(account_sid, auth_token)
            self.twilio_number = phone_number
            self.use_twilio    = True
            print("✅ Twilio SMS Service initialised")
        except ImportError:
            print("⚠️  twilio package not installed — running in MOCK mode")
        except Exception as e:
            print(f"❌ Twilio Client() failed: {e} — running in MOCK mode")

    # ── Phone number formatting ───────────────────────────────────────────────

    def _format_phone(self, phone_number):
        """Normalise to E.164 format (+91XXXXXXXXXX for Indian numbers)."""
        phone = str(phone_number).strip().replace(' ', '').replace('-', '')
        if phone.startswith('+'):
            return phone
        if phone.startswith('91') and len(phone) == 12:
            return f'+{phone}'
        if len(phone) == 10:
            return f'+91{phone}'
        return f'+{phone}'

    # ── Message builder ───────────────────────────────────────────────────────

    def _create_reminder_message(self, patient, medicine):
        timing = getattr(medicine, 'timing', None) or 'as prescribed'
        return (
            f"Medication Reminder\n\n"
            f"Hi {patient.full_name},\n\n"
            f"Time to take your medicine:\n"
            f"Medicine: {medicine.medicine_name}\n"
            f"Dosage:   {medicine.dosage}\n"
            f"Frequency:{medicine.frequency}\n"
            f"Take:     {timing}\n\n"
            f"Stay healthy!"
        )

    # ── Core send (called by Celery task only) ────────────────────────────────

    def _send_sms(self, phone_number, message, sms_reminder):
        """
        Send one SMS and update the SMSReminder row.
        Called by the Celery task at the scheduled time — NOT during upload.
        Returns True on success, False on failure.
        """
        if not self.use_twilio:
            print(f"\n📱 MOCK SMS → {phone_number}\n{message}\n")
            sms_reminder.status     = 'sent'
            sms_reminder.sent_time  = timezone.now()
            sms_reminder.twilio_sid = f"MOCK_{int(timezone.now().timestamp())}"
            sms_reminder.save()
            return True

        try:
            formatted = self._format_phone(phone_number)
            msg = self.client.messages.create(
                body  = message,
                from_ = self.twilio_number,
                to    = formatted,
            )
            sms_reminder.status     = 'sent'
            sms_reminder.sent_time  = timezone.now()
            sms_reminder.twilio_sid = msg.sid
            sms_reminder.save()
            print(f"✅ SMS sent → {formatted} | SID: {msg.sid}")
            return True

        except Exception as e:
            err = str(e)
            sms_reminder.status        = 'failed'
            sms_reminder.error_message = err
            sms_reminder.save()
            print(f"❌ SMS failed → {phone_number}: {err}")
            return False

    # ── Schedule reminders for an entire prescription ─────────────────────────

    def schedule_reminders_for_prescription(self, prescription):
        """
        Write SMSReminder rows to DB only — no SMS is sent here.
        Celery Beat polls every 60 s and calls _send_sms() at the right time.

        FIX: uses timedelta arithmetic instead of datetime.replace() to build
        scheduled_time, avoiding ValueError on DST-boundary times in pytz
        managed timezones.
        """
        medicines         = prescription.medicines.all()
        reminders_created = []
        now               = timezone.now()   # UTC-aware

        for medicine in medicines:
            times_per_day = max(int(medicine.total_doses_per_day or 1), 1)
            duration_days = int(prescription.treatment_duration_days or 7)

            # Hour-of-day schedule for each dose slot
            if times_per_day == 1:
                dose_hours = [9]
            elif times_per_day == 2:
                dose_hours = [9, 21]
            elif times_per_day == 3:
                dose_hours = [8, 14, 20]
            else:
                # Spread evenly across waking hours 08:00–22:00
                step       = 14 // times_per_day
                dose_hours = [8 + i * step for i in range(times_per_day)]

            for day in range(duration_days):
                for hour in dose_hours:
                    # FIX: build scheduled_time with timedelta from midnight of
                    # (now + day) to avoid DST-ambiguous datetime.replace().
                    base_midnight = (now + timedelta(days=day)).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    scheduled_time = base_midnight + timedelta(hours=hour)

                    message = self._create_reminder_message(
                        prescription.patient, medicine)

                    reminder = SMSReminder.objects.create(
                        patient         = prescription.patient,
                        medicine        = medicine,
                        phone_number    = prescription.patient.phone_number,
                        message_content = message,
                        scheduled_time  = scheduled_time,
                        status          = 'scheduled',
                    )
                    reminders_created.append(reminder)

        count = len(reminders_created)
        print(f"📅 {count} reminders scheduled for prescription #{prescription.id}")
        return reminders_created

    # ── Immediate / test send ─────────────────────────────────────────────────

    def send_medication_reminder(self, patient, medicine,
                                 scheduled_time=None, send_now=True):
        """
        Create an SMSReminder row and optionally send immediately.

        send_now=True  → send SMS right away (used by test endpoint)
        send_now=False → only write DB row; Celery will send it later
        """
        if scheduled_time is None:
            scheduled_time = timezone.now()

        message = self._create_reminder_message(patient, medicine)

        sms_reminder = SMSReminder.objects.create(
            patient         = patient,
            medicine        = medicine,
            phone_number    = patient.phone_number,
            message_content = message,
            scheduled_time  = scheduled_time,
            status          = 'scheduled',
        )

        if send_now:
            success = self._send_sms(patient.phone_number, message, sms_reminder)
        else:
            success = True   # Celery will send at scheduled_time

        return sms_reminder, success

    # ── OTP delivery ──────────────────────────────────────────────────────────

    def send_otp_sms(self, phone_number, otp_code):
        message = (
            f"Medication Adherence App\n\n"
            f"Your OTP code is: {otp_code}\n\n"
            f"This code expires in 10 minutes.\n"
            f"Do not share this code with anyone."
        )
        if self.use_twilio and self.client:
            try:
                formatted = self._format_phone(phone_number)
                self.client.messages.create(
                    body  = message,
                    from_ = self.twilio_number,
                    to    = formatted,
                )
                print(f"✅ OTP SMS sent → {formatted}")
                return True
            except Exception as e:
                print(f"❌ OTP SMS failed: {e}")
                return False
        else:
            print(f"\n📱 MOCK OTP → {phone_number} | OTP: {otp_code}\n")
            return True

    # ── High-risk doctor alert ────────────────────────────────────────────────

    def send_high_risk_alert(self, patient, prediction):
        doctor  = patient.doctor
        message = (
            f"HIGH RISK ALERT\n\n"
            f"Patient: {patient.full_name}\n"
            f"Risk:    {prediction.risk_level.upper()}\n"
            f"Score:   {prediction.adherence_score:.2f}\n\n"
            f"Immediate intervention recommended."
        )
        if self.use_twilio and self.client:
            try:
                self.client.messages.create(
                    body  = message,
                    from_ = self.twilio_number,
                    to    = self._format_phone(doctor.phone_number),
                )
                return True
            except Exception as e:
                print(f"❌ High-risk alert failed: {e}")
                return False
        else:
            print(f"\n🚨 MOCK ALERT → {doctor.phone_number}\n{message}\n")
            return True

    # ── Statistics ────────────────────────────────────────────────────────────

    def get_reminder_statistics(self, patient=None):
        qs = SMSReminder.objects.filter(patient=patient) if patient \
             else SMSReminder.objects.all()
        return {
            'total_reminders': qs.count(),
            'sent':            qs.filter(status='sent').count(),
            'scheduled':       qs.filter(status='scheduled').count(),
            'failed':          qs.filter(status='failed').count(),
            'cancelled':       qs.filter(status='cancelled').count(),
            'taken':           qs.filter(status='taken').count(),
        }


# ── Module-level singleton ────────────────────────────────────────────────────
# FIX: wrapped in try/except so a credential failure never prevents Django or
# Celery from starting. All callers (tasks.py, views.py) import this object.
try:
    sms_service = SMSReminderService()
except Exception as _e:
    print(f"❌ CRITICAL: Could not create sms_service singleton: {_e}")
    # Create a bare instance that operates in MOCK mode
    sms_service              = SMSReminderService.__new__(SMSReminderService)
    sms_service.use_twilio   = False
    sms_service.client       = None
    sms_service.twilio_number = None