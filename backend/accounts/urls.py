from django.urls import path
from . import views

urlpatterns = [
    # Authentication endpoints
    path('doctor/login/', views.doctor_login, name='doctor-login'),
    path('doctor/register/', views.doctor_register, name='doctor-register'),
    
    path('patient/send-otp/', views.patient_send_otp, name='patient-send-otp'),
    path('patient/verify-otp/', views.patient_verify_otp, name='patient-verify-otp'),
    path('patient/register/', views.patient_register, name='patient-register'),
    
    # User info endpoints
    path('user/me/', views.get_current_user, name='current-user'),
    path('doctor/patients/', views.get_doctor_patients, name='doctor-patients'),
    path('patient/<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),
]