import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../config/constants.dart';
import 'dart:convert';

class AuthProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  
  bool _isAuthenticated = false;
  String? _userType;
  Map<String, dynamic>? _userData;
  bool _isLoading = false;
  String? _error;
  
  bool get isAuthenticated => _isAuthenticated;
  String? get userType => _userType;
  Map<String, dynamic>? get userData => _userData;
  bool get isLoading => _isLoading;
  String? get error => _error;
  ApiService get apiService => _apiService; // Add this getter
  
  bool get isDoctor => _userType == 'doctor';
  bool get isPatient => _userType == 'patient';
  
  // Check if user is logged in
  Future<void> checkAuth() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(AppConstants.keyToken);
    
    if (token != null) {
      _isAuthenticated = true;
      _userType = prefs.getString(AppConstants.keyUserType);
      
      final userDataString = prefs.getString(AppConstants.keyUserData);
      if (userDataString != null) {
        _userData = json.decode(userDataString);
      }
      
      notifyListeners();
    }
  }
  
  // Doctor Login
  Future<bool> loginDoctor(String username, String password) async {
    _isLoading = true;
    _error = null;
    notifyListeners();
    
    try {
      final response = await _apiService.loginDoctor(username, password);
      
      if (response['success']) {
        final data = response['data'];
        final token = data['tokens']['access'];
        
        await _apiService.setToken(token);
        
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(AppConstants.keyToken, token);
        await prefs.setString(AppConstants.keyUserType, 'doctor');
        await prefs.setString(AppConstants.keyUserData, json.encode(data['doctor']));
        
        _isAuthenticated = true;
        _userType = 'doctor';
        _userData = data['doctor'];
        
        _isLoading = false;
        notifyListeners();
        return true;
      }
      
      _error = response['message'];
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }
  
  // Patient Send OTP
  Future<String?> sendPatientOTP(String phoneNumber) async {
    _isLoading = true;
    _error = null;
    notifyListeners();
    
    try {
      final response = await _apiService.sendOTP(phoneNumber);
      
      _isLoading = false;
      notifyListeners();
      
      if (response['success']) {
        // Return OTP code (in production, this would be sent via SMS)
        return response['data']['otp_code'];
      }
      
      _error = response['message'];
      return null;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return null;
    }
  }
  
  // Patient Verify OTP
  Future<bool> verifyPatientOTP(String phoneNumber, String otpCode) async {
    _isLoading = true;
    _error = null;
    notifyListeners();
    
    try {
      final response = await _apiService.verifyOTP(phoneNumber, otpCode);
      
      if (response['success']) {
        final data = response['data'];
        final token = data['tokens']['access'];
        
        await _apiService.setToken(token);
        
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(AppConstants.keyToken, token);
        await prefs.setString(AppConstants.keyUserType, 'patient');
        await prefs.setString(AppConstants.keyUserData, json.encode(data['patient']));
        
        _isAuthenticated = true;
        _userType = 'patient';
        _userData = data['patient'];
        
        _isLoading = false;
        notifyListeners();
        return true;
      }
      
      _error = response['message'];
      _isLoading = false;
      notifyListeners();
      return false;
    } catch (e) {
      _error = e.toString();
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }
  
  // Logout
  Future<void> logout() async {
    await _apiService.clearToken();
    
    _isAuthenticated = false;
    _userType = null;
    _userData = null;
    _error = null;
    
    notifyListeners();
  }
  
  // Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}