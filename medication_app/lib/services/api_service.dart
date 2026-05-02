import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import '../config/constants.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  String? _token;

  // FIX: removed redundant _baseUrl getter that duplicated platform logic.
  // AppConstants.baseUrl is already platform-aware (Android emulator / iOS /
  // web / desktop). Using it directly avoids the old bug where the emulator
  // still got the physical device IP.
  String get _baseUrl => AppConstants.baseUrl;

  // ── Token management ───────────────────────────────────────────────────────

  Future<Map<String, String>> _getHeaders({bool includeAuth = true}) async {
    final Map<String, String> headers = {'Content-Type': 'application/json'};
    if (includeAuth) {
      await getToken();
      if (_token != null) {
        headers['Authorization'] = 'Bearer $_token';
        print('🔑 Using token: ${_token!.substring(0, 20)}...');
      } else {
        print('⚠️ No token available!');
      }
    }
    return headers;
  }

  Future<void> setToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(AppConstants.keyToken, token);
    print('✅ Token saved: ${token.substring(0, 20)}...');
  }

  Future<String?> getToken() async {
    if (_token != null) return _token;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString(AppConstants.keyToken);
    if (_token != null) {
      print('🔄 Token loaded from storage: ${_token!.substring(0, 20)}...');
    } else {
      print('❌ No token in storage');
    }
    return _token;
  }

  Future<void> clearToken() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(AppConstants.keyToken);
    await prefs.remove(AppConstants.keyUserType);
    await prefs.remove(AppConstants.keyUserId);
    await prefs.remove(AppConstants.keyUserData);
    print('🗑️ Token cleared');
  }

  // ── HTTP verbs ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> get(String endpoint) async {
    try {
      final headers  = await _getHeaders();
      final url      = '$_baseUrl$endpoint';
      print('📡 GET $url');
      final response = await http.get(Uri.parse(url), headers: headers);
      print('📥 Response status: ${response.statusCode}');
      return _handleResponse(response);
    } catch (e) {
      print('❌ GET Error: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> post(
    String endpoint,
    Map<String, dynamic> data, {
    bool includeAuth = true,
  }) async {
    try {
      final headers  = await _getHeaders(includeAuth: includeAuth);
      final url      = '$_baseUrl$endpoint';
      print('📡 POST $url');
      print('📤 Data: ${json.encode(data)}');
      final response = await http.post(
        Uri.parse(url),
        headers: headers,
        body: json.encode(data),
      );
      print('📥 Response status: ${response.statusCode}');
      print('📥 Response body: ${response.body}');
      return _handleResponse(response);
    } catch (e) {
      print('❌ POST Error: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> delete(String endpoint) async {
    try {
      final headers  = await _getHeaders();
      final url      = '$_baseUrl$endpoint';
      print('📡 DELETE $url');
      final response = await http.delete(Uri.parse(url), headers: headers);
      print('📥 Response status: ${response.statusCode}');
      if (response.statusCode == 204) {
        return {'success': true, 'message': 'Deleted successfully'};
      }
      return _handleResponse(response);
    } catch (e) {
      print('❌ DELETE Error: $e');
      rethrow;
    }
  }

  Future<Map<String, dynamic>> uploadFile(
    String endpoint,
    File file, {
    Map<String, dynamic>? additionalData,
  }) async {
    try {
      await getToken();
      final url     = '$_baseUrl$endpoint';
      final request = http.MultipartRequest('POST', Uri.parse(url));
      if (_token != null) {
        request.headers['Authorization'] = 'Bearer $_token';
      }
      request.files.add(
        await http.MultipartFile.fromPath('prescription_image', file.path),
      );
      if (additionalData != null) {
        additionalData.forEach((key, value) {
          request.fields[key] = value.toString();
        });
      }
      final streamedResponse = await request.send();
      final response         = await http.Response.fromStream(streamedResponse);
      return _handleResponse(response);
    } catch (e) {
      print('❌ Upload Error: $e');
      rethrow;
    }
  }

  // FIX: _handleResponse no longer swallows the real Django error body.
  // The inner catch now re-throws the original exception instead of a
  // generic status-code message, so debug logs show the actual error.
  Map<String, dynamic> _handleResponse(http.Response response) {
    print('Response code: ${response.statusCode}');
    print('Response body: ${response.body}');

    if (response.statusCode >= 200 && response.statusCode < 300) {
      return json.decode(response.body) as Map<String, dynamic>;
    }

    // Try to parse a structured error from Django
    String errorMessage;
    try {
      final error = json.decode(response.body) as Map<String, dynamic>;
      errorMessage = (error['message'] ?? error['detail'] ?? '').toString();
      if (errorMessage.isEmpty) errorMessage = response.body;
    } catch (_) {
      // Body is not JSON — use raw body so we can see the real Django error
      errorMessage = response.body.isNotEmpty
          ? response.body
          : 'Request failed with status ${response.statusCode}';
    }

    if (response.statusCode == 401) {
      throw Exception('Session expired. Please login again.');
    }
    if (response.statusCode == 403) {
      throw Exception('Access denied: $errorMessage');
    }
    throw Exception(errorMessage);
  }

  // ── Auth APIs ──────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> loginDoctor(
      String username, String password) async {
    final response = await post(
      AppConstants.loginDoctor,
      {'username': username, 'password': password},
      includeAuth: false,
    );

    if (response['success'] == true && response['data'] != null) {
      final data   = response['data'] as Map<String, dynamic>;
      final token  = data['tokens']['access'] as String;
      final doctor = data['doctor'] as Map<String, dynamic>;

      await setToken(token);

      // FIX: save userId and userType so every screen can read them
      // from SharedPreferences without another API call.
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.keyUserType, 'doctor');
      await prefs.setString(
          AppConstants.keyUserId, doctor['id'].toString());
      await prefs.setString(
          AppConstants.keyUserData, json.encode(doctor));
    }
    return response;
  }

  Future<Map<String, dynamic>> sendOTP(String phoneNumber) async {
    return await post(
      AppConstants.sendOTP,
      {'phone_number': phoneNumber},
      includeAuth: false,
    );
  }

  Future<Map<String, dynamic>> verifyOTP(
      String phoneNumber, String otpCode) async {
    final response = await post(
      AppConstants.verifyOTP,
      {'phone_number': phoneNumber, 'otp_code': otpCode},
      includeAuth: false,
    );

    if (response['success'] == true && response['data'] != null) {
      final data    = response['data'] as Map<String, dynamic>;
      final token   = data['tokens']['access'] as String;
      final patient = data['patient'] as Map<String, dynamic>;

      await setToken(token);

      // FIX: save patient userId and userType — without this every screen
      // that reads keyUserId from SharedPreferences gets null and crashes.
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(AppConstants.keyUserType, 'patient');
      await prefs.setString(
          AppConstants.keyUserId, patient['id'].toString());
      await prefs.setString(
          AppConstants.keyUserData, json.encode(patient));
    }
    return response;
  }

  Future<Map<String, dynamic>> getCurrentUser() async {
    return await get(AppConstants.getCurrentUser);
  }

  // ── Doctor APIs ────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> getDoctorPatients() async {
    return await get(AppConstants.getDoctorPatients);
  }

  Future<Map<String, dynamic>> registerPatient(
      Map<String, dynamic> data) async {
    return await post(AppConstants.registerPatient, data);
  }

  Future<Map<String, dynamic>> deletePatient(int patientId) async {
    return await delete('/auth/patient/$patientId/delete/');
  }

  // ── Prescription APIs ──────────────────────────────────────────────────────

  /// Upload prescription image, then automatically:
  ///   1. Schedule SMS reminders (uses prescription_id from upload response)
  ///   2. Run adherence prediction
  ///
  /// FIX: previously upload succeeded but neither reminders nor prediction
  /// were ever triggered — the full pipeline now runs in one call.
  Future<Map<String, dynamic>> uploadPrescription(
      File image, int patientId, int doctorId) async {
    // Step 1 — upload image + OCR
    final uploadResponse = await uploadFile(
      AppConstants.uploadPrescription,
      image,
      additionalData: {'patient': patientId, 'doctor': doctorId},
    );

    if (uploadResponse['success'] != true) {
      return uploadResponse;
    }

    final prescriptionId =
        uploadResponse['data']?['prescription_id'] as int?;

    if (prescriptionId != null) {
      // Step 2 — schedule SMS reminders (non-fatal if it fails)
      try {
        await scheduleReminders(prescriptionId);
        print('📅 Reminders scheduled for prescription #$prescriptionId');
      } catch (e) {
        print('⚠️ scheduleReminders failed (non-fatal): $e');
      }

      // Step 3 — run adherence prediction (non-fatal if it fails)
      try {
        await predictAdherence(patientId, prescriptionId);
        print('🤖 Adherence prediction run for prescription #$prescriptionId');
      } catch (e) {
        print('⚠️ predictAdherence failed (non-fatal): $e');
      }
    }

    return uploadResponse;
  }

  Future<Map<String, dynamic>> getPatientPrescriptions(int patientId) async {
    return await get('${AppConstants.getPatientPrescriptions}$patientId/');
  }

  // ── Prediction APIs ────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> predictAdherence(
      int patientId, int prescriptionId) async {
    return await post(AppConstants.predictAdherence,
        {'patient_id': patientId, 'prescription_id': prescriptionId});
  }

  Future<Map<String, dynamic>> getPatientPredictions(int patientId) async {
    return await get('${AppConstants.getPatientPredictions}$patientId/');
  }

  Future<Map<String, dynamic>> getHighRiskPatients() async {
    return await get(AppConstants.getHighRiskPatients);
  }

  Future<Map<String, dynamic>> getPredictionStats() async {
    return await get(AppConstants.getPredictionStats);
  }

  Future<Map<String, dynamic>> getSelectedFeatures() async {
    return await get('/predictions/features/');
  }

  Future<Map<String, dynamic>> predictSmart(
      Map<String, dynamic> featureData) async {
    return await post('/predictions/predict-smart/', featureData);
  }

  // ── Notification APIs ──────────────────────────────────────────────────────

  Future<Map<String, dynamic>> scheduleReminders(int prescriptionId) async {
    return await post(
      '${AppConstants.scheduleReminders}$prescriptionId/schedule/',
      {},
    );
  }

  Future<Map<String, dynamic>> getPatientReminders(int patientId) async {
    return await get(
      '${AppConstants.getPatientReminders}$patientId/reminders/?filter=today',
    );
  }

  Future<Map<String, dynamic>> getPatientRemindersFiltered(
      int patientId, String filter) async {
    return await get(
      '${AppConstants.getPatientReminders}$patientId/reminders/?filter=$filter',
    );
  }

  Future<Map<String, dynamic>> markReminderTaken(int reminderId) async {
    return await post('/notifications/reminder/$reminderId/taken/', {});
  }

  // ── Patient Monitoring API ─────────────────────────────────────────────────

  Future<Map<String, dynamic>> getPatientMonitoring(int patientId) async {
    return await get('/auth/patient/$patientId/monitoring/');
  }
}