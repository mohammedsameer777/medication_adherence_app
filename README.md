# 💊 Medication Adherence App

A full-stack mobile application that uses Machine Learning to predict medication non-adherence risk, automate SMS reminders, and enable doctors to monitor patient compliance — built with **Django REST Framework**, **Flutter**, and **Scikit-learn**.

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Tech Stack](#tech-stack)
4. [Project Structure](#project-structure)
5. [Django Apps & Models](#django-apps--models)
6. [Machine Learning Pipeline](#machine-learning-pipeline)
7. [OCR Pipeline](#ocr-pipeline)
8. [SMS Notification Service](#sms-notification-service)
9. [Authentication System](#authentication-system)
10. [API Reference](#api-reference)
11. [Flutter Frontend](#flutter-frontend)
12. [Configuration & Settings](#configuration--settings)
13. [Getting Started](#getting-started)
14. [Demo Credentials](#demo-credentials)
15. [Known Issues & Fixes Applied](#known-issues--fixes-applied)

---

## Overview

Around 50% of patients with chronic diseases do not take their medications as prescribed, leading to poor health outcomes and avoidable hospitalizations. This app tackles that gap by:

- Predicting adherence risk (**Low / Medium / High**) using an ML pipeline trained on 5,002 real patient records from Kaggle
- Sending automated **SMS reminders** via Twilio (with a mock/console mode for development)
- Allowing doctors to **upload prescription images** that are processed with Tesseract OCR to extract patient and medicine data automatically
- Providing a **Flutter mobile app** for both doctors (dashboard, smart predictions, feature importance) and patients (OTP login, reminders, awareness messages)

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                   Flutter Frontend (Dart)                     │
│   Doctor: Dashboard · Smart Prediction · Feature Importance   │
│   Patient: OTP Login · Prescriptions · Reminders              │
│   State: Provider  |  HTTP: http + dio  |  Storage: SharedPrefs│
└───────────────────────────┬──────────────────────────────────┘
                            │ REST API (JWT Bearer Token)
┌───────────────────────────▼──────────────────────────────────┐
│              Django REST Framework  (Port 8000)               │
│                                                               │
│  ┌───────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ accounts  │  │ prescriptions│  │      predictions       │ │
│  │           │  │              │  │                        │ │
│  │ Doctor    │  │ Prescription │  │ AdherencePrediction    │ │
│  │ Patient   │  │ Medicine     │  │ MLModel                │ │
│  │ OTP       │  │ AwarenessMsg │  │ ml_service.py          │ │
│  └───────────┘  │ ocr_service  │  │ data_loader.py         │ │
│                 └──────────────┘  └────────────────────────┘ │
│                                                               │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                    notifications                          │ │
│  │  SMSReminder · PushNotification · sms_service.py         │ │
│  └──────────────────────────────────────────────────────────┘ │
└───────┬───────────────┬──────────────────┬────────────────────┘
        │               │                  │
   SQLite DB       Twilio SMS        ml_models/ (pkl files)
   (db.sqlite3)   (or mock mode)    random_forest_model.pkl
                                    scaler.pkl
                                    label_encoders.pkl
                                    feature_names.pkl
                                    feature_importances.pkl
```

---

## Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Backend framework | Django + Django REST Framework | 4.2 |
| Auth | `djangorestframework-simplejwt` | JWT (7-day access, 30-day refresh) |
| Database | SQLite | (PostgreSQL/MySQL ready) |
| ML | Scikit-learn, XGBoost, Pandas, NumPy | — |
| OCR | Tesseract + OpenCV (cv2) + PIL | — |
| SMS | Twilio (with mock fallback) | — |
| CORS | `django-cors-headers` | — |
| Frontend | Flutter | SDK ≥ 3.0 |
| State management | Provider | ^6.1.1 |
| HTTP client | `http` + `dio` | ^1.1.0 / ^5.4.0 |
| Charts | `fl_chart` | ^0.66.0 |
| Local storage | `shared_preferences` | ^2.2.2 |
| Image picker | `image_picker` | ^1.0.7 |
| Timezone | Asia/Kolkata | set in settings.py |

---

## Project Structure

```
medication_adherence_app/
│
├── backend/
│   ├── accounts/                  # Doctor & patient auth, OTP
│   │   ├── models.py              # Doctor, Patient, OTP models
│   │   ├── views.py               # Login, register, OTP views
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── prescriptions/             # Prescription upload & OCR
│   │   ├── models.py              # Prescription, Medicine, AwarenessMessage
│   │   ├── ocr_service.py         # Tesseract + OpenCV OCR pipeline
│   │   ├── views.py
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── predictions/               # ML training & inference
│   │   ├── ml_service.py          # AdherencePredictor class (core ML)
│   │   ├── data_loader.py         # DatasetLoader class (Kaggle CSV)
│   │   ├── models.py              # AdherencePrediction, MLModel
│   │   ├── views.py               # Predict, train, stats, features
│   │   ├── serializers.py
│   │   └── urls.py
│   │
│   ├── notifications/             # SMS reminders & push notifications
│   │   ├── sms_service.py         # SMSReminderService (Twilio/mock)
│   │   ├── models.py              # SMSReminder, PushNotification
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── medication_backend/        # Django project config
│   │   ├── settings.py
│   │   └── urls.py
│   │
│   ├── datasets/
│   │   └── patient_adherence_dataset.csv   # 5,002 Kaggle records
│   │
│   ├── ml_models/                 # Auto-generated after training
│   │   ├── random_forest_model.pkl
│   │   ├── scaler.pkl
│   │   ├── label_encoders.pkl
│   │   ├── feature_names.pkl
│   │   ├── feature_importances.pkl
│   │   └── dataset_info.pkl
│   │
│   └── manage.py
│
├── medication_app/                # Flutter application
│   └── lib/
│       ├── config/constants.dart  # API base URL & all endpoint constants
│       ├── main.dart
│       ├── providers/
│       │   └── auth_provider.dart
│       ├── screens/
│       │   ├── splash_screen.dart
│       │   ├── doctor/
│       │   │   ├── doctor_login_screen.dart
│       │   │   ├── doctor_dashboard.dart
│       │   │   ├── smart_prediction_screen.dart
│       │   │   └── feature_importance_screen.dart
│       │   └── patient/
│       │       ├── patient_login_screen.dart
│       │       └── patient_dashboard.dart
│       └── services/
│           └── api_service.dart   # Singleton HTTP client
│
├── requirements.txt
└── .gitignore
```

---

## Django Apps & Models

### `accounts` app

**Doctor**
```
db_table: doctors
Fields: user (OneToOne → Django User), full_name, phone_number (unique),
        specialization, hospital_name, registration_number (unique),
        created_at, updated_at, is_active
```

**Patient**
```
db_table: patients
Fields: doctor (FK → Doctor), full_name, phone_number (unique), age,
        gender (male/female/other), disease_type,
        is_verified, last_login, created_at, updated_at, is_active
```

**OTP**
```
db_table: otp_codes
Fields: phone_number, otp_code (6-digit, auto-generated on save),
        created_at, is_verified,
        expires_at (auto = now + 10 minutes)
Method: is_valid() → returns True if not expired AND not already used
```

---

### `prescriptions` app

**Prescription**
```
db_table: prescriptions
Fields: patient (FK), doctor (FK),
        prescription_image (ImageField → media/prescriptions/),
        extracted_text, patient_name_extracted, age_extracted, disease_extracted,
        treatment_duration_days, total_medicines,
        is_processed, ocr_status (pending/processing/completed/failed),
        created_at, updated_at
```

**Medicine**
```
db_table: medicines
Fields: prescription (FK, related_name='medicines'),
        medicine_name, dosage, frequency, timing, duration_days,
        morning, afternoon, evening, night (BooleanFields),
        total_doses_per_day, created_at
```

**AwarenessMessage**
```
db_table: awareness_messages
Fields: disease_type, message_title, message_content,
        message_type (tip/warning/info/reminder), is_active, created_at
```

---

### `predictions` app

**AdherencePrediction**
```
db_table: adherence_predictions
Fields: patient (FK),
        prescription (FK, null=True — supports prescription-free smart predictions),
        age, num_medicines, total_doses_per_day, treatment_duration_days, disease_type,
        adherence_score (Float 0.0-1.0), risk_level (low/medium/high),
        model_used, model_accuracy, recommendation (Text), created_at
```

**MLModel**
```
db_table: ml_models
Fields: model_name, model_type (logistic/random_forest/svm/xgboost/deep_learning),
        accuracy, precision, recall, f1_score,
        model_file_path, is_active, training_date, notes
```

---

### `notifications` app

**SMSReminder**
```
db_table: sms_reminders
Fields: patient (FK), medicine (FK), phone_number, message_content,
        scheduled_time, sent_time,
        status (scheduled/sent/failed/cancelled),
        twilio_sid, error_message, created_at
```

**PushNotification**
```
db_table: push_notifications
Fields: patient (FK), title, message,
        notification_type (medicine/awareness/appointment/general),
        is_read, sent_at
```

---

## Machine Learning Pipeline

### Dataset

- **Source:** Kaggle — `patient_adherence_dataset.csv`
- **Records:** 5,002 patients
- **Location:** `backend/datasets/patient_adherence_dataset.csv`

### All 13 Raw Features

| Feature | Type | Encoding |
|---------|------|----------|
| Age | Numeric | Used as-is |
| Gender | Categorical | Male=0, Female=1, Other=2 → `gender_encoded` |
| Medication_Type | Categorical | TypeA=0, TypeB=1, TypeC=2 → `medication_type_encoded` |
| Dosage_mg | Numeric | Min-max normalised → `dosage_normalized` |
| Previous_Adherence | Binary | 0 = poor history, 1 = good history |
| Education_Level | Ordinal | High School=0, Graduate=1, Postgraduate=2 → `education_encoded` |
| Income | Numeric | Min-max normalised → `income_normalized` |
| Social_Support_Level | Ordinal | Low=0, Medium=1, High=2 → `social_support_encoded` |
| Condition_Severity | Ordinal | Mild=0, Moderate=1, Severe=2 → `severity_encoded` |
| Comorbidities_Count | Numeric | Used as-is |
| Healthcare_Access | Ordinal | Poor=0, Average=1, Good=2 → `healthcare_access_encoded` |
| Mental_Health_Status | Ordinal | Poor=0, Moderate=1, Good=2 → `mental_health_encoded` |
| Insurance_Coverage | Binary | 0 = no insurance, 1 = insured |

### Target Variable: `adherence_risk`

The dataset's binary `Adherence` column (0/1) is converted to a **3-class risk score** using a weighted multi-factor formula in `DatasetLoader._convert_adherence_to_risk()`:

```
risk_score =
    (Adherence == 0)          × 0.30   ← current non-adherence
  + (Previous_Adherence == 0) × 0.20   ← past non-adherence
  + (Comorbidities_Count ≥ 3) × 0.15   ← complex regimen
  + Condition_Severity_risk   × 0.15   ← Mild→0, Moderate→0.5, Severe→1
  + Healthcare_Access_risk    × 0.10   ← Good→0, Average→0.5, Poor→1
  + Mental_Health_risk        × 0.10   ← Good→0, Moderate→0.5, Poor→1

Binned:  [0.00, 0.33] → 'low'
         (0.33, 0.66] → 'medium'
         (0.66, 1.00] → 'high'
```

### Feature Selection (Automatic)

Before training, a **preliminary Random Forest** runs on all 13 features to score importance. The **top 7 features** are selected automatically and used for all downstream models:

```python
selector_rf = RandomForestClassifier(
    n_estimators=200, max_depth=10, random_state=42,
    n_jobs=-1, class_weight='balanced'
)
selector_rf.fit(X_all_13_features, y)
# → top 7 by feature_importances_ are selected
```

Selected features are then scaled with **`StandardScaler`** before being passed to all models (especially important for Logistic Regression and SVM).

### Models Trained

All 4 models are trained on an **80/20 stratified train/test split** and evaluated with **5-fold Stratified Cross-Validation** (cv_f1_mean ± std is reported for each):

**Logistic Regression**
```python
LogisticRegression(
    max_iter=2000, random_state=42,
    class_weight='balanced', C=0.5, solver='lbfgs'
)
```

**Random Forest**
```python
RandomForestClassifier(
    n_estimators=500, max_depth=12,
    min_samples_split=4, min_samples_leaf=2,
    max_features='sqrt', random_state=42,
    class_weight='balanced', n_jobs=-1,
    bootstrap=True, oob_score=True   # OOB score reported
)
```

**Gradient Boosting**
```python
GradientBoostingClassifier(
    n_estimators=300, learning_rate=0.05,
    max_depth=5, min_samples_split=4,
    subsample=0.8, random_state=42
)
```

**XGBoost**
```python
xgb.XGBClassifier(
    n_estimators=300, learning_rate=0.05,
    max_depth=6, subsample=0.8, colsample_bytree=0.8,
    random_state=42, eval_metric='mlogloss', n_jobs=-1
)
```

### Voting Ensemble

After individual training, a **soft-voting ensemble** is built from the **top 3 sklearn models** ranked by cross-validated F1 (XGBoost excluded — sklearn VotingClassifier API incompatibility):

```python
VotingClassifier(
    estimators=[(name, model) for top 3 sklearn models],
    voting='soft',
    n_jobs=-1
)
```

### Model Selection

The **best model by weighted F1-score** across all 5 candidates (4 individual + ensemble) is auto-selected and saved as the production model.

### Per-Model Metrics Reported During Training

For every model, the following are printed and saved to `MLModel` DB:
- Accuracy, Precision (weighted), Recall (weighted), F1-Score (weighted)
- CV F1 mean ± std (5-fold)
- OOB Score (Random Forest only)
- Per-class Classification Report
- Top 5 feature importances (tree-based models only)

### Prediction Output

```python
predictor.predict(input_data) → {
    'risk_level':              'low' | 'medium' | 'high',
    'confidence':              float,          # max class probability
    'adherence_score':         float,          # 0.0 – 1.0
    'adherence_percentage':    float,          # adherence_score × 100
    'model_used':              str,
    'recommendation':          str,            # personalised action plan
    'risk_probabilities':      {'low': f, 'medium': f, 'high': f},
    'selected_features_used':  list[str]       # 7 selected feature names
}
```

**`adherence_score` formula (bug fixed):**
```python
# OLD (buggy): 1 - (label_index / 2) → was always 1.0 for 'high'
# NEW (fixed):
adherence_score = low_probability + 0.5 * medium_probability
# Higher score = better adherence likelihood (0 = certain high risk, 1 = certain low risk)
```

### Contextual Recommendations

| Risk Level | Core Actions |
|-----------|-------------|
| `low` | Regular follow-ups, monthly check-ins, maintain current habits |
| `medium` | Daily SMS reminders, weekly calls, pill organiser, bi-weekly monitoring |
| `high` | Daily SMS + call reminders, family involvement, home visits, daily monitoring, weekly consultations, medication synchronisation |

Additional rules appended contextually:
- Age > 65 → "Caregiver assistance recommended"
- Medicines > 5 → "Use medication adherence aids"
- Treatment > 90 days → "Provide ongoing motivation"

### Saved Model Artifacts

All written to `backend/ml_models/` via `pickle`:

| File | Contents |
|------|---------|
| `<model_name>_model.pkl` | Best trained model |
| `scaler.pkl` | Fitted `StandardScaler` (for the 7 selected features) |
| `label_encoders.pkl` | Dict of `LabelEncoder` objects |
| `feature_names.pkl` | List of 7 selected feature names |
| `feature_importances.pkl` | Dict of all 13 feature importance scores |
| `dataset_info.pkl` | Dataset statistics snapshot |

### Two Prediction Modes

**Mode 1 — OCR Path** (`POST /api/predictions/predict/`):
Input features are automatically derived from the OCR-parsed prescription:
- `Age` ← `prescription.age_extracted` or `patient.age`
- `dosage_normalized` ← `total_doses / 15` (capped at 1.0)
- `Comorbidities_Count` ← `num_medicines - 2`
- `severity_encoded` ← mapped from disease keyword
- Others default to neutral values

**Mode 2 — Smart Path** (`POST /api/predictions/predict-smart/`):
Doctor manually inputs the 7 feature values in Flutter. Prediction is saved to `AdherencePrediction` if `patient_id` is supplied.

---

## OCR Pipeline

**Engine:** Tesseract OCR  
**Class:** `PrescriptionOCR` in `backend/prescriptions/ocr_service.py`

### Preprocessing

**OpenCV path (primary — if cv2 is installed):**
```
cv2.imread(image_path)
→ cv2.cvtColor(BGR → GRAY)
→ cv2.threshold(THRESH_BINARY + THRESH_OTSU)
→ cv2.fastNlMeansDenoising(h=10, templateWindowSize=7, searchWindowSize=21)
→ pytesseract.image_to_string(processed_img)
```

**PIL path (fallback — if OpenCV not installed):**
```
Image.open(image_path)
→ img.convert('L')  # grayscale
→ pytesseract.image_to_string(img)
```

### Extraction Rules

**Patient Name** — tried in order:
1. `Patient Name: <name>`
2. `Name: <name>`
3. `Patient: <name>`
→ Validated: length 3–50 characters

**Age** — tried in order:
1. `Age: <n>`
2. `<n> years` / `<n> yrs`
→ Validated: 1–120

**Disease / Diagnosis** — tried in order:
1. `Diagnosis: ...` / `Disease: ...` / `Condition: ...`
2. Keyword scan for: `diabetes, hypertension, asthma, arthritis, thyroid, fever, cold, cough, infection, blood pressure, heart disease, kidney disease, liver disease`

**Medicines** — line-by-line scan:
- Pattern: `<Name> <dosage: mg|tablet|cap|ml>`
- Extracts frequency (`<n> times daily`), duration (`<n> days`)
- Skips lines containing: prescription, patient, doctor, date, diagnosis, name, age

**Treatment Duration:**
1. `<n> days` / `Duration: <n> days` / `for <n> days`
→ Validated: 1–365, default: 7

### Full `parse_prescription()` Return

```python
{
    'success': True,
    'extracted_text': str,
    'patient_name': str | None,
    'age': int | None,
    'disease': str | None,
    'medicines': [
        {'name': str, 'dosage': str, 'frequency': str, 'duration_days': int},
        ...
    ],
    'treatment_duration_days': int,
    'total_medicines': int
}
```

### Upload Flow

```
Doctor uploads image via Flutter
  → POST /api/prescriptions/upload/
  → prescription.ocr_status = 'processing'
  → PrescriptionOCR.parse_prescription(image_path)
  → On success:
      Save extracted fields to Prescription
      Create Medicine records for each parsed medicine
      ocr_status = 'completed'
  → On failure:
      ocr_status = 'failed'
```

### Tesseract Path

```python
# settings.py
TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Windows
# TESSERACT_CMD = '/usr/bin/tesseract'                           # Linux/macOS
```

---

## SMS Notification Service

**Class:** `SMSReminderService` in `backend/notifications/sms_service.py`  
**Singleton:** `sms_service = SMSReminderService()` — imported directly by notification views

### Modes

| `USE_TWILIO` | Behaviour |
|-------------|-----------|
| `True` | Real SMS via Twilio REST API |
| `False` | Mock mode — message printed to Django console |

### Phone Number Formatting (E.164)

```python
# Already has + prefix → used as-is
# Starts with '91' and length 12 → +<number>
# 10-digit → +91<number>  (Indian mobile)
```

### Message Types

**Medication Reminder:**
```
Medication Reminder

Hi <Patient Name>,

Time to take your medicine:
Medicine: <medicine_name>
Dosage: <dosage>
Frequency: <frequency>
Take: <timing or 'as prescribed'>

Stay healthy!
```

**OTP (Patient Login):**
```
Medication Adherence App

Your OTP code is: <6-digit code>

This code expires in 10 minutes.
Do not share this code with anyone.
```

**High Risk Alert (to Doctor):**
```
HIGH RISK ALERT

Patient: <full_name>
Age: <age>
Disease: <disease_type>

Adherence Risk: HIGH
Score: <adherence_score>

Immediate intervention recommended.
```

### Reminder Scheduling

`schedule_reminders_for_prescription(prescription)` creates reminders for **7 days**, for every medicine in the prescription:

| Doses/day | Times |
|-----------|-------|
| 1 | 09:00 |
| 2 | 09:00, 21:00 |
| 3 | 08:00, 14:00, 20:00 |
| 4+ | Distributed from 08:00 at `14 / n` hour intervals |

Each reminder is saved as an `SMSReminder` with status `sent` (or `failed`) and `twilio_sid` (or `MOCK_<timestamp>`).

### Statistics

`get_reminder_statistics(patient=None)` returns:
```python
{
    'total_reminders': int,
    'sent': int,
    'scheduled': int,
    'failed': int,
    'cancelled': int
}
```

---

## Authentication System

### Doctor Auth — Username + Password

1. `POST /api/auth/doctor/login/` with `{username, password}`
2. Django's `authenticate()` validates credentials against the `Doctor` + `User` model
3. Returns JWT access token (7-day) + refresh token (30-day)
4. JWT carries custom claim: `user_type = 'doctor'`

### Patient Auth — OTP (Passwordless)

1. `POST /api/auth/patient/send-otp/` with `{phone_number}`
   - Generates 6-digit OTP, expiry = now + 10 minutes
   - Demo mode: OTP returned in response body
   - Production: sent via Twilio `send_otp_sms()`
2. `POST /api/auth/patient/verify-otp/` with `{phone_number, otp_code}`
   - Validates OTP hasn't expired and `is_verified=False`
   - Gets or creates Django `User` with username `patient_<phone_number>`
   - Ensures `user.is_active = True`
   - Returns JWT access token

### JWT Settings

```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS':  False,
    'ALGORITHM':              'HS256',
    'AUTH_HEADER_TYPES':      ('Bearer',),
}
```

### Doctor Isolation

Every doctor sees **only their own patients**. `get_doctor_patients` resolves the doctor from `request.user` via the JWT token — there is no hardcoded patient lookup.

---

## API Reference

All endpoints are prefixed with `/api/`. All except the four auth endpoints require `Authorization: Bearer <token>`.

### Auth — `/api/auth/`

| Method | Endpoint | Auth Required | Description |
|--------|----------|:---:|-------------|
| `POST` | `doctor/login/` | ❌ | Doctor login → JWT |
| `POST` | `doctor/register/` | ❌ | Register new doctor |
| `POST` | `patient/send-otp/` | ❌ | Send/generate OTP |
| `POST` | `patient/verify-otp/` | ❌ | Verify OTP → JWT |
| `POST` | `patient/register/` | ✅ | Register patient (by doctor) |
| `GET` | `user/me/` | ✅ | Current user info |
| `GET` | `doctor/patients/` | ✅ | Doctor's patient list |

### Prescriptions — `/api/prescriptions/`

| Method | Endpoint | Auth | Description |
|--------|----------|:---:|-------------|
| `POST` | `upload/` | ✅ | Upload image → OCR processing |
| `GET` | `<id>/` | ✅ | Single prescription detail |
| `GET` | `patient/<id>/` | ✅ | All prescriptions for a patient |
| `GET` | `doctor/all/` | ✅ | All prescriptions by logged-in doctor |
| `GET` | `awareness/<disease_type>/` | ✅ | Awareness messages for a disease |
| `POST` | `awareness/create/` | ✅ | Create awareness message |

### Predictions — `/api/predictions/`

| Method | Endpoint | Auth | Description |
|--------|----------|:---:|-------------|
| `POST` | `predict/` | ✅ | Predict from uploaded prescription |
| `POST` | `predict-smart/` | ✅ | Predict from direct feature values |
| `GET` | `patient/<id>/` | ✅ | Prediction history for a patient |
| `GET` | `high-risk/` | ✅ | All high-risk predictions |
| `GET` | `stats/` | ✅ | Aggregate risk distribution |
| `GET` | `features/` | ✅ | Selected features + all 13 importances |
| `POST` | `models/train/` | ✅ | Trigger full model retraining |
| `GET` | `models/all/` | ✅ | List all trained model records |

#### `POST /api/predictions/predict-smart/` — Request Body
```json
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
```

#### `GET /api/predictions/stats/` — Response
```json
{
    "success": true,
    "data": {
        "total_predictions": 120,
        "low_risk_count": 45,
        "medium_risk_count": 50,
        "high_risk_count": 25,
        "low_risk_percentage": 37.5,
        "medium_risk_percentage": 41.7,
        "high_risk_percentage": 20.8
    }
}
```

#### `GET /api/predictions/features/` — Response
```json
{
    "success": true,
    "data": {
        "selected_features": ["income_normalized", "dosage_normalized", ...],
        "total_features_available": 13,
        "features_selected": 7,
        "importances_ranked": [
            {"feature": "income_normalized", "importance": 0.1423, "selected": true},
            ...
        ]
    }
}
```

### Notifications — `/api/notifications/`

| Method | Endpoint | Auth | Description |
|--------|----------|:---:|-------------|
| `POST` | `prescription/<id>/schedule/` | ✅ | Schedule reminders for all medicines |
| `GET` | `patient/<id>/reminders/` | ✅ | All reminders for a patient |
| `GET` | `statistics/` | ✅ | SMS stats (total/sent/failed/scheduled) |
| `POST` | `test-sms/` | ✅ | Send a test SMS |

---

## Flutter Frontend

### Screens

| Screen | File | Role |
|--------|------|------|
| Splash | `splash_screen.dart` | Checks stored token → routes to doctor or patient login |
| Doctor Login | `doctor_login_screen.dart` | Username + password form |
| Doctor Dashboard | `doctor_dashboard.dart` | Patient list, prescriptions, stats |
| Smart Prediction | `smart_prediction_screen.dart` | 7-feature form + animated result card |
| Feature Importance | `feature_importance_screen.dart` | Ranked bar chart of all 13 features |
| Patient Login | `patient_login_screen.dart` | Phone number + OTP verification |
| Patient Dashboard | `patient_dashboard.dart` | Prescriptions, reminders, awareness messages |

### Smart Prediction Screen — Input Controls

| Feature | Widget |
|---------|--------|
| Age | `TextFormField` (validated 1–120) |
| Income Level | `Slider` 0.0–1.0 with live value badge |
| Dosage Level | `Slider` 0.0–1.0 with live value badge |
| Previous Adherence | Two-button toggle (Good History / Poor History) |
| Number of Other Diseases | `TextFormField` (validated 0–20) |
| Condition Severity | Three-way segmented selector (Mild / Moderate / Severe) |
| Healthcare Access | Three-way segmented selector (Poor / Average / Good) |

Result card shows: risk badge (green/orange/red), confidence %, adherence score progress bar, per-class probability bars, full recommendation text, model name, and "Saved to history" indicator.

### Feature Importance Screen

Horizontal bar chart of all 13 features ranked by importance. Selected features highlighted in blue with `SELECTED` badge; non-selected in grey. Includes a "What Does This Mean?" card with key insights about the strongest predictors.

### API Service (`services/api_service.dart`)

Singleton HTTP client with:
- JWT stored in `SharedPreferences` (key: `auth_token`)
- Auto-injects `Authorization: Bearer <token>` on all authenticated requests
- `uploadFile()` for multipart prescription image upload
- On `kIsWeb`: replaces `localhost` with `127.0.0.1` to avoid CORS
- Typed exceptions: 401 → "Session expired", 403 → "Authentication failed"

### Base URL Config

```dart
// lib/config/constants.dart
static const String baseUrl = 'http://192.168.1.10/api';

// Android Emulator:  http://10.0.2.2:8000/api
// Physical Device:   http://<LAN_IP>:8000/api
// Flutter Web:       http://127.0.0.1:8000/api
```

---

## Configuration & Settings

### Key `settings.py` Values

```python
TIME_ZONE = 'Asia/Kolkata'

MEDIA_URL  = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'        # prescription images stored here

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
}

CORS_ALLOW_ALL_ORIGINS = True          # development only — restrict in production

TESSERACT_CMD = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

USE_TWILIO          = True
TWILIO_ACCOUNT_SID  = 'AC...'
TWILIO_AUTH_TOKEN   = '...'
TWILIO_PHONE_NUMBER = '+1...'
```

> ⚠️ **Security notice:** Move `SECRET_KEY`, all Twilio credentials, and `DEBUG=False` to environment variables before any deployment. Never commit real credentials to version control.

---

## Getting Started

### Prerequisites

- Python 3.10+
- Flutter SDK 3.x
- Tesseract OCR on PATH
- (Optional) Twilio account for live SMS

### Backend Setup

```bash
# 1. Clone and navigate to backend
git clone https://github.com/mohammedsameer777/medication_adherence_app.git
cd medication_adherence_app/backend

# 2. Virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Migrate database
python manage.py makemigrations
python manage.py migrate

# 5. Create admin superuser
python manage.py createsuperuser

# 6. Train ML models (first run only — takes 2–5 minutes)
python manage.py shell
>>> from predictions.ml_service import predictor
>>> predictor.train_models()
>>> exit()

# 7. Start server
python manage.py runserver 0.0.0.0:8000
```

> After training, model files are saved to `backend/ml_models/`. On subsequent server starts, models are loaded from disk automatically.

### Flutter Setup

```bash
cd ../medication_app

flutter pub get

# Edit lib/config/constants.dart → set correct baseUrl for your environment

flutter run
```

### Tesseract Installation

| OS | Command |
|----|---------|
| Windows | Installer from https://github.com/UB-Mannheim/tesseract/wiki |
| Ubuntu/Debian | `sudo apt install tesseract-ocr` |
| macOS | `brew install tesseract` |

Verify: `tesseract --version`, then update `TESSERACT_CMD` in `settings.py`.

---

## Demo Credentials

| Role | Field | Value |
|------|-------|-------|
| Doctor | Username | `dr_john` |
| Doctor | Password | `password123` |
| Patient | Phone | `8765432109` |
| Patient | OTP | Displayed on screen in mock/demo mode |

---

## Known Issues & Fixes Applied

| Bug | Fix Applied |
|-----|-------------|
| `adherence_score` was always `1.0` for high-risk patients | `adherence_score = low_prob + 0.5 × medium_prob` |
| All doctors saw every patient (hardcoded `id=1`) | Doctor resolved from JWT `request.user` |
| Patient users created with `is_active=False` → 401 on all requests | `user.is_active = True` enforced on create and on every login |
| `Medicine.related_name` clashed with `AdherencePrediction` model | Renamed to `related_name='medicines'` |
| `AdherencePrediction.prescription` non-nullable blocked smart predictions | `null=True, blank=True` added |
| Twilio hardcoded in `__init__`, impossible to toggle without code change | `USE_TWILIO` flag read from `settings.py` at runtime |
| Flutter Web CORS error when using `localhost` | `ApiService` replaces `localhost` with `127.0.0.1` when `kIsWeb` is true |

---

## License

Developed for academic purposes. Not intended for production clinical use without appropriate clinical validation and regulatory compliance.
