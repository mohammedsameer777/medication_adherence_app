from django.urls import path
from . import views

urlpatterns = [
    # OCR upload
    path('upload/', views.upload_prescription, name='upload-prescription'),

    # Manual prescription entry (no image needed)
    path('manual/', views.create_manual_prescription, name='manual-prescription'),

    # REPLACE all medicines for an existing prescription (used after OCR edit)
    path('<int:prescription_id>/update-medicines/', views.update_medicines_for_prescription, name='update-medicines'),

    # Add missing medicines to existing prescription (appends, does not delete)
    path('<int:prescription_id>/add-medicines/', views.add_medicines_manually, name='add-medicines'),

    # Delete wrong medicine
    path('<int:prescription_id>/medicines/<int:medicine_id>/delete/', views.delete_medicine, name='delete-medicine'),

    # Get prescriptions
    path('<int:prescription_id>/', views.get_prescription, name='get-prescription'),
    path('patient/<int:patient_id>/', views.get_patient_prescriptions, name='patient-prescriptions'),
    path('doctor/all/', views.get_doctor_prescriptions, name='doctor-prescriptions'),

    # Awareness messages
    path('awareness/<str:disease_type>/', views.get_awareness_messages, name='awareness-messages'),
    path('awareness/create/', views.create_awareness_message, name='create-awareness'),
]