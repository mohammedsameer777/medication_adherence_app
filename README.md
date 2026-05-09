💊 Medication Adherence App
Full-Stack AI-Powered Prescription & Adherence Monitoring System
Django REST API  •  Flutter App  •  XGBoost ML  •  Gemini Vision OCR  •  Twilio SMS
Django 4	Flutter	XGBoost	Gemini AI	Twilio SMS	Redis+Celery


📖 Project Overview
The Medication Adherence App is a full-stack healthcare system designed to help doctors manage patients, upload prescriptions, and predict medication adherence risk using machine learning. It consists of a Django REST Framework backend and a Flutter mobile/web frontend.
The core idea: when a doctor uploads a prescription image, the system uses AI (Google Gemini 1.5 Flash) to read and extract medicine details automatically. Then it runs an XGBoost model to predict whether the patient is at low, medium, or high risk of not adhering to their medication schedule — and sends automated SMS reminders via Twilio.

🏗️ System Architecture
High-Level Flow
Doctor Login → Upload Prescription Image → Gemini Vision OCR → Extract Medicines → Run XGBoost Prediction → SMS Reminders via Twilio → Patient Dashboard

Layer	Technology	Purpose
Frontend	Flutter (Dart) + Provider	Doctor & Patient mobile/web UI
Backend API	Django REST Framework + JWT	REST API, auth, business logic
Database	SQLite (dev) / PostgreSQL (prod)	All data storage
OCR Engine	Google Gemini 1.5 Flash (primary)	Reads handwritten + printed prescriptions
OCR Fallback 1	OCR.space API (free, 25k/month)	Text-based OCR fallback
OCR Fallback 2	Tesseract + OpenCV (local)	Fully offline fallback
ML Model	XGBoost (89.42% accuracy)	Adherence risk prediction
Task Queue	Celery + Redis	Scheduled SMS reminders
SMS Service	Twilio	Medication reminder SMS
Auth	JWT (SimpleJWT) + OTP (SMS)	Doctor JWT, Patient OTP login

📦 Backend Django Apps
The backend is organized into 4 Django apps:
1. accounts
•	Models:  Doctor registration and JWT-based login
•	 Patient management linked to a doctor
•	 OTP-based authentication for patients (6-digit, 10-minute expiry)
•	 Phone number-based patient identity
2. prescriptions
•	 Upload prescription image (JPG/PNG)
•	 Process with PrescriptionOCR class (3-tier fallback)
•	 Store extracted medicines, dosage, frequency, disease, patient name, age
•	 AwarenessMessage model for disease-specific health tips
3. predictions
•	 Full ML pipeline: data loading, feature engineering, RFE, SMOTE, training, saving
•	 AdherencePrediction model stores every prediction with risk level and recommendation
•	 MLModel registry tracks all trained models and their metrics
•	 Two prediction endpoints: prescription-based and smart form-based
4. notifications
•	 SMSReminder model stores scheduled reminder records
•	 Celery Beat polls every 60 seconds for due reminders
•	 Twilio SMS sent at scheduled time (mock mode available for dev)

🔍 OCR Pipeline — How Prescription Reading Works
The OCR is implemented in backend/prescriptions/ocr_service.py as the PrescriptionOCR class. It has a strict 3-tier fallback strategy with zero recursion:
Tier 1 — Google Gemini 1.5 Flash (Primary)
The prescription image is base64-encoded and sent directly to the Gemini Vision API with a structured prompt. Gemini returns a JSON object with patient name, age, disease, treatment duration, and a list of medicines (name, dosage, frequency, duration_days).
Why Gemini? It handles handwritten prescriptions, mixed handwritten/printed text, and Tamil/regional scripts better than traditional OCR. Free tier allows 1,500 requests/day.
Gemini Prompt Strategy
You are a medical prescription parser.
Return ONLY a JSON object with:
  patient_name, age, disease,
  treatment_duration_days,
  medicines: [ { name, dosage, frequency, duration_days } ]
Rules:
  - T. or Tab. prefix = tablet
  - frequency = "N times daily"
  - Return [] if no medicines found
