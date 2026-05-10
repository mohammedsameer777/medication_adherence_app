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
  List<dynamic> _patients = [];
  Map<String, dynamic>? _stats;
  bool _isLoading = true;
  int _selectedIndex = 0;

  Map<String, dynamic>? get _doctorData =>
      Provider.of<AuthProvider>(context, listen: false).userData;
  int? get _doctorId => _doctorData?['id'];
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
      final stats = await _apiService.getPredictionStats();
      setState(() {
        _patients = patients['data']['patients'] ?? [];
        _stats = stats['data'];
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
    final formKey = GlobalKey<FormState>();
    final nameController = TextEditingController();
    final phoneController = TextEditingController();
    final ageController = TextEditingController();
    final diseaseController = TextEditingController();
    String selectedGender = 'male';

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
                  if (age == null || age < 1 || age > 120)
                    return 'Enter valid age (1-120)';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: selectedGender,
                decoration: const InputDecoration(
                    labelText: 'Gender', prefixIcon: Icon(Icons.wc)),
                items: const [
                  DropdownMenuItem(value: 'male', child: Text('Male')),
                  DropdownMenuItem(value: 'female', child: Text('Female')),
                  DropdownMenuItem(value: 'other', child: Text('Other')),
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
              child: const Text('Cancel')),
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
        'full_name': name,
        'phone_number': phone,
        'age': age,
        'gender': gender,
        'disease_type': disease,
        'doctor': _doctorId,
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
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
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
        final data = result['data'];
        final prescription = data['prescription'];
        final prescriptionId = prescription['id'];
        final extractedMedicinesList =
            data['extracted_medicines_list'] as String? ?? '';

        int remindersScheduled = data['reminders_scheduled'] ?? 0;
        try {
          final reminderResult =
              await _apiService.scheduleReminders(prescriptionId);
          if (reminderResult['success'] == true) {
            final extra =
                reminderResult['data']['total_reminders'] ?? 0;
            if (extra > remindersScheduled) remindersScheduled = extra;
          }
        } catch (_) {}

        if (!mounted) return;
        Navigator.pop(context);

        // ── Show extracted medicines for doctor to REVIEW & EDIT ──────────
        final medicines = prescription['medicines'] as List<dynamic>? ?? [];
        showDialog(
          context: context,
          builder: (_) => _UploadSuccessDialog(
            prescription: prescription,
            remindersScheduled: remindersScheduled,
            extractedMedicinesList: extractedMedicinesList,
            prescriptionId: prescriptionId,
            apiService: _apiService,
            extractedMedicines: medicines,
          ),
        );
        _loadData();
      } else {
        if (!mounted) return;
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
            content: Text('Upload failed. Please try again.'),
            backgroundColor: Colors.red));
      }
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red));
    }
  }

  // ── Manual Prescription Entry ─────────────────────────────────────────────
  Future<void> _showManualPrescriptionDialog(int patientId) async {
    final formKey = GlobalKey<FormState>();
    final diseaseController = TextEditingController();
    final durationController = TextEditingController(text: '30');
    final List<Map<String, dynamic>> medicineControllers = [];

    // Add first medicine row by default
    medicineControllers.add({
      'name': TextEditingController(),
      'dosage': TextEditingController(text: '1 tablet'),
      'frequency': TextEditingController(text: '1 times daily'),
      'duration': TextEditingController(text: '30'),
      'timing': 'Morning',  // string state, not controller
    });

    await showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: const Row(children: [
            Icon(Icons.edit_note, color: Colors.blue),
            SizedBox(width: 8),
            Text('Manual Prescription'),
          ]),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: Form(
                key: formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextFormField(
                      controller: diseaseController,
                      decoration: const InputDecoration(
                          labelText: 'Disease / Diagnosis',
                          prefixIcon: Icon(Icons.medical_services)),
                    ),
                    const SizedBox(height: 8),
                    TextFormField(
                      controller: durationController,
                      decoration: const InputDecoration(
                          labelText: 'Treatment Duration (days)',
                          prefixIcon: Icon(Icons.calendar_today)),
                      keyboardType: TextInputType.number,
                    ),
                    const SizedBox(height: 16),
                    const Text('Medicines',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 15)),
                    const SizedBox(height: 8),
                    ...medicineControllers.asMap().entries.map((entry) {
                      final i = entry.key;
                      final c = entry.value;
                      return _MedicineEntryCard(
                        index: i,
                        controllers: c,
                        showRemove: medicineControllers.length > 1,
                        onRemove: () => setDialogState(
                            () => medicineControllers.removeAt(i)),
                        onTimingChanged: (val) =>
                            setDialogState(() => c['timing'] = val),
                      );
                    }),
                    TextButton.icon(
                      onPressed: () {
                        setDialogState(() {
                          medicineControllers.add({
                            'name': TextEditingController(),
                            'dosage': TextEditingController(text: '1 tablet'),
                            'frequency': TextEditingController(
                                text: '1 times daily'),
                            'duration': TextEditingController(
                                text: durationController.text),
                            'timing': 'Morning',
                          });
                        });
                      },
                      icon: const Icon(Icons.add),
                      label: const Text('Add Medicine'),
                    ),
                  ],
                ),
              ),
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel')),
            ElevatedButton(
              onPressed: () async {
                if (!formKey.currentState!.validate()) return;
                Navigator.pop(ctx);
                await _submitManualPrescription(
                  patientId: patientId,
                  disease: diseaseController.text.trim(),
                  durationDays:
                      int.tryParse(durationController.text) ?? 30,
                  medicineControllers: medicineControllers,
                );
              },
              style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.blue),
              child: const Text('Save Prescription',
                  style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _submitManualPrescription({
    required int patientId,
    required String disease,
    required int durationDays,
    required List<Map<String, dynamic>> medicineControllers,
  }) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );
    try {
      if (_doctorId == null) throw Exception('Session expired.');
      final medicines = medicineControllers.map((c) {
        return {
          'name': (c['name'] as TextEditingController).text.trim(),
          'dosage': (c['dosage'] as TextEditingController).text.trim().isEmpty
              ? '1 tablet'
              : (c['dosage'] as TextEditingController).text.trim(),
          'frequency':
              (c['frequency'] as TextEditingController).text.trim().isEmpty
                  ? '1 times daily'
                  : (c['frequency'] as TextEditingController).text.trim(),
          'duration_days':
              int.tryParse((c['duration'] as TextEditingController).text) ??
                  durationDays,
          'timing': c['timing'] as String? ?? 'Morning',
        };
      }).toList();

      final result = await _apiService.createManualPrescription({
        'patient': patientId,
        'doctor': _doctorId,
        'disease': disease,
        'treatment_duration_days': durationDays,
        'medicines': medicines,
      });

      if (!mounted) return;
      Navigator.pop(context);

      if (result['success'] == true) {
        final data = result['data'];
        final list = data['medicines_list'] as String? ?? '';
        showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: const Row(children: [
              Icon(Icons.check_circle, color: Colors.green),
              SizedBox(width: 8),
              Text('Prescription Saved'),
            ]),
            content: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                      '${data['total_medicines']} medicine(s) saved.',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                  Text(
                      '${data['reminders_scheduled']} reminder(s) scheduled.',
                      style: const TextStyle(color: Colors.green)),
                  if (list.isNotEmpty) ...[
                    const Divider(),
                    const Text('Medicines:',
                        style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text(list, style: const TextStyle(fontSize: 13)),
                  ],
                ],
              ),
            ),
            actions: [
              ElevatedButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Done')),
            ],
          ),
        );
        _loadData();
      } else {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(result['message'] ?? 'Failed'),
            backgroundColor: Colors.red));
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
              child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () => Navigator.pop(context, true),
            child:
                const Text('Delete', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );

    if (confirmed != true) return;

    final removedPatient = patient;
    final removedIndex =
        _patients.indexWhere((p) => p['id'] == patient['id']);
    setState(() => _patients.removeWhere((p) => p['id'] == patient['id']));

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
          backgroundColor: Colors.green));
      _loadData();
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      setState(() {
        if (removedIndex >= 0 && removedIndex <= _patients.length) {
          _patients.insert(removedIndex, removedPatient);
        } else {
          _patients.add(removedPatient);
        }
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Error deleting patient: $e'),
          backgroundColor: Colors.red));
    }
  }

  void _openSmartPrediction(Map<String, dynamic> patient) => Navigator.push(
      context,
      MaterialPageRoute(
          builder: (_) => SmartPredictionScreen(patient: patient)));

  void _openFeatureImportance() => Navigator.push(context,
      MaterialPageRoute(builder: (_) => const FeatureImportanceScreen()));

  void _openMonitoring(Map<String, dynamic> patient) => Navigator.push(
      context,
      MaterialPageRoute(
          builder: (_) => PatientMonitoringScreen(patient: patient)));

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
      body:
          _selectedIndex == 0 ? _buildPatientsTab() : _buildStatsTab(),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() => _selectedIndex = index);
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
            onUpload: () => _uploadPrescriptionOnly(patient['id']),
            onManual: () => _showManualPrescriptionDialog(patient['id']),
            onSmartPredict: () => _openSmartPrediction(patient),
            onDelete: () => _deletePatient(patient),
            onMonitor: () => _openMonitoring(patient),
          );
        },
      ),
    );
  }

  Widget _buildStatsTab() {
    if (_isLoading || _stats == null)
      return const Center(child: CircularProgressIndicator());
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
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
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_doctorName,
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold)),
                    Text(
                      'ID: $_doctorId  |  ${_doctorData?['specialization'] ?? ''}',
                      style: const TextStyle(
                          color: Colors.white70, fontSize: 12),
                    ),
                    Text(_doctorData?['hospital_name'] ?? '',
                        style: const TextStyle(
                            color: Colors.white70, fontSize: 12)),
                  ]),
            ),
          ]),
        ),
        const SizedBox(height: 16),
        GestureDetector(
          onTap: _openFeatureImportance,
          child: Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [
                Colors.purple.shade700,
                Colors.purple.shade400
              ]),
              borderRadius: BorderRadius.circular(16),
            ),
            child: const Row(children: [
              Icon(Icons.bar_chart, color: Colors.white, size: 32),
              SizedBox(width: 12),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('View Feature Importances',
                          style: TextStyle(
                              color: Colors.white,
                              fontSize: 16,
                              fontWeight: FontWeight.bold)),
                      Text('See which patient factors drive predictions',
                          style: TextStyle(
                              color: Colors.white70, fontSize: 12)),
                    ]),
              ),
              Icon(Icons.arrow_forward_ios,
                  color: Colors.white70, size: 16),
            ]),
          ),
        ),
        const SizedBox(height: 16),
        _StatCard(
            title: 'My Patients',
            value: _patients.length.toString(),
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
            subtitle:
                '${(_stats!['high_risk_percentage'] as num).toStringAsFixed(1)}%',
            icon: Icons.warning,
            color: Colors.red),
        const SizedBox(height: 12),
        _StatCard(
            title: 'Medium Risk',
            value: _stats!['medium_risk_count'].toString(),
            subtitle:
                '${(_stats!['medium_risk_percentage'] as num).toStringAsFixed(1)}%',
            icon: Icons.info,
            color: Colors.orange),
        const SizedBox(height: 12),
        _StatCard(
            title: 'Low Risk',
            value: _stats!['low_risk_count'].toString(),
            subtitle:
                '${(_stats!['low_risk_percentage'] as num).toStringAsFixed(1)}%',
            icon: Icons.check_circle,
            color: Colors.green),
      ]),
    );
  }
}

