from django.urls import path
from . import views

urlpatterns = [
    # ── Original endpoints (unchanged) ────────────────────────────────────────
    path('predict/',                  views.predict_adherence,      name='predict-adherence'),
    path('patient/<int:patient_id>/', views.get_patient_predictions, name='patient-predictions'),
    path('high-risk/',                views.get_high_risk_patients,  name='high-risk-patients'),
    path('stats/',                    views.get_prediction_stats,    name='prediction-stats'),
    path('models/train/',             views.train_models,            name='train-models'),
    path('models/all/',               views.get_all_models,          name='all-models'),

    # ── NEW endpoints ─────────────────────────────────────────────────────────
    path('features/',                 views.get_selected_features,   name='selected-features'),
    path('predict-smart/',            views.predict_with_features,   name='predict-smart'),
]