Tier 2 — OCR.space API (Text OCR Fallback)
If Gemini is unavailable or rate-limited, the image is sent to OCR.space (free API, 25,000 requests/month). This returns plain text. The system then applies regex extractors to parse patient name, age, disease, duration, and medicines from the raw text.
Tier 3 — Tesseract + OpenCV (Offline Fallback)
If both cloud APIs are unavailable, Tesseract runs locally. OpenCV pre-processes the image: grayscale conversion → adaptive thresholding → fast non-local means denoising → Tesseract PSM 6 OCR. Regex extractors then parse the output same as Tier 2.
Regex Extraction (Tiers 2 & 3)
After raw text is obtained, these extractors run:
•	Patient name: matches 'Patient Name:', 'Name:', 'Patient:' patterns
•	Age: matches 'Age:', 'N years', 'N/M' (age/gender) patterns
•	Disease: matches 'Diagnosis:', 'Dx:', 'C/O:', common disease keywords
•	Duration: matches 'for N days', 'Duration: N days'
•	Medicines: matches Tab./T./Syp./Cap. prefixes, timing patterns (1-0-1), OD/BD/TDS/QID abbreviations, tabular layouts

🤖 Machine Learning — Adherence Prediction
Algorithm: XGBoost (Forced as Primary Model)
Algorithm: XGBoost Classifier (eXtreme Gradient Boosting). Trained alongside Random Forest, Gradient Boosting, MLP Neural Network, LightGBM, KNN, and Logistic Regression — but XGBoost is always selected as the deployed model regardless of leaderboard position.
Dataset
Property	Value
Source	Kaggle: patient_adherence_dataset.csv
Base records	~5,000 real patient records
Augmentation	3x duplication with 3% Gaussian noise on numeric columns
Final training size	~15,000 records
Target classes	Low risk, Medium risk, High risk
Random seed	42 (reproducible)
Feature Engineering (13 → 34 Features)
Starting from 13 original input features, 21 additional features are engineered:
Original 13 Input Features
Feature	Description
Age	Patient age (integer)
gender_encoded	0=Female, 1=Male
medication_type_encoded	Encoded medication category
dosage_normalized	Dosage normalized 0–1
Previous_Adherence	0=non-adherent history, 1=adherent
education_encoded	Education level (0–2)
income_normalized	Income normalized 0–1
social_support_encoded	Social support level (0–2)
severity_encoded	Disease severity (0=low, 1=med, 2=high)
Comorbidities_Count	Number of additional conditions
healthcare_access_encoded	Access to healthcare (0–2)
mental_health_encoded	Mental health status (0–2)
Insurance_Coverage	0=no insurance, 1=insured

