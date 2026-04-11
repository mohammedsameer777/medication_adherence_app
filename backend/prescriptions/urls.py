from django.urls import path
from . import views

urlpatterns = [
    # Prescription endpoints
    path('upload/', views.upload_prescription, name='upload-prescription'),
    path('<int:prescription_id>/', views.get_prescription, name='get-prescription'),
    path('patient/<int:patient_id>/', views.get_patient_prescriptions, name='patient-prescriptions'),
    path('doctor/all/', views.get_doctor_prescriptions, name='doctor-prescriptions'),
    
    # Awareness messages
    path('awareness/<str:disease_type>/', views.get_awareness_messages, name='awareness-messages'),
    path('awareness/create/', views.create_awareness_message, name='create-awareness'),
]