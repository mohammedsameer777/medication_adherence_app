import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:io';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';
import 'smart_prediction_screen.dart';
import 'feature_importance_screen.dart';
import 'patient_monitoring_screen.dart';

class DoctorDashboard extends StatefulWidget {
  const DoctorDashboard({super.key});

  @override
  State<DoctorDashboard> createState() => _DoctorDashboardState();
}

class _DoctorDashboardState extends State<DoctorDashboard> {
  final ApiService _apiService = ApiService();
  List<dynamic> _patients      = [];
  Map<String, dynamic>? _stats;
  bool _isLoading              = true;
  int _selectedIndex           = 0;

  Map<String, dynamic>? get _doctorData =>
      Provider.of<AuthProvider>(context, listen: false).userData;

  int?   get _doctorId   => _doctorData?['id'];
  String get _doctorName => _doctorData?['full_name'] ?? 'Doctor';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final patients = await _apiService.getDoctorPatients();
      final stats    = await _apiService.getPredictionStats();
      setState(() {
        _patients  = patients['data']['patients'] ?? [];
        _stats     = stats['data'];
        _isLoading = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _showAddPatientDialog() async {
    final formKey           = GlobalKey<FormState>();
    final nameController    = TextEditingController();
    final phoneController   = TextEditingController();
    final ageController     = TextEditingController();
    final diseaseController = TextEditingController();
    String selectedGender   = 'male';

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Add New Patient'),
        content: SingleChildScrollView(
          child: Form(
            key: formKey,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              TextFormField(
                controller: nameController,
                decoration: const InputDecoration(
                    labelText: 'Full Name', prefixIcon: Icon(Icons.person)),
                validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: phoneController,
                decoration: const InputDecoration(
                    labelText: 'Phone Number', prefixIcon: Icon(Icons.phone)),
                keyboardType: TextInputType.phone,
                maxLength: 10,
                validator: (v) => v?.length != 10 ? 'Enter 10 digits' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: ageController,
                decoration: const InputDecoration(
                    labelText: 'Age', prefixIcon: Icon(Icons.cake)),
                keyboardType: TextInputType.number,
                validator: (v) {
                  if (v?.isEmpty ?? true) return 'Required';
                  final age = int.tryParse(v!);
                  if (age == null || age < 1 || age > 120) return 'Enter valid age (1-120)';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: selectedGender,
                decoration: const InputDecoration(
                    labelText: 'Gender', prefixIcon: Icon(Icons.wc)),
                items: const [
                  DropdownMenuItem(value: 'male',   child: Text('Male')),
                  DropdownMenuItem(value: 'female', child: Text('Female')),
                  DropdownMenuItem(value: 'other',  child: Text('Other')),
                ],
                onChanged: (value) => selectedGender = value!,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: diseaseController,
                decoration: const InputDecoration(
                    labelText: 'Disease Type',
                    prefixIcon: Icon(Icons.medical_services)),
                validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
              ),
            ]),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () async {
              if (formKey.currentState!.validate()) {
                Navigator.pop(context);
                await _registerPatient(
                  nameController.text.trim(),
                  phoneController.text.trim(),
                  int.parse(ageController.text),
                  selectedGender,
                  diseaseController.text.trim(),
                );
              }
            },
            child: const Text('Add Patient'),
          ),
        ],
      ),
    );
  }

  Future<void> _registerPatient(String name, String phone, int age,
      String gender, String disease) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );
    try {
      if (_doctorId == null) throw Exception('Session expired. Login again.');
      await _apiService.registerPatient({
        'full_name':    name,
        'phone_number': phone,
        'age':          age,
        'gender':       gender,
        'disease_type': disease,
        'doctor':       _doctorId,
      });
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Patient added successfully!'),
          backgroundColor: Colors.green));
      _loadData();
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Error: $e'), backgroundColor: Colors.red));
    }
  }

  Future<void> _uploadPrescriptionOnly(int patientId) async {
    final ImagePicker picker = ImagePicker();
    final source = await showDialog<ImageSource>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Upload Prescription'),
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          ListTile(
            leading: const Icon(Icons.camera_alt),
            title: const Text('Take Photo'),
            onTap: () => Navigator.pop(context, ImageSource.camera),
          ),
          ListTile(
            leading: const Icon(Icons.photo_library),
            title: const Text('Choose from Gallery'),
            onTap: () => Navigator.pop(context, ImageSource.gallery),
          ),
        ]),
      ),
    );
    if (source == null) return;

    final XFile? image = await picker.pickImage(source: source);
    if (image == null) return;

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const AlertDialog(
        content: Column(mainAxisSize: MainAxisSize.min, children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Processing prescription...'),
          Text('Running OCR & scheduling reminders...'),
        ]),
      ),
    );

    try {
      if (_doctorId == null) throw Exception('Session expired.');

      final result = await _apiService.uploadPrescription(
          File(image.path), patientId, _doctorId!);

      if (!mounted) return;

      if (result['success'] == true) {
        final prescription   = result['data']['prescription'];
        final prescriptionId = prescription['id'];

        int remindersScheduled = 0;
        try {
          final reminderResult = await _apiService.scheduleReminders(prescriptionId);
          if (reminderResult['success'] == true) {
            remindersScheduled = reminderResult['data']['total_reminders'] ?? 0;
          }
        } catch (e) {
          print('⚠️ Reminder scheduling failed: $e');
        }

        if (!mounted) return;
        Navigator.pop(context);
        showDialog(
          context: context,
          builder: (_) => _UploadSuccessDialog(
            prescription: prescription,
            remindersScheduled: remindersScheduled,
          ),
        );
        _loadData();
      } else {
        if (!mounted) return;
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
              content: Text('Upload failed. Please try again.'),
              backgroundColor: Colors.red),
        );
      }
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    }
  }

  Future<void> _deletePatient(Map<String, dynamic> patient) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Row(children: [
          Icon(Icons.warning_amber_rounded, color: Colors.red),
          SizedBox(width: 8),
          Text('Delete Patient'),
        ]),
        content: Text(
          'Are you sure you want to delete "${patient['full_name']}"?\n\n'
          'This will permanently remove all their prescriptions, '
          'predictions and reminders.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    // ── OPTIMISTIC UPDATE ────────────────────────────────────────────────────
    // Remove the patient from the local list IMMEDIATELY so the Statistics tab
    // shows the correct count right away — no waiting for _loadData() to finish.
    final removedPatient = patient;
    final removedIndex   = _patients.indexWhere((p) => p['id'] == patient['id']);
    setState(() {
      _patients.removeWhere((p) => p['id'] == patient['id']);
    });

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      await _apiService.deletePatient(patient['id']);
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('${patient['full_name']} deleted successfully'),
        backgroundColor: Colors.green,
      ));
      // Refresh from server to sync any other data (stats, etc.)
      _loadData();
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);

      // ── ROLLBACK if API call failed ──────────────────────────────────────
      setState(() {
        if (removedIndex >= 0 && removedIndex <= _patients.length) {
          _patients.insert(removedIndex, removedPatient);
        } else {
          _patients.add(removedPatient);
        }
      });

      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Error deleting patient: $e'),
        backgroundColor: Colors.red,
      ));
    }
  }

  void _openSmartPrediction(Map<String, dynamic> patient) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => SmartPredictionScreen(patient: patient)),
    );
  }

  void _openFeatureImportance() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const FeatureImportanceScreen()),
    );
  }

  void _openMonitoring(Map<String, dynamic> patient) {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => PatientMonitoringScreen(patient: patient)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);

    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Doctor Dashboard',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          Text(_doctorName,
              style: const TextStyle(fontSize: 12, color: Colors.white70)),
        ]),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
            icon: const Icon(Icons.bar_chart),
            tooltip: 'Feature Importances',
            onPressed: _openFeatureImportance,
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () async {
              await authProvider.logout();
              if (!mounted) return;
              Navigator.of(context).pushReplacementNamed('/');
            },
          ),
        ],
      ),
      body: _selectedIndex == 0 ? _buildPatientsTab() : _buildStatsTab(),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() => _selectedIndex = index);
          // Refresh stats every time the Statistics tab is opened
          if (index == 1) _loadData();
        },
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.people), label: 'My Patients'),
          BottomNavigationBarItem(
              icon: Icon(Icons.bar_chart), label: 'Statistics'),
        ],
      ),
      floatingActionButton: _selectedIndex == 0
          ? FloatingActionButton.extended(
              onPressed: _showAddPatientDialog,
              icon: const Icon(Icons.person_add),
              label: const Text('Add Patient'),
              backgroundColor: Colors.blue,
            )
          : null,
    );
  }

  Widget _buildPatientsTab() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());

    if (_patients.isEmpty) {
      return Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.people_outline, size: 80, color: Colors.grey),
          const SizedBox(height: 16),
          Text('No patients yet, $_doctorName'),
          const SizedBox(height: 4),
          const Text('Add your first patient to get started',
              style: TextStyle(color: Colors.grey)),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            onPressed: _showAddPatientDialog,
            icon: const Icon(Icons.person_add),
            label: const Text('Add Your First Patient'),
          ),
        ]),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _patients.length,
        itemBuilder: (context, index) {
          final patient = _patients[index];
          return _PatientCard(
            patient: patient,
            onUpload:      () => _uploadPrescriptionOnly(patient['id']),
            onSmartPredict: () => _openSmartPrediction(patient),
            onDelete:      () => _deletePatient(patient),
            onMonitor:     () => _openMonitoring(patient),
          );
        },
      ),
    );
  }

  Widget _buildStatsTab() {
    if (_isLoading || _stats == null) {
      return const Center(child: CircularProgressIndicator());
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        // Doctor profile card
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
                colors: [Colors.blue.shade700, Colors.blue.shade500]),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(children: [
            CircleAvatar(
              backgroundColor: Colors.white,
              radius: 28,
              child: Text(
                _doctorName.isNotEmpty ? _doctorName[0].toUpperCase() : 'D',
                style: TextStyle(
                    color: Colors.blue.shade700,
                    fontSize: 22,
                    fontWeight: FontWeight.bold),
              ),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(_doctorName,
                    style: const TextStyle(
                        color: Colors.white, fontSize: 16,
                        fontWeight: FontWeight.bold)),
                Text(
                  'ID: $_doctorId  |  ${_doctorData?['specialization'] ?? ''}',
                  style: const TextStyle(color: Colors.white70, fontSize: 12),
                ),
                Text(_doctorData?['hospital_name'] ?? '',
                    style: const TextStyle(color: Colors.white70, fontSize: 12)),
              ]),
            ),
          ]),
        ),
        const SizedBox(height: 16),

        // Feature importances banner
        GestureDetector(
          onTap: _openFeatureImportance,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                  colors: [Colors.purple.shade700, Colors.purple.shade400]),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Row(children: [
              Icon(Icons.bar_chart, color: Colors.white, size: 32),
              SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('View Feature Importances',
                      style: TextStyle(
                          color: Colors.white, fontSize: 16,
                          fontWeight: FontWeight.bold)),
                  Text('See which patient factors drive predictions',
                      style: TextStyle(color: Colors.white70, fontSize: 12)),
                ]),
              ),
              Icon(Icons.arrow_forward_ios, color: Colors.white70, size: 16),
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // ── Stats cards — patient count uses live _patients.length ──────────
        _StatCard(
            title: 'My Patients',
            value: _patients.length.toString(),   // always live after optimistic delete
            icon: Icons.people,
            color: Colors.purple),
        const SizedBox(height: 12),
        _StatCard(
            title: 'Total Predictions',
            value: _stats!['total_predictions'].toString(),
            icon: Icons.analytics,
            color: Colors.blue),
        const SizedBox(height: 12),
        _StatCard(
            title: 'High Risk',
            value: _stats!['high_risk_count'].toString(),
            subtitle: '${(_stats!['high_risk_percentage'] as num).toStringAsFixed(1)}%',
            icon: Icons.warning,
            color: Colors.red),
        const SizedBox(height: 12),
        _StatCard(
            title: 'Medium Risk',
            value: _stats!['medium_risk_count'].toString(),
            subtitle: '${(_stats!['medium_risk_percentage'] as num).toStringAsFixed(1)}%',
            icon: Icons.info,
            color: Colors.orange),
        const SizedBox(height: 12),
        _StatCard(
            title: 'Low Risk',
            value: _stats!['low_risk_count'].toString(),
            subtitle: '${(_stats!['low_risk_percentage'] as num).toStringAsFixed(1)}%',
            icon: Icons.check_circle,
            color: Colors.green),
      ]),
    );
  }
}