// ── Medicine Entry Card (used in manual prescription) ────────────────────────

class _MedicineEntryCard extends StatelessWidget {
  final int index;
  final Map<String, dynamic> controllers;
  final bool showRemove;
  final VoidCallback onRemove;
  final ValueChanged<String> onTimingChanged;

  const _MedicineEntryCard({
    required this.index,
    required this.controllers,
    required this.showRemove,
    required this.onRemove,
    required this.onTimingChanged,
  });

  static const timingOptions = [
    {'label': '🌅 Morning',           'sub': '8:00 AM',        'value': 'Morning'},
    {'label': '☀️ Afternoon',          'sub': '2:00 PM',        'value': 'Afternoon'},
    {'label': '🌙 Night',              'sub': '8:00 PM',        'value': 'Night'},
    {'label': '🌅🌙 Morn & Night',     'sub': '8AM & 8PM',      'value': 'Morning & Night'},
    {'label': '🌅☀️🌙 3× Daily',       'sub': '8AM,2PM,8PM',   'value': 'Morning, Afternoon & Night'},
  ];

  @override
  Widget build(BuildContext context) {
    final selectedTiming = controllers['timing'] as String? ?? 'Morning';
    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      color: Colors.blue.shade50,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Text('Medicine ${index + 1}',
                style: const TextStyle(fontWeight: FontWeight.bold)),
            const Spacer(),
            if (showRemove)
              IconButton(
                icon: const Icon(Icons.remove_circle,
                    color: Colors.red, size: 20),
                onPressed: onRemove,
              ),
          ]),
          TextFormField(
            controller: controllers['name'] as TextEditingController,
            decoration: const InputDecoration(
                labelText: 'Medicine Name', isDense: true),
            validator: (v) => v?.isEmpty ?? true ? 'Required' : null,
          ),
          const SizedBox(height: 6),
          Row(children: [
            Expanded(
              child: TextFormField(
                controller: controllers['dosage'] as TextEditingController,
                decoration:
                    const InputDecoration(labelText: 'Dosage', isDense: true),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: TextFormField(
                controller: controllers['duration'] as TextEditingController,
                decoration:
                    const InputDecoration(labelText: 'Days', isDense: true),
                keyboardType: TextInputType.number,
              ),
            ),
          ]),
          const SizedBox(height: 6),
          TextFormField(
            controller: controllers['frequency'] as TextEditingController,
            decoration: const InputDecoration(
                labelText: 'Frequency (e.g. 2 times daily)',
                isDense: true),
          ),
          const SizedBox(height: 10),
          // ── Timing Selector ─────────────────────────────────────────────
          Container(
            padding:
                const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: Colors.blue.shade200),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(Icons.alarm, size: 15, color: Colors.blue.shade700),
                  const SizedBox(width: 5),
                  Text(
                    'Reminder Timing',
                    style: TextStyle(
                        fontSize: 12,
                        color: Colors.blue.shade700,
                        fontWeight: FontWeight.w600),
                  ),
                ]),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: timingOptions.map((opt) {
                    final isSelected = selectedTiming == opt['value'];
                    return GestureDetector(
                      onTap: () => onTimingChanged(opt['value']!),
                      child: AnimatedContainer(
                        duration: const Duration(milliseconds: 150),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: isSelected
                              ? Colors.blue.shade600
                              : Colors.grey.shade100,
                          borderRadius: BorderRadius.circular(20),
                          border: Border.all(
                            color: isSelected
                                ? Colors.blue.shade800
                                : Colors.grey.shade300,
                            width: isSelected ? 1.5 : 1,
                          ),
                          boxShadow: isSelected
                              ? [
                                  BoxShadow(
                                      color: Colors.blue.shade200,
                                      blurRadius: 4,
                                      offset: const Offset(0, 2))
                                ]
                              : [],
                        ),
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              opt['label']!,
                              style: TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w600,
                                color: isSelected
                                    ? Colors.white
                                    : Colors.grey.shade700,
                              ),
                            ),
                            Text(
                              opt['sub']!,
                              style: TextStyle(
                                fontSize: 10,
                                color: isSelected
                                    ? Colors.white70
                                    : Colors.grey.shade500,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ]),
      ),
    );
  }
}

