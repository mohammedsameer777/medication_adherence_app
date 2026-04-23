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

  String get _baseUrl {
    if (kIsWeb) {
      return AppConstants.baseUrl.replaceFirst('localhost', '127.0.0.1');
    }
    return AppConstants.baseUrl;
  }

  Future<Map<String, String>> _getHeaders({bool includeAuth = true}) async {
    Map<String, String> headers = {'Content-Type': 'application/json'};
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

  Future<Map<String, dynamic>> get(String endpoint) async {
    try {
      final headers = await _getHeaders();
      final url     = '$_baseUrl$endpoint';
      print('📡 GET $url');
      final response = await http.get(Uri.parse(url), headers: headers);
      print('📥 Response status: ${response.statusCode}');
      return _handleResponse(response);
    } catch (e) {
      print('❌ GET Error: $e');
      throw Exception('Network error: $e');
    }
  }

  Future<Map<String, dynamic>> post(
    String endpoint,
    Map<String, dynamic> data, {
    bool includeAuth = true,
  }) async {
    try {
      final headers = await _getHeaders(includeAuth: includeAuth);
      final url     = '$_baseUrl$endpoint';
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
      throw Exception('Network error: $e');
    }
  }

  Future<Map<String, dynamic>> delete(String endpoint) async {
    try {
      final headers = await _getHeaders();
      final url     = '$_baseUrl$endpoint';
      print('📡 DELETE $url');
      final response = await http.delete(Uri.parse(url), headers: headers);
      print('📥 Response status: ${response.statusCode}');
      if (response.statusCode == 204) {
        return {'success': true, 'message': 'Deleted successfully'};
      }
      return _handleResponse(response);
    } catch (e) {
      print('❌ DELETE Error: $e');
      throw Exception('Network error: $e');
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
      var   request = http.MultipartRequest('POST', Uri.parse(url));
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
      var streamedResponse = await request.send();
      var response         = await http.Response.fromStream(streamedResponse);
      return _handleResponse(response);
    } catch (e) {
      throw Exception('Upload error: $e');
    }
  }

  Map<String, dynamic> _handleResponse(http.Response response) {
    print('Response code: ${response.statusCode}');
    print('Response body: ${response.body}');
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return json.decode(response.body);
    } else if (response.statusCode == 401) {
      throw Exception('Session expired. Please login again.');
    } else if (response.statusCode == 403) {
      throw Exception('Authentication failed. Please login again.');
    } else {
      try {
        final error = json.decode(response.body);
        throw Exception(
            error['message'] ?? error['detail'] ?? 'Request failed');
      } catch (_) {
        throw Exception(
            'Request failed with status ${response.statusCode}');
      }
    }
  }

  // ── Auth APIs ─────────────────────────────────────────────────────────────

  Future<Map<String, dynamic>> loginDoctor(
      String username, String password) async {
    final response = await post(
      AppConstants.loginDoctor,
      {'username': username, 'password': password},
      includeAuth: false,
    );
    if (response['success'] == true && response['data'] != null) {
      final token = response['data']['tokens']['access'];
      await setToken(token);
    }
    return response;
  }

  Future<Map<String, dynamic>> sendOTP(String phoneNumber) async {
    return await post(AppConstants.sendOTP, {'phone_number': phoneNumber},
        includeAuth: false);
  }

  Future<Map<String, dynamic>> verifyOTP(
      String phoneNumber, String otpCode) async {
    final response = await post(
      AppConstants.verifyOTP,
      {'phone_number': phoneNumber, 'otp_code': otpCode},
      includeAuth: false,
    );
    if (response['success'] == true && response['data'] != null) {
      final token = response['data']['tokens']['access'];
      await setToken(token);
    }
    return response;
  }

  Future<Map<String, dynamic>> getCurrentUser() async {
    return await get(AppConstants.getCurrentUser);
  }

  // ── Doctor APIs ───────────────────────────────────────────────────────────

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

  // ── Prescription APIs ─────────────────────────────────────────────────────

  Future<Map<String, dynamic>> uploadPrescription(
      File image, int patientId, int doctorId) async {
    return await uploadFile(
      AppConstants.uploadPrescription,
      image,
      additionalData: {'patient': patientId, 'doctor': doctorId},
    );
  }

  Future<Map<String, dynamic>> getPatientPrescriptions(int patientId) async {
    return await get('${AppConstants.getPatientPrescriptions}$patientId/');
  }

  // ── Prediction APIs ───────────────────────────────────────────────────────

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

  // ── Notification APIs ─────────────────────────────────────────────────────

  Future<Map<String, dynamic>> scheduleReminders(int prescriptionId) async {
    return await post(
        '${AppConstants.scheduleReminders}$prescriptionId/schedule/', {});
  }

  Future<Map<String, dynamic>> getPatientReminders(int patientId) async {
    return await get(
        '${AppConstants.getPatientReminders}$patientId/reminders/?filter=today');
  }

  Future<Map<String, dynamic>> getPatientRemindersFiltered(
      int patientId, String filter) async {
    return await get(
        '${AppConstants.getPatientReminders}$patientId/reminders/?filter=$filter');
  }

  Future<Map<String, dynamic>> markReminderTaken(int reminderId) async {
    return await post('/notifications/reminder/$reminderId/taken/', {});
  }

  // ── Patient Monitoring API (NEW) ──────────────────────────────────────────

  Future<Map<String, dynamic>> getPatientMonitoring(int patientId) async {
    return await get('/auth/patient/$patientId/monitoring/');
  }
}