// ── Upload Success Dialog ─────────────────────────────────────────────────────

class _UploadSuccessDialog extends StatelessWidget {
  final Map<String, dynamic> prescription;
  final int remindersScheduled;

  const _UploadSuccessDialog({
    required this.prescription,
    required this.remindersScheduled,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Row(children: [
        Icon(Icons.check_circle, color: Colors.green),
        SizedBox(width: 8),
        Text('Prescription Uploaded'),
      ]),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('OCR extraction complete.',
                style: TextStyle(color: Colors.grey, fontSize: 13)),
            const Divider(height: 20),
            if (prescription['patient_name_extracted'] != null)
              _infoRow(Icons.person, 'Patient', prescription['patient_name_extracted']),
            if (prescription['disease_extracted'] != null)
              _infoRow(Icons.medical_services, 'Disease', prescription['disease_extracted']),
            if (prescription['total_medicines'] != null)
              _infoRow(Icons.medication, 'Medicines',
                  '${prescription['total_medicines']} found'),
            if (prescription['treatment_duration_days'] != null)
              _infoRow(Icons.calendar_today, 'Duration',
                  '${prescription['treatment_duration_days']} days'),
            const Divider(height: 20),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: remindersScheduled > 0
                    ? Colors.green.shade50 : Colors.orange.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: remindersScheduled > 0
                      ? Colors.green.shade300 : Colors.orange.shade300),
              ),
              child: Row(children: [
                Icon(
                  remindersScheduled > 0
                      ? Icons.notifications_active : Icons.notifications_off,
                  color: remindersScheduled > 0 ? Colors.green : Colors.orange,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    remindersScheduled > 0
                        ? '$remindersScheduled reminder(s) scheduled ✅'
                        : 'No reminders scheduled (no medicines extracted).',
                    style: TextStyle(
                      fontSize: 12,
                      color: remindersScheduled > 0
                          ? Colors.green.shade700 : Colors.orange.shade700,
                    ),
                  ),
                ),
              ]),
            ),
            const SizedBox(height: 10),
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.blue.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: Colors.blue.shade200),
              ),
              child: const Row(children: [
                Icon(Icons.info_outline, color: Colors.blue, size: 18),
                SizedBox(width: 8),
                Expanded(
                  child: Text('Use "AI Predict" button to run adherence prediction.',
                      style: TextStyle(fontSize: 12, color: Colors.blue)),
                ),
              ]),
            ),
          ],
        ),
      ),
      actions: [
        ElevatedButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Done'),
        ),
      ],
    );
  }

  Widget _infoRow(IconData icon, String label, dynamic value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Icon(icon, size: 16, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Text('$label: ', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        Expanded(child: Text('$value', style: const TextStyle(fontSize: 13))),
      ]),
    );
  }
}

