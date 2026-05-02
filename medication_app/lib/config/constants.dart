// lib/config/constants.dart

import 'dart:io' show Platform;
import 'package:flutter/foundation.dart' show kIsWeb;

class AppConstants {
  // ── Your PC's LAN IP ───────────────────────────────────────────────────────
  static const String _physicalDeviceIp = '192.168.1.13';

  static const int _port = 8000;

  // ── Set to false for physical device, true for emulator ───────────────────
  static const bool _useEmulator = false;

  // ── Base URL (platform-aware) ──────────────────────────────────────────────
  static String get baseUrl {
    if (kIsWeb) {
      return 'http://127.0.0.1:$_port/api';
    }
    if (Platform.isAndroid) {
      return _useEmulator
          ? 'http://10.0.2.2:$_port/api'
          : 'http://$_physicalDeviceIp:$_port/api';
    }
    if (Platform.isIOS) {
      return _useEmulator
          ? 'http://127.0.0.1:$_port/api'
          : 'http://$_physicalDeviceIp:$_port/api';
    }
    return 'http://127.0.0.1:$_port/api';
  }

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