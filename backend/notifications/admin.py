from django.contrib import admin
from .models import SMSReminder, PushNotification


@admin.register(SMSReminder)
class SMSReminderAdmin(admin.ModelAdmin):
    list_display = ['patient', 'medicine', 'scheduled_time', 'sent_time', 'status']
    list_filter = ['status', 'scheduled_time', 'created_at']
    search_fields = ['patient__full_name', 'phone_number', 'medicine__medicine_name']
    readonly_fields = ['created_at']


@admin.register(PushNotification)
class PushNotificationAdmin(admin.ModelAdmin):
    list_display = ['patient', 'title', 'notification_type', 'is_read', 'sent_at']
    list_filter = ['notification_type', 'is_read', 'sent_at']
    search_fields = ['patient__full_name', 'title', 'message']
    readonly_fields = ['sent_at']