// ── Patient Card ──────────────────────────────────────────────────────────────

class _PatientCard extends StatelessWidget {
  final Map<String, dynamic> patient;
  final VoidCallback onUpload;
  final VoidCallback onSmartPredict;
  final VoidCallback onDelete;
  final VoidCallback onMonitor;

  const _PatientCard({
    required this.patient,
    required this.onUpload,
    required this.onSmartPredict,
    required this.onDelete,
    required this.onMonitor,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            CircleAvatar(
              backgroundColor: Colors.blue,
              child: Text(
                (patient['full_name'] as String? ?? 'P')[0].toUpperCase(),
                style: const TextStyle(color: Colors.white),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(patient['full_name'] ?? '',
                    style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                const SizedBox(height: 2),
                Text('Age: ${patient['age']}  |  ${patient['gender'] ?? ''}',
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                Text(patient['disease_type'] ?? '',
                    style: TextStyle(fontSize: 12, color: Colors.blue.shade700)),
              ]),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.red),
              tooltip: 'Delete Patient',
              onPressed: onDelete,
            ),
          ]),
          const SizedBox(height: 10),

          Row(children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: onUpload,
                icon: const Icon(Icons.upload_file, size: 15),
                label: const Text('Upload Rx', style: TextStyle(fontSize: 12)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.blue,
                  side: const BorderSide(color: Colors.blue),
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: onMonitor,
                icon: const Icon(Icons.monitor_heart, size: 15),
                label: const Text('Monitor', style: TextStyle(fontSize: 12)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.teal,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ),
          ]),
          const SizedBox(height: 6),

          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: onSmartPredict,
              icon: const Icon(Icons.psychology, size: 15),
              label: const Text('AI Predict', style: TextStyle(fontSize: 12)),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.deepPurple,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 9),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8)),
              ),
            ),
          ),
        ]),
      ),
    );
  }
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

class _StatCard extends StatelessWidget {
  final String title;
  final String value;
  final String? subtitle;
  final IconData icon;
  final Color color;

  const _StatCard({
    required this.title,
    required this.value,
    this.subtitle,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: color.withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: color, size: 32),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(title,
                  style: TextStyle(fontSize: 14, color: Colors.grey.shade600)),
              Text(value,
                  style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold)),
              if (subtitle != null)
                Text(subtitle!,
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
            ]),
          ),
        ]),
      ),
    );
  }
}