21 Engineered Features
Engineered Feature	Formula / Logic
vulnerability_score	(Age/100)*0.4 + (severity/2)*0.6
support_gap	(1-social_support/2) * (comorbidities/max)
adherence_capacity	income*0.35 + education*0.35 + access*0.30
stress_index	(1-mental/max) * (1-income)
dosage_burden	dosage_normalized * (Age/100)
history_support	Previous_Adherence * (social_support/2)
comorbidity_severity	Comorbidities_Count * (severity+1)
risk_composite	Weighted sum of non-adherence risk factors
adherence_risk_score	Weighted sum of protective factors
barrier_index	Weighted sum of adherence barriers
protective_score	Weighted combination of protective factors
combined_risk	risk_composite * (1 - protective_score)
net_risk_score	barrier_index - protective_score
income_x_adherence	income_normalized * Previous_Adherence
severity_x_comorbid	severity * comorbidities (interaction)
access_x_support	healthcare_access * social_support
dosage_x_severity	dosage * severity (interaction)
age_x_comorbid	(Age/100) * comorbidities
mental_x_income	mental_health * income
prev_adh_x_severity	Previous_Adherence * (1 - severity/2)
insurance_x_income	Insurance_Coverage * income_normalized
Feature Selection — RFE (Recursive Feature Elimination)
After engineering 34 features, RFE with a Random Forest estimator (300 trees) is used to select the top 20 most informative features. This reduces overfitting and improves generalization.
•	All 34 features are first scored using a Random Forest for importance ranking
•	RFE then iteratively removes the least important features until 20 remain
•	The selected 20 features are saved to ml_models/feature_names.pkl
•	RFE selector itself is saved to ml_models/rfe_selector.pkl for inference
Class Imbalance Handling — SMOTE
SMOTE (Synthetic Minority Oversampling TEchnique) from imbalanced-learn is applied after RFE to balance the three risk classes before training. It generates synthetic samples for minority classes rather than simply duplicating them.
Preprocessing
•	StandardScaler normalizes all 20 selected features before training and inference
•	Scaler saved to ml_models/scaler.pkl — same scaler used at prediction time
•	80/20 train-test split with stratification on the risk classes
•	5-fold Stratified Cross-Validation for F1 score evaluation
XGBoost Hyperparameters
XGBoost Configuration
n_estimators    = 500
learning_rate   = 0.05
max_depth       = 6
subsample       = 0.8
colsample_bytree= 0.8
reg_alpha       = 0.1   (L1 regularization)
reg_lambda      = 1.0   (L2 regularization)
min_child_weight= 5
eval_metric     = mlogloss
random_state    = 42
Model Performance
Model	Accuracy	Precision	Recall	F1	CV F1
XGBoost 🏆	89.42%	~89%	~89%	~89%	~89%
LightGBM	~88%	~88%	~88%	~88%	~88%
Random Forest	~86%	~86%	~86%	~86%	~86%
Gradient Boosting	~85%	~85%	~85%	~85%	~85%
MLP Neural Net	~83%	~83%	~83%	~83%	~83%
KNN	~78%	~78%	~78%	~78%	~78%
Logistic Regression	~72%	~72%	~72%	~72%	~72%
Prediction Output
Given 13 input features, the model outputs:
•	risk_level: 'low', 'medium', or 'high'
•	adherence_score: float 0–1 (computed from class probabilities)
•	adherence_percentage: score * 100
•	confidence: probability of predicted class
•	risk_probabilities: {low: 0.xx, medium: 0.xx, high: 0.xx}
•	recommendation: actionable text advice based on risk level + age + medicines

📱 SMS Notification System
Medication reminders are sent via Twilio SMS. The system uses Celery Beat for scheduled task execution.
Flow
•	Doctor uploads prescription → medicines are saved with dosage and frequency
•	SMSReminder records are created with a scheduled_time for each dose
•	Celery Beat task (send_due_reminders) runs every 60 seconds
•	Task queries reminders with status='scheduled' and scheduled_time within last 2 minutes
•	Twilio client sends SMS with medicine name, dosage, frequency, and timing
•	Reminder status updated to 'sent' with Twilio SID stored for tracking
Mock Mode
Setting USE_TWILIO=False in settings runs in mock mode — SMS content is printed to console. Useful for development without Twilio credentials.

📲 Flutter Frontend
Architecture
The Flutter app uses the Provider package for state management and a singleton ApiService for all HTTP calls. JWT tokens are stored in SharedPreferences.
Screens
Screen	Description
SplashScreen	App entry — checks stored token, routes to login
DoctorLoginScreen	Email + password JWT login for doctors
DoctorDashboard	Patient list, prescription upload, summary stats
PatientMonitoringScreen	Per-patient adherence history, risk timeline
SmartPredictionScreen	Manual 13-feature form → ML prediction result
FeatureImportanceScreen	Bar chart of all 34 feature importances (fl_chart)
PatientLoginScreen	Phone number + OTP-based login for patients
PatientDashboard	Patient's own prescriptions, medicines, reminders
Key Flutter Packages
Package	Use
http / dio	REST API calls
provider	State management
shared_preferences	JWT token storage
image_picker	Prescription photo selection from camera/gallery
fl_chart	Feature importance bar charts
flutter_spinkit	Loading animations
intl	Date and time formatting
permission_handler	Camera and storage permissions