// ── Upload Success Dialog ─────────────────────────────────────────────────────

class _UploadSuccessDialog extends StatefulWidget {
  final Map<String, dynamic> prescription;
  final int remindersScheduled;
  final String extractedMedicinesList;
  final int prescriptionId;
  final ApiService apiService;
  final List<dynamic> extractedMedicines;

  const _UploadSuccessDialog({
    required this.prescription,
    required this.remindersScheduled,
    required this.extractedMedicinesList,
    required this.prescriptionId,
    required this.apiService,
    required this.extractedMedicines,
  });

  @override
  State<_UploadSuccessDialog> createState() => _UploadSuccessDialogState();
}

class _UploadSuccessDialogState extends State<_UploadSuccessDialog> {
  // Editable medicine list — doctor can fix timing before finalising
  late List<Map<String, dynamic>> _editableMedicines;
  bool _editMode = false;

  static const timingOptions = [
    {'label': '🌅 Morning',       'sub': '8:00 AM',      'value': 'Morning'},
    {'label': '☀️ Afternoon',      'sub': '2:00 PM',      'value': 'Afternoon'},
    {'label': '🌙 Night',          'sub': '8:00 PM',      'value': 'Night'},
    {'label': '🌅🌙 Morn & Night', 'sub': '8AM & 8PM',    'value': 'Morning & Night'},
    {'label': '🌅☀️🌙 3× Daily',   'sub': '8AM,2PM,8PM', 'value': 'Morning, Afternoon & Night'},
  ];

