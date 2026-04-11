from django.urls import path
from . import views

urlpatterns = [
    path('prescription/<int:prescription_id>/schedule/', views.schedule_prescription_reminders, name='schedule-reminders'),
    path('patient/<int:patient_id>/reminders/',          views.get_patient_reminders,            name='patient-reminders'),
    path('statistics/',                                  views.get_reminder_statistics,          name='reminder-statistics'),
    path('test-sms/',                                    views.send_test_sms,                    name='test-sms'),

    # ✅ NEW — patient marks medicine as taken
    path('reminder/<int:reminder_id>/taken/',            views.mark_reminder_taken,              name='mark-taken'),
]