🔗 REST API Endpoints
Auth — /api/auth/
Method	Endpoint	Description
POST	/doctor/login/	Doctor login, returns JWT access+refresh tokens
POST	/doctor/register/	Register new doctor account
POST	/patient/send-otp/	Send 6-digit OTP to patient phone (via Twilio)
POST	/patient/verify-otp/	Verify OTP and return JWT token
POST	/patient/register/	Register patient linked to doctor
GET	/user/me/	Get current authenticated user details
GET	/doctor/patients/	List all patients under logged-in doctor
GET	/patient/<id>/monitoring/	Full monitoring data for a patient
DELETE	/patient/<id>/delete/	Delete a patient record

Prescriptions — /api/prescriptions/
Method	Endpoint	Description
POST	/upload/	Upload prescription image → triggers OCR pipeline
GET	/<id>/	Get single prescription + extracted medicines
GET	/patient/<id>/	All prescriptions for a patient
GET	/doctor/	All prescriptions uploaded by logged-in doctor
GET	/awareness/<disease>/	Awareness messages for a disease type
POST	/awareness/create/	Create new disease awareness message

Predictions — /api/predictions/
Method	Endpoint	Description
POST	/predict/	Predict adherence from uploaded prescription data
POST	/predict-smart/	Predict from manual 13-feature form input
GET	/patient/<id>/	All predictions for a patient
GET	/high-risk/	All high-risk patient predictions
GET	/stats/	Prediction statistics (count by risk level)
GET	/features/	Selected features + importance rankings
GET	/models/all/	List all trained ML models
POST	/models/train/	Trigger full model retraining pipeline

🔐 Authentication
Doctor Authentication (JWT)
•	Doctors register with email, password, phone, specialization, hospital, registration number
•	Login returns a JWT access token (7-day expiry) and refresh token (30-day expiry)
•	All API calls include Authorization: Bearer <token> header
•	Algorithm: HS256, signed with Django SECRET_KEY
Patient Authentication (OTP)
•	Patients have no password — they authenticate with their phone number + SMS OTP
•	OTP is 6 digits, expires in 10 minutes
•	After OTP verification, a JWT token is returned for subsequent API calls
•	OTP is sent via Twilio SMS to the patient's registered phone

📁 Project Structure
Directory Layout
medication_adherence_app/
├── backend/                    # Django REST API
│   ├── accounts/               # Doctor, Patient, OTP models & auth
│   ├── prescriptions/          # Prescription upload, OCR, medicine models
│   │   └── ocr_service.py      # 3-tier OCR: Gemini → OCR.space → Tesseract
│   ├── predictions/            # ML pipeline, XGBoost, adherence prediction
│   │   ├── ml_service.py       # Training, feature engineering, prediction
│   │   └── data_loader.py      # Kaggle dataset loader
│   ├── notifications/          # Celery tasks, Twilio SMS, reminders
│   ├── ml_models/              # Saved model files (.pkl)
│   ├── datasets/               # patient_adherence_dataset.csv
│   └── medication_backend/     # Django settings, URLs, Celery config
├── medication_app/             # Flutter frontend
│   ├── lib/
│   │   ├── screens/doctor/     # Doctor UI screens
│   │   ├── screens/patient/    # Patient UI screens
│   │   └── services/           # ApiService singleton
│   └── pubspec.yaml
└── requirements.txt

⚙️ Setup & Installation
Prerequisites
•	Python 3.10+
•	Flutter SDK 3.0+
•	Redis (for Celery)
•	Tesseract OCR (optional, local fallback)
•	Twilio account (optional, mock mode available)
•	Google Gemini API key (free at aistudio.google.com)
Backend Setup
Step 1 — Install dependencies
cd backend
pip install -r requirements.txt
Step 2 — Database migrations
python manage.py makemigrations
python manage.py migrate
Step 3 — Configure settings.py
GEMINI_API_KEY    = 'your-gemini-key'        # aistudio.google.com (free)
OCR_SPACE_API_KEY = 'your-ocrspace-key'      # ocr.space (25k/month free)
TWILIO_ACCOUNT_SID  = 'your-sid'
TWILIO_AUTH_TOKEN   = 'your-token'
TWILIO_PHONE_NUMBER = '+1xxxxxxxxxx'
USE_TWILIO = True   # False for mock mode
Step 4 — Train the ML model
POST /api/predictions/models/train/
# Or call predictor.train_models() in Django shell
# This runs: data load → feature engineering → RFE
#            → SMOTE → StandardScaler → XGBoost → save
Step 5 — Start services
# Terminal 1 — Django server
python manage.py runserver

