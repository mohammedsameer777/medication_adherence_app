from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from .models import AdherencePrediction, MLModel
from accounts.models import Patient
from prescriptions.models import Prescription
from .serializers import (
    AdherencePredictionSerializer, PredictionRequestSerializer,
    MLModelSerializer
)
from .ml_service import predictor


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _get_severity(disease_type):
    severity_map = {
        'diabetes': 1, 'hypertension': 1,
        'heart disease': 2, 'kidney disease': 2,
        'cancer': 2, 'asthma': 1, 'arthritis': 0
    }
    disease_lower = str(disease_type).lower()
    return next((v for k, v in severity_map.items() if k in disease_lower), 1)


# ─────────────────────────────────────────────────────────────────────────────
# ORIGINAL ENDPOINTS (all unchanged — nothing broken)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_adherence(request):
    """
    Original endpoint — predict via uploaded prescription (OCR path).
    POST /api/predictions/predict/
    """
    serializer = PredictionRequestSerializer(data=request.data)

    if serializer.is_valid():
        patient_id      = serializer.validated_data['patient_id']
        prescription_id = serializer.validated_data['prescription_id']

        patient      = get_object_or_404(Patient, id=patient_id)
        prescription = get_object_or_404(Prescription, id=prescription_id)

        age           = prescription.age_extracted or patient.age
        num_medicines = prescription.total_medicines
        total_doses   = sum([med.total_doses_per_day for med in prescription.medicines.all()])
        duration      = prescription.treatment_duration_days
        disease       = prescription.disease_extracted or patient.disease_type

        try:
            input_data = {
                'Age':                       age,
                'gender_encoded':            0,
                'medication_type_encoded':   0,
                'dosage_normalized':         min(total_doses / 15, 1.0),
                'Previous_Adherence':        1,
                'education_encoded':         1,
                'income_normalized':         0.5,
                'social_support_encoded':    1,
                'severity_encoded':          _get_severity(disease),
                'Comorbidities_Count':       max(0, num_medicines - 2),
                'healthcare_access_encoded': 1,
                'mental_health_encoded':     2,
                'Insurance_Coverage':        1,
            }

            result = predictor.predict(input_data)

            prediction = AdherencePrediction.objects.create(
                patient=patient,
                prescription=prescription,
                age=age,
                num_medicines=num_medicines,
                total_doses_per_day=total_doses,
                treatment_duration_days=duration,
                disease_type=disease,
                adherence_score=result['adherence_score'],
                risk_level=result['risk_level'],
                model_used=result['model_used'],
                recommendation=result['recommendation']
            )

            return Response({
                'success': True,
                'message': 'Prediction generated successfully',
                'data': {
                    'prediction':          AdherencePredictionSerializer(prediction).data,
                    'confidence':          result['confidence'],
                    'adherence_percentage': result.get('adherence_percentage', 0),
                }
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'success': False,
                'message': 'Prediction failed',
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response({
        'success': False,
        'message': 'Invalid data',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_predictions(request, patient_id):
    """GET /api/predictions/patient/<patient_id>/"""
    patient     = get_object_or_404(Patient, id=patient_id)
    predictions = AdherencePrediction.objects.filter(
        patient=patient).order_by('-created_at')

    return Response({
        'success': True,
        'data': {
            'total_predictions': predictions.count(),
            'predictions':       AdherencePredictionSerializer(predictions, many=True).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_high_risk_patients(request):
    """GET /api/predictions/high-risk/"""
    high_risk_predictions = AdherencePrediction.objects.filter(
        risk_level='high').order_by('-created_at')
    patient_ids = high_risk_predictions.values_list(
        'patient_id', flat=True).distinct()

    return Response({
        'success': True,
        'data': {
            'total_high_risk_patients': len(patient_ids),
            'predictions':              AdherencePredictionSerializer(
                high_risk_predictions, many=True).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def train_models(request):
    """POST /api/predictions/models/train/"""
    try:
        results = predictor.train_models()

        saved_models = []
        model_type_map = {
            'Logistic Regression': 'logistic',
            'Random Forest':       'random_forest',
            'SVM':                 'svm',
            'XGBoost':             'xgboost',
            'Gradient Boosting':   'other',
            'Voting Ensemble':     'other',
        }

        for result in results:
            model_type = model_type_map.get(result['model_name'], 'other')
            ml_model = MLModel.objects.create(
                model_name=result['model_name'],
                model_type=model_type,
                accuracy=result['accuracy'] * 100,
                precision=result['precision'] * 100,
                recall=result['recall'] * 100,
                f1_score=result['f1_score'] * 100,
                model_file_path=(
                    f"ml_models/"
                    f"{result['model_name'].replace(' ', '_').lower()}_model.pkl"
                ),
                is_active=(result['model_name'] == predictor.best_model_name),
                notes='Trained with feature selection + StandardScaler'
            )
            saved_models.append(ml_model)

        return Response({
            'success': True,
            'message': 'Models trained successfully',
            'data': {
                'best_model':        predictor.best_model_name,
                'selected_features': predictor.get_selected_features(),
                'models':            MLModelSerializer(saved_models, many=True).data
            }
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({
            'success': False,
            'message': 'Model training failed',
            'error':   str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_models(request):
    """GET /api/predictions/models/all/"""
    models = MLModel.objects.all().order_by('-f1_score')
    return Response({
        'success': True,
        'data': {
            'total_models': models.count(),
            'models':       MLModelSerializer(models, many=True).data
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_prediction_stats(request):
    """GET /api/predictions/stats/"""
    total       = AdherencePrediction.objects.count()
    low_risk    = AdherencePrediction.objects.filter(risk_level='low').count()
    medium_risk = AdherencePrediction.objects.filter(risk_level='medium').count()
    high_risk   = AdherencePrediction.objects.filter(risk_level='high').count()

    return Response({
        'success': True,
        'data': {
            'total_predictions':      total,
            'low_risk_count':         low_risk,
            'medium_risk_count':      medium_risk,
            'high_risk_count':        high_risk,
            'low_risk_percentage':    (low_risk    / total * 100) if total > 0 else 0,
            'medium_risk_percentage': (medium_risk / total * 100) if total > 0 else 0,
            'high_risk_percentage':   (high_risk   / total * 100) if total > 0 else 0,
        }
    }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# NEW ENDPOINTS
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_selected_features(request):
    """
    GET /api/predictions/features/
    Returns selected features + all 13 importance scores for Flutter chart.
    """
    features    = predictor.get_selected_features()
    importances = predictor.get_feature_importances()

    if not features:
        return Response({
            'success': False,
            'message': 'Model not trained yet. Call POST /models/train/ first.'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    ranked = sorted(importances.items(), key=lambda x: x[1], reverse=True)

    return Response({
        'success': True,
        'data': {
            'selected_features':        features,
            'total_features_available': 13,
            'features_selected':        len(features),
            'importances_ranked': [
                {
                    'feature':    feat,
                    'importance': round(imp, 4),
                    'selected':   feat in features
                }
                for feat, imp in ranked
            ]
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def predict_with_features(request):
    """
    POST /api/predictions/predict-smart/
    Smart prediction — doctor sends 7 feature values directly.
    SAVES result to AdherencePrediction database if patient_id provided.

    Body example:
    {
        "patient_id": 6,
        "Age": 45,
        "income_normalized": 0.3,
        "dosage_normalized": 0.7,
        "Previous_Adherence": 0,
        "Comorbidities_Count": 3,
        "severity_encoded": 2,
        "healthcare_access_encoded": 1
    }
    """
    if not predictor.get_selected_features():
        return Response({
            'success': False,
            'message': 'Model not trained. POST to /models/train/ first.'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Extract patient_id — remove it from ML input dict
    patient_id = request.data.get('patient_id')
    input_data = {k: v for k, v in request.data.items() if k != 'patient_id'}

    try:
        result = predictor.predict(input_data)

        # Save to database if patient_id provided
        saved_prediction = None
        if patient_id:
            try:
                patient = Patient.objects.get(id=patient_id)
                saved_prediction = AdherencePrediction.objects.create(
                    patient=patient,
                    prescription=None,
                    age=int(float(input_data.get('Age', 0))),
                    num_medicines=int(float(input_data.get('Comorbidities_Count', 0))) + 1,
                    total_doses_per_day=0,
                    treatment_duration_days=90,
                    disease_type=patient.disease_type or 'Unknown',
                    adherence_score=result['adherence_score'],
                    risk_level=result['risk_level'],
                    model_used=result['model_used'],
                    recommendation=result['recommendation']
                )
            except Patient.DoesNotExist:
                pass
            except Exception:
                pass

        response_data = {**result}
        if saved_prediction:
            response_data['prediction_id'] = saved_prediction.id
            response_data['saved_to_db']   = True
        else:
            response_data['saved_to_db'] = False

        return Response({
            'success': True,
            'data':    response_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({
            'success': False,
            'error':   str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)