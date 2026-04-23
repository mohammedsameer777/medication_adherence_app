from django.urls import path
from . import views
from . import patient_monitoring_views   # ← NEW

urlpatterns = [
    # ── Auth ──────────────────────────────────────────────────────────────────
    path('doctor/login/',    views.doctor_login,    name='doctor_login'),
    path('doctor/register/', views.doctor_register, name='doctor_register'),

    path('patient/send-otp/',    views.patient_send_otp,    name='patient_send_otp'),
    path('patient/verify-otp/',  views.patient_verify_otp,  name='patient_verify_otp'),
    path('patient/register/',    views.patient_register,    name='patient_register'),
    path('patient/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),

    path('user/me/', views.get_current_user, name='get_current_user'),

    # ── Doctor APIs ───────────────────────────────────────────────────────────
    path('doctor/patients/', views.get_doctor_patients, name='get_doctor_patients'),

    # ── Patient Monitoring (NEW) ──────────────────────────────────────────────
    path('patient/<int:patient_id>/monitoring/',
         patient_monitoring_views.get_patient_monitoring,
         name='patient_monitoring'),
]