# Terminal 2 — Redis
redis-server

# Terminal 3 — Celery worker
celery -A medication_backend worker --loglevel=info

# Terminal 4 — Celery Beat (scheduled tasks)
celery -A medication_backend beat --loglevel=info
Flutter Setup
Flutter steps
cd medication_app
flutter pub get

# Update API base URL in lib/config/constants.dart
# Default: http://localhost:8000

flutter run

🗂️ Saved ML Model Files
File	Contents
xgboost_model.pkl	Trained XGBoost classifier (primary)
scaler.pkl	StandardScaler fitted on training data
rfe_selector.pkl	RFE selector (20 of 34 features)
feature_names.pkl	List of the 20 selected feature names
label_encoders.pkl	LabelEncoder for risk classes
feature_importances.pkl	All 34 feature importance scores
all_engineered_cols.pkl	Ordered list of all 34 engineered columns
dataset_info.pkl	Dataset statistics for display

🔑 Key Design Decisions
•	Gemini Vision over traditional OCR: Handwritten prescriptions (common in India) are poorly read by Tesseract. Gemini handles both handwritten and printed text and returns structured JSON directly, removing the need for fragile regex on raw text.
•	XGBoost forced as primary: XGBoost consistently outperforms on tabular medical data. Rather than dynamically selecting the best model each time, it is hardcoded as the deployed model for predictability.
•	SMOTE for imbalanced classes: Medical adherence datasets are naturally imbalanced (fewer high-risk patients). SMOTE generates synthetic samples rather than just upsampling to avoid overfitting on duplicates.
•	Feature engineering doubles signal: 13 raw features alone cannot capture non-linear relationships like 'elderly patient with high severity and no social support'. Composite features like risk_composite and protective_score encode these relationships explicitly.
•	OTP-based patient auth: Patients, especially elderly, often don't remember passwords. Phone-based OTP is simpler and already tied to the SMS reminder infrastructure.
•	Celery + Redis for SMS: Sending SMS at upload time would create sync delays. Celery defers it to background workers, and Beat polls every 60 seconds to send reminders at the right scheduled time.

🛠️ Complete Tech Stack
Category	Technology	Version / Notes
Backend Framework	Django + DRF	REST Framework + SimpleJWT
ML - Primary	XGBoost	89.42% accuracy, 500 trees
ML - Comparison	LightGBM, Random Forest, GBM, MLP, KNN, LR	All trained, XGBoost deployed
Feature Selection	RFE (sklearn)	20 of 34 features
Imbalance	SMOTE (imbalanced-learn)	Synthetic minority oversampling
Scaling	StandardScaler (sklearn)	Fitted on training data
OCR Primary	Google Gemini 1.5 Flash	Free tier, handles handwriting
OCR Fallback 1	OCR.space API	25k requests/month free
OCR Fallback 2	Tesseract + OpenCV	Local, fully offline
Task Queue	Celery + Redis	Beat polls every 60 seconds
SMS	Twilio REST API	India phone support (+91)
Auth	JWT (SimpleJWT) + OTP	Doctor JWT, Patient OTP
Database	SQLite (dev)	Easily switchable to PostgreSQL
Frontend	Flutter (Dart)	Runs on Android, iOS, Web
State Mgmt	Provider	Singleton ApiService pattern
Charts	fl_chart	Feature importance visualization
Timezone	Asia/Kolkata (IST)	All server timestamps

Built with Django · Flutter · XGBoost · Gemini AI · Twilio · Redis
