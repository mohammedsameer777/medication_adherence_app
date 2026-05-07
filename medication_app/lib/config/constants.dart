// lib/config/constants.dart

class AppConstants {
  // ── Production URL (Render) ────────────────────────────────────────────────
  static const String baseUrl = 'https://medication-adherence-app.onrender.com/api';

  // ── Auth endpoints ─────────────────────────────────────────────────────────
  static const String loginDoctor    = '/auth/doctor/login/';
  static const String registerDoctor = '/auth/doctor/register/';
  static const String sendOTP        = '/auth/patient/send-otp/';
  static const String verifyOTP      = '/auth/patient/verify-otp/';
  static const String getCurrentUser = '/auth/user/me/';

  // ── Doctor endpoints ───────────────────────────────────────────────────────
  static const String getDoctorPatients = '/auth/doctor/patients/';
  static const String registerPatient   = '/auth/patient/register/';

  // ── Prescription endpoints ─────────────────────────────────────────────────
  static const String uploadPrescription      = '/prescriptions/upload/';
  static const String getPatientPrescriptions = '/prescriptions/patient/';

  // ── Prediction endpoints ───────────────────────────────────────────────────
  static const String predictAdherence      = '/predictions/predict/';
  static const String getPatientPredictions = '/predictions/patient/';
  static const String getHighRiskPatients   = '/predictions/high-risk/';
  static const String getPredictionStats    = '/predictions/stats/';

  // ── Notification endpoints ─────────────────────────────────────────────────
  static const String scheduleReminders   = '/notifications/prescription/';
  static const String getPatientReminders = '/notifications/patient/';

  // ── SharedPreferences keys ─────────────────────────────────────────────────
  static const String keyToken    = 'auth_token';
  static const String keyUserType = 'user_type';
  static const String keyUserId   = 'user_id';
  static const String keyUserData = 'user_data';
}