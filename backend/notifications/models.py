from django.db import models
from accounts.models import Patient
from prescriptions.models import Medicine


class SMSReminder(models.Model):
    """
    Stores SMS reminder logs
    """
    patient  = models.ForeignKey(Patient,  on_delete=models.CASCADE, related_name='sms_reminders')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name='reminders')

    phone_number    = models.CharField(max_length=15)
    message_content = models.TextField()

    scheduled_time = models.DateTimeField()
    sent_time      = models.DateTimeField(null=True, blank=True)

    status = models.CharField(max_length=20, choices=[
        ('scheduled', 'Scheduled'),
        ('sent',      'Sent'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
        ('taken',     'Taken'),       # ✅ NEW — patient marked as taken
    ], default='scheduled')

    twilio_sid    = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    # ✅ NEW — when patient marked it as taken
    taken_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"SMS to {self.patient.full_name} at {self.scheduled_time}"

    class Meta:
        db_table = 'sms_reminders'
        ordering = ['-scheduled_time']


class PushNotification(models.Model):
    """
    Stores push notification logs for mobile app
    """
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='notifications')

    title             = models.CharField(max_length=200)
    message           = models.TextField()
    notification_type = models.CharField(max_length=20, choices=[
        ('medicine',    'Medicine Reminder'),
        ('awareness',   'Health Awareness'),
        ('appointment', 'Appointment'),
        ('general',     'General')
    ], default='general')

    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.patient.full_name}"

    class Meta:
        db_table = 'push_notifications'
        ordering = ['-sent_at']