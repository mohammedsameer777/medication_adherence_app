from twilio.rest import Client
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import SMSReminder


class SMSReminderService:

    def __init__(self):
        self.use_twilio = getattr(settings, 'USE_TWILIO', False)

        if self.use_twilio:
            self.account_sid   = settings.TWILIO_ACCOUNT_SID
            self.auth_token    = settings.TWILIO_AUTH_TOKEN
            self.twilio_number = settings.TWILIO_PHONE_NUMBER
            try:
                from twilio.rest import Client
                self.client = Client(self.account_sid, self.auth_token)
                print("✅ Twilio SMS Service initialized")
            except Exception as e:
                print(f"❌ Twilio init failed: {e}")
                self.use_twilio = False
        else:
            print("📱 SMS Service running in MOCK mode")

    def _format_phone(self, phone_number):
        phone = str(phone_number).strip().replace(' ', '').replace('-', '')
        if phone.startswith('+'):
            return phone
        if phone.startswith('91') and len(phone) == 12:
            return f'+{phone}'
        if len(phone) == 10:
            return f'+91{phone}'
        return f'+{phone}'

    def _create_reminder_message(self, patient, medicine):
        return (
            f"Medication Reminder\n\n"
            f"Hi {patient.full_name},\n\n"
            f"Time to take your medicine:\n"
            f"Medicine: {medicine.medicine_name}\n"
            f"Dosage: {medicine.dosage}\n"
            f"Frequency: {medicine.frequency}\n"
            f"Take: {medicine.timing if medicine.timing else 'as prescribed'}\n\n"
            f"Stay healthy!"
        )

    def _send_sms(self, phone_number, message, sms_reminder):
        """Called by Celery task at scheduled time — NOT during upload."""
        if not self.use_twilio:
            print(f"\n📱 MOCK SMS → {phone_number}\n{message}\n")
            sms_reminder.status     = 'sent'
            sms_reminder.sent_time  = timezone.now()
            sms_reminder.twilio_sid = f"MOCK_{timezone.now().timestamp()}"
            sms_reminder.save()
            return True
        try:
            formatted = self._format_phone(phone_number)
            msg = self.client.messages.create(
                body=message,
                from_=self.twilio_number,
                to=formatted
            )
            sms_reminder.status     = 'sent'
            sms_reminder.sent_time  = timezone.now()
            sms_reminder.twilio_sid = msg.sid
            sms_reminder.save()
            print(f"✅ SMS sent to {formatted} | SID: {msg.sid}")
            return True
        except Exception as e:
            sms_reminder.status        = 'failed'
            sms_reminder.error_message = str(e)
            sms_reminder.save()
            print(f"❌ SMS failed to {phone_number}: {e}")
            return False

    def send_medication_reminder(self, patient, medicine, scheduled_time=None):
        if scheduled_time is None:
            scheduled_time = timezone.now()
        message    = self._create_reminder_message(patient, medicine)
        sms_reminder = SMSReminder.objects.create(
            patient=patient,
            medicine=medicine,
            phone_number=patient.phone_number,
            message_content=message,
            scheduled_time=scheduled_time,
            status='scheduled'
        )
        # Direct send only used for immediate/test reminders
        success = self._send_sms(patient.phone_number, message, sms_reminder)
        return sms_reminder, success

    def schedule_reminders_for_prescription(self, prescription):
        """
        Save reminders to DB only — NO SMS sent here.
        Celery Beat sends SMS at the right time.
        Uses timezone-aware datetimes to fix the naive datetime warning.
        """
        medicines         = prescription.medicines.all()
        reminders_created = []
        now               = timezone.now()

        for medicine in medicines:
            times_per_day = medicine.total_doses_per_day or 1

            for day in range(prescription.treatment_duration_days or 7):
                for dose in range(times_per_day):
                    base_date = now + timedelta(days=day)

                    if times_per_day == 1:
                        hour = 9
                    elif times_per_day == 2:
                        hour = 9 if dose == 0 else 21
                    elif times_per_day == 3:
                        hour = [8, 14, 20][dose]
                    else:
                        hour = 8 + (dose * (14 // times_per_day))

                    # ✅ Use timezone-aware datetime — fixes naive datetime warning
                    scheduled_time = base_date.replace(
                        hour=hour, minute=0, second=0, microsecond=0)

                    message = self._create_reminder_message(
                        prescription.patient, medicine)

                    reminder = SMSReminder.objects.create(
                        patient=prescription.patient,
                        medicine=medicine,
                        phone_number=prescription.patient.phone_number,
                        message_content=message,
                        scheduled_time=scheduled_time,
                        status='scheduled',
                    )
                    reminders_created.append(reminder)

        print(f"📅 {len(reminders_created)} reminders scheduled in DB")
        return reminders_created

    def send_otp_sms(self, phone_number, otp_code):
        message = (
            f"Medication Adherence App\n\n"
            f"Your OTP code is: {otp_code}\n\n"
            f"This code expires in 10 minutes.\n"
            f"Do not share this code with anyone."
        )
        if self.use_twilio:
            try:
                formatted = self._format_phone(phone_number)
                self.client.messages.create(
                    body=message, from_=self.twilio_number, to=formatted)
                print(f"✅ OTP sent to {formatted}")
                return True
            except Exception as e:
                print(f"❌ OTP failed: {e}")
                return False
        else:
            print(f"\n📱 MOCK OTP → {phone_number} | OTP: {otp_code}\n")
            return True

    def send_high_risk_alert(self, patient, prediction):
        doctor  = patient.doctor
        message = (
            f"HIGH RISK ALERT\n\nPatient: {patient.full_name}\n"
            f"Risk: {prediction.risk_level.upper()}\n"
            f"Score: {prediction.adherence_score:.2f}\n\n"
            f"Immediate intervention recommended."
        )
        if self.use_twilio:
            try:
                self.client.messages.create(
                    body=message, from_=self.twilio_number,
                    to=self._format_phone(doctor.phone_number))
                return True
            except Exception as e:
                print(f"❌ Alert failed: {e}")
                return False
        else:
            print(f"\n🚨 MOCK ALERT → {doctor.phone_number}\n")
            return True

    def get_reminder_statistics(self, patient=None):
        reminders = SMSReminder.objects.filter(
            patient=patient) if patient else SMSReminder.objects.all()
        return {
            'total_reminders': reminders.count(),
            'sent':      reminders.filter(status='sent').count(),
            'scheduled': reminders.filter(status='scheduled').count(),
            'failed':    reminders.filter(status='failed').count(),
            'cancelled': reminders.filter(status='cancelled').count(),
            'taken':     reminders.filter(status='taken').count(),
        }


sms_service = SMSReminderService()