  @override
  void initState() {
    super.initState();
    // Build editable list from extracted medicines
    _editableMedicines = widget.extractedMedicines.map((m) {
      final map = m as Map<String, dynamic>;
      return {
        'id': map['id'],
        'nameCtrl': TextEditingController(
            text: map['medicine_name'] ?? ''),
        'dosageCtrl': TextEditingController(text: map['dosage'] ?? ''),
        'frequencyCtrl':
            TextEditingController(text: map['frequency'] ?? ''),
        'timing': map['timing'] ?? 'Morning',
      };
    }).toList();
  }

  Future<void> _saveEdits() async {
    // Build updated medicines payload
    final medicines = _editableMedicines.map((m) => {
          'name': (m['nameCtrl'] as TextEditingController).text.trim(),
          'dosage':
              (m['dosageCtrl'] as TextEditingController).text.trim(),
          'frequency':
              (m['frequencyCtrl'] as TextEditingController).text.trim(),
          'timing': m['timing'] as String,
          'duration_days': widget.prescription['treatment_duration_days'] ?? 7,
        }).toList();

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(child: CircularProgressIndicator()),
    );

    try {
      // Delete old reminders and reschedule with updated medicines
      // We use add-medicines endpoint to reschedule
      final result = await widget.apiService
          .addMedicinesToPrescription(widget.prescriptionId, medicines);

      if (!mounted) return;
      Navigator.pop(context); // close loader
      Navigator.pop(context); // close this dialog

      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(result['success'] == true
            ? '✅ Medicines updated & reminders rescheduled!'
            : 'Failed to update medicines'),
        backgroundColor: result['success'] == true ? Colors.green : Colors.red,
      ));
    } catch (e) {
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('Error: $e'), backgroundColor: Colors.red));
    }
  }

  @override
  Widget build(BuildContext context) {
    final medicines = widget.prescription['medicines'] as List<dynamic>? ?? [];

    return AlertDialog(
      title: Row(children: [
        const Icon(Icons.check_circle, color: Colors.green),
        const SizedBox(width: 8),
        const Text('Prescription Uploaded'),
        const Spacer(),
        if (medicines.isNotEmpty)
          TextButton.icon(
            icon: Icon(_editMode ? Icons.close : Icons.edit,
                size: 16,
                color: _editMode ? Colors.red : Colors.blue),
            label: Text(
              _editMode ? 'Cancel' : 'Edit',
              style: TextStyle(
                  color: _editMode ? Colors.red : Colors.blue,
                  fontSize: 12),
            ),
            onPressed: () => setState(() => _editMode = !_editMode),
          ),
      ]),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('OCR extraction complete.',
                style: TextStyle(color: Colors.grey, fontSize: 13)),
            const Divider(height: 20),
            if (widget.prescription['patient_name_extracted'] != null)
              _infoRow(Icons.person, 'Patient',
                  widget.prescription['patient_name_extracted']),
            if (widget.prescription['disease_extracted'] != null)
              _infoRow(Icons.medical_services, 'Disease',
                  widget.prescription['disease_extracted']),
            _infoRow(Icons.medication, 'Medicines',
                '${widget.prescription['total_medicines'] ?? 0} found'),
            _infoRow(Icons.calendar_today, 'Duration',
                '${widget.prescription['treatment_duration_days'] ?? 7} days'),

            // ── Extracted / Editable medicines ────────────────────────────
            if (medicines.isNotEmpty) ...[
              const Divider(height: 16),
              Row(children: [
                const Text('Extracted Medicines:',
                    style: TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 13)),
                const Spacer(),
                if (_editMode)
                  const Text('⚠️ Edit & fix timing',
                      style:
                          TextStyle(fontSize: 11, color: Colors.orange)),
              ]),
              const SizedBox(height: 6),

              if (!_editMode)
                // ── Read-only view ────────────────────────────────────────
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(10),
                  decoration: BoxDecoration(
                    color: Colors.green.shade50,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: Colors.green.shade200),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: medicines.asMap().entries.map((e) {
                      final i = e.key + 1;
                      final m = e.value as Map<String, dynamic>;
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              '$i. ${m['medicine_name']} — ${m['dosage']} — ${m['frequency']}',
                              style: const TextStyle(fontSize: 12),
                            ),
                            Row(children: [
                              const SizedBox(width: 14),
                              Icon(Icons.alarm,
                                  size: 12,
                                  color: Colors.blue.shade400),
                              const SizedBox(width: 3),
                              Text(
                                m['timing'] ?? 'Not set',
                                style: TextStyle(
                                    fontSize: 11,
                                    color: Colors.blue.shade600,
                                    fontStyle: FontStyle.italic),
                              ),
                            ]),
                          ],
                        ),
                      );
                    }).toList(),
                  ),
                )
              else
                // ── Edit mode ─────────────────────────────────────────────
                StatefulBuilder(
                  builder: (ctx, setS) => Column(
                    children: _editableMedicines.asMap().entries.map((e) {
                      final i = e.key;
                      final m = e.value;
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        color: Colors.blue.shade50,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(8)),
                        child: Padding(
                          padding: const EdgeInsets.all(8),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Medicine ${i + 1}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold,
                                      fontSize: 12)),
                              const SizedBox(height: 4),
                              TextField(
                                controller: m['nameCtrl']
                                    as TextEditingController,
                                decoration: const InputDecoration(
                                    labelText: 'Name',
                                    isDense: true,
                                    contentPadding: EdgeInsets.symmetric(
                                        vertical: 6, horizontal: 8)),
                              ),
                              const SizedBox(height: 4),
                              Row(children: [
                                Expanded(
                                  child: TextField(
                                    controller: m['dosageCtrl']
                                        as TextEditingController,
                                    decoration: const InputDecoration(
                                        labelText: 'Dosage',
                                        isDense: true,
                                        contentPadding: EdgeInsets.symmetric(
                                            vertical: 6, horizontal: 8)),
                                  ),
                                ),
                                const SizedBox(width: 6),
                                Expanded(
                                  child: TextField(
                                    controller: m['frequencyCtrl']
                                        as TextEditingController,
                                    decoration: const InputDecoration(
                                        labelText: 'Frequency',
                                        isDense: true,
                                        contentPadding: EdgeInsets.symmetric(
                                            vertical: 6, horizontal: 8)),
                                  ),
                                ),
                              ]),
                              const SizedBox(height: 8),
                              // Timing chips
                              Text('Reminder Time:',
                                  style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.blue.shade700,
                                      fontWeight: FontWeight.w600)),
                              const SizedBox(height: 4),
                              Wrap(
                                spacing: 4,
                                runSpacing: 4,
                                children: timingOptions.map((opt) {
                                  final sel =
                                      m['timing'] == opt['value'];
                                  return GestureDetector(
                                    onTap: () => setS(() =>
                                        m['timing'] = opt['value']),
                                    child: Container(
                                      padding: const EdgeInsets.symmetric(
                                          horizontal: 8, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: sel
                                            ? Colors.blue.shade600
                                            : Colors.grey.shade100,
                                        borderRadius:
                                            BorderRadius.circular(14),
                                        border: Border.all(
                                          color: sel
                                              ? Colors.blue.shade800
                                              : Colors.grey.shade300,
                                        ),
                                      ),
                                      child: Column(
                                        mainAxisSize: MainAxisSize.min,
                                        children: [
                                          Text(opt['label']!,
                                              style: TextStyle(
                                                  fontSize: 10,
                                                  fontWeight:
                                                      FontWeight.w600,
                                                  color: sel
                                                      ? Colors.white
                                                      : Colors
                                                          .grey.shade700)),
                                          Text(opt['sub']!,
                                              style: TextStyle(
                                                  fontSize: 9,
                                                  color: sel
                                                      ? Colors.white70
                                                      : Colors
                                                          .grey.shade500)),
                                        ],
                                      ),
                                    ),
                                  );
                                }).toList(),
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
                  ),
                ),
            ] else ...[
              const Divider(height: 16),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.orange.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.orange.shade200),
                ),
                child: const Row(children: [
                  Icon(Icons.warning_amber, color: Colors.orange, size: 18),
                  SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'No medicines extracted. Please add them manually.',
                      style:
                          TextStyle(fontSize: 12, color: Colors.orange),
                    ),
                  ),
                ]),
              ),
            ],

            const SizedBox(height: 10),

            // ── Reminders status ──────────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: widget.remindersScheduled > 0
                    ? Colors.green.shade50
                    : Colors.orange.shade50,
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                    color: widget.remindersScheduled > 0
                        ? Colors.green.shade300
                        : Colors.orange.shade300),
              ),
              child: Row(children: [
                Icon(
                  widget.remindersScheduled > 0
                      ? Icons.notifications_active
                      : Icons.notifications_off,
                  color: widget.remindersScheduled > 0
                      ? Colors.green
                      : Colors.orange,
                  size: 18,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    widget.remindersScheduled > 0
                        ? '${widget.remindersScheduled} reminder(s) scheduled ✅'
                        : 'No reminders — add medicines first.',
                    style: TextStyle(
                        fontSize: 12,
                        color: widget.remindersScheduled > 0
                            ? Colors.green.shade700
                            : Colors.orange.shade700),
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
                  child: Text(
                      'Use "AI Predict" button to run adherence prediction.',
                      style:
                          TextStyle(fontSize: 12, color: Colors.blue)),
                ),
              ]),
            ),
          ],
        ),
      ),
      actions: [
        if (_editMode)
          ElevatedButton.icon(
            icon: const Icon(Icons.save, size: 16),
            label: const Text('Save & Reschedule'),
            style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                foregroundColor: Colors.white),
            onPressed: _saveEdits,
          )
        else ...[
          TextButton.icon(
            icon: const Icon(Icons.add_circle_outline,
                color: Colors.orange),
            label: const Text('Add Medicine',
                style: TextStyle(color: Colors.orange)),
            onPressed: () {
              Navigator.pop(context);
              _showAddMedicineDialog(
                  context, widget.prescriptionId, widget.apiService);
            },
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Done'),
          ),
        ],
      ],
    );
  }

  Widget _infoRow(IconData icon, String label, dynamic value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Icon(icon, size: 16, color: Colors.grey.shade600),
        const SizedBox(width: 8),
        Text('$label: ',
            style: const TextStyle(
                fontWeight: FontWeight.bold, fontSize: 13)),
        Expanded(
            child: Text('$value', style: const TextStyle(fontSize: 13))),
      ]),
    );
  }

  static void _showAddMedicineDialog(
      BuildContext context, int prescriptionId, ApiService apiService) {
    final List<Map<String, dynamic>> rows = [
      {
        'name': TextEditingController(),
        'dosage': TextEditingController(text: '1 tablet'),
        'frequency': TextEditingController(text: '1 times daily'),
        'duration': TextEditingController(text: '7'),
        'timing': 'Morning',
      }
    ];

    const timingOpts = [
      {'label': '🌅 Morning',       'sub': '8:00 AM',      'value': 'Morning'},
      {'label': '☀️ Afternoon',      'sub': '2:00 PM',      'value': 'Afternoon'},
      {'label': '🌙 Night',          'sub': '8:00 PM',      'value': 'Night'},
      {'label': '🌅🌙 Morn & Night', 'sub': '8AM & 8PM',    'value': 'Morning & Night'},
      {'label': '🌅☀️🌙 3× Daily',   'sub': '8AM,2PM,8PM', 'value': 'Morning, Afternoon & Night'},
    ];

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setS) => AlertDialog(
          title: const Row(children: [
            Icon(Icons.add_circle, color: Colors.orange),
            SizedBox(width: 8),
            Text('Add Missing Medicines'),
          ]),
          content: SizedBox(
            width: double.maxFinite,
            child: SingleChildScrollView(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  ...rows.asMap().entries.map((entry) {
                    final i = entry.key;
                    final c = entry.value;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 10),
                      color: Colors.orange.shade50,
                      child: Padding(
                        padding: const EdgeInsets.all(10),
                        child: Column(children: [
                          Row(children: [
                            Text('Medicine ${i + 1}',
                                style: const TextStyle(
                                    fontWeight: FontWeight.bold)),
                            const Spacer(),
                            if (rows.length > 1)
                              IconButton(
                                icon: const Icon(Icons.remove_circle,
                                    color: Colors.red, size: 20),
                                onPressed: () =>
                                    setS(() => rows.removeAt(i)),
                              ),
                          ]),
                          TextField(
                            controller:
                                c['name'] as TextEditingController,
                            decoration: const InputDecoration(
                                labelText: 'Medicine Name',
                                isDense: true),
                          ),
                          const SizedBox(height: 6),
                          Row(children: [
                            Expanded(
                              child: TextField(
                                controller:
                                    c['dosage'] as TextEditingController,
                                decoration: const InputDecoration(
                                    labelText: 'Dosage', isDense: true),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: TextField(
                                controller: c['duration']
                                    as TextEditingController,
                                decoration: const InputDecoration(
                                    labelText: 'Days', isDense: true),
                                keyboardType: TextInputType.number,
                              ),
                            ),
                          ]),
                          const SizedBox(height: 6),
                          TextField(
                            controller:
                                c['frequency'] as TextEditingController,
                            decoration: const InputDecoration(
                                labelText: 'Frequency', isDense: true),
                          ),
                          const SizedBox(height: 8),
                          // Timing chips
                          Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 8, vertical: 6),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(8),
                              border:
                                  Border.all(color: Colors.orange.shade200),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(children: [
                                  Icon(Icons.alarm,
                                      size: 13,
                                      color: Colors.orange.shade700),
                                  const SizedBox(width: 4),
                                  Text('Reminder Timing',
                                      style: TextStyle(
                                          fontSize: 11,
                                          color: Colors.orange.shade700,
                                          fontWeight: FontWeight.w600)),
                                ]),
                                const SizedBox(height: 6),
                                Wrap(
                                  spacing: 4,
                                  runSpacing: 4,
                                  children: timingOpts.map((opt) {
                                    final sel =
                                        c['timing'] == opt['value'];
                                    return GestureDetector(
                                      onTap: () => setS(
                                          () => c['timing'] = opt['value']),
                                      child: Container(
                                        padding: const EdgeInsets.symmetric(
                                            horizontal: 8, vertical: 4),
                                        decoration: BoxDecoration(
                                          color: sel
                                              ? Colors.orange.shade600
                                              : Colors.grey.shade100,
                                          borderRadius:
                                              BorderRadius.circular(14),
                                          border: Border.all(
                                              color: sel
                                                  ? Colors.orange.shade800
                                                  : Colors.grey.shade300),
                                        ),
                                        child: Column(
                                          mainAxisSize: MainAxisSize.min,
                                          children: [
                                            Text(opt['label']!,
                                                style: TextStyle(
                                                    fontSize: 10,
                                                    fontWeight:
                                                        FontWeight.w600,
                                                    color: sel
                                                        ? Colors.white
                                                        : Colors.grey
                                                            .shade700)),
                                            Text(opt['sub']!,
                                                style: TextStyle(
                                                    fontSize: 9,
                                                    color: sel
                                                        ? Colors.white70
                                                        : Colors.grey
                                                            .shade500)),
                                          ],
                                        ),
                                      ),
                                    );
                                  }).toList(),
                                ),
                              ],
                            ),
                          ),
                        ]),
                      ),
                    );
                  }),
                  TextButton.icon(
                    onPressed: () => setS(() => rows.add({
                          'name': TextEditingController(),
                          'dosage':
                              TextEditingController(text: '1 tablet'),
                          'frequency': TextEditingController(
                              text: '1 times daily'),
                          'duration': TextEditingController(text: '7'),
                          'timing': 'Morning',
                        })),
                    icon: const Icon(Icons.add),
                    label: const Text('Add Another'),
                  ),
                ],
              ),
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel')),
            ElevatedButton(
              style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.orange),
              onPressed: () async {
                Navigator.pop(ctx);
                final medicines = rows
                    .where((c) => (c['name'] as TextEditingController)
                        .text
                        .trim()
                        .isNotEmpty)
                    .map((c) => {
                          'name': (c['name'] as TextEditingController)
                              .text
                              .trim(),
                          'dosage':
                              (c['dosage'] as TextEditingController)
                                          .text
                                          .trim()
                                          .isEmpty
                                  ? '1 tablet'
                                  : (c['dosage'] as TextEditingController)
                                      .text
                                      .trim(),
                          'frequency':
                              (c['frequency'] as TextEditingController)
                                          .text
                                          .trim()
                                          .isEmpty
                                  ? '1 times daily'
                                  : (c['frequency']
                                          as TextEditingController)
                                      .text
                                      .trim(),
                          'duration_days': int.tryParse(
                                  (c['duration'] as TextEditingController)
                                      .text) ??
                              7,
                          'timing': c['timing'] as String? ?? 'Morning',
                        })
                    .toList();
                if (medicines.isEmpty) return;
                try {
                  final result =
                      await apiService.addMedicinesToPrescription(
                          prescriptionId, medicines);
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                      content: Text(result['success'] == true
                          ? '${result['data']['medicines_added']} medicine(s) added & reminders updated!'
                          : 'Failed to add medicines'),
                      backgroundColor: result['success'] == true
                          ? Colors.green
                          : Colors.red,
                    ));
                  }
                } catch (e) {
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                        content: Text('Error: $e'),
                        backgroundColor: Colors.red));
                  }
                }
              },
              child: const Text('Save',
                  style: TextStyle(color: Colors.white)),
            ),
          ],
        ),
      ),
    );
  }
}

// ── Patient Card ──────────────────────────────────────────────────────────────

class _PatientCard extends StatelessWidget {
  final Map<String, dynamic> patient;
  final VoidCallback onUpload;
  final VoidCallback onManual;
  final VoidCallback onSmartPredict;
  final VoidCallback onDelete;
  final VoidCallback onMonitor;

  const _PatientCard({
    required this.patient,
    required this.onUpload,
    required this.onManual,
    required this.onSmartPredict,
    required this.onDelete,
    required this.onMonitor,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      shape:
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child:
            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
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
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(patient['full_name'] ?? '',
                        style: const TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 15)),
                    const SizedBox(height: 2),
                    Text(
                        'Age: ${patient['age']}  |  ${patient['gender'] ?? ''}',
                        style: TextStyle(
                            fontSize: 12, color: Colors.grey.shade600)),
                    Text(patient['disease_type'] ?? '',
                        style: TextStyle(
                            fontSize: 12, color: Colors.blue.shade700)),
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
                label:
                    const Text('Upload Rx', style: TextStyle(fontSize: 12)),
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
              child: OutlinedButton.icon(
                onPressed: onManual,
                icon: const Icon(Icons.edit_note, size: 15),
                label:
                    const Text('Manual Rx', style: TextStyle(fontSize: 12)),
                style: OutlinedButton.styleFrom(
                  foregroundColor: Colors.orange,
                  side: const BorderSide(color: Colors.orange),
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ),
          ]),
          const SizedBox(height: 6),

          Row(children: [
            Expanded(
              child: ElevatedButton.icon(
                onPressed: onMonitor,
                icon: const Icon(Icons.monitor_heart, size: 15),
                label:
                    const Text('Monitor', style: TextStyle(fontSize: 12)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.teal,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 9),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8)),
                ),
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: onSmartPredict,
                icon: const Icon(Icons.psychology, size: 15),
                label: const Text('AI Predict',
                    style: TextStyle(fontSize: 12)),
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
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title,
                      style: TextStyle(
                          fontSize: 14, color: Colors.grey.shade600)),
                  Text(value,
                      style: const TextStyle(
                          fontSize: 24, fontWeight: FontWeight.bold)),
                  if (subtitle != null)
                    Text(subtitle!,
                        style: TextStyle(
                            fontSize: 12, color: Colors.grey.shade600)),
                ]),
          ),
        ]),
      ),
    );
  }
}