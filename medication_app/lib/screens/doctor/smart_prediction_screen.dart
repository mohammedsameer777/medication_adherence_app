import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class SmartPredictionScreen extends StatefulWidget {
  final Map<String, dynamic> patient;
  const SmartPredictionScreen({super.key, required this.patient});

  @override
  State<SmartPredictionScreen> createState() => _SmartPredictionScreenState();
}

class _SmartPredictionScreenState extends State<SmartPredictionScreen> {
  final ApiService _apiService = ApiService();
  final _formKey               = GlobalKey<FormState>();
  final _scrollController      = ScrollController();
  final _resultKey             = GlobalKey();

  bool _isLoading          = false;
  Map<String, dynamic>? _result;

  // ── Text controllers ────────────────────────────────────────────────────────
  final _ageController         = TextEditingController();
  final _dosageController      = TextEditingController();
  final _comorbidityController = TextEditingController();

  // ── Dropdown / toggle state ─────────────────────────────────────────────────
  int    _genderEncoded           = 0;
  int    _medicationTypeEncoded   = 0;
  int    _previousAdherence       = 1;
  int    _educationEncoded        = 1;
  double _incomeNormalized        = 0.5;
  int    _socialSupportEncoded    = 1;
  int    _severityEncoded         = 1;
  int    _healthcareAccessEncoded = 1;
  int    _mentalHealthEncoded     = 1;
  int    _insuranceCoverage       = 1;

  @override
  void initState() {
    super.initState();
    final age = widget.patient['age'];
    if (age != null) _ageController.text = age.toString();

    final gender = (widget.patient['gender'] as String? ?? '').toLowerCase();
    if (gender == 'female')     _genderEncoded = 1;
    else if (gender == 'other') _genderEncoded = 2;
    else                        _genderEncoded = 0;
  }

  @override
  void dispose() {
    _ageController.dispose();
    _dosageController.dispose();
    _comorbidityController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  // ── Submit ──────────────────────────────────────────────────────────────────
  Future<void> _runPrediction() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() { _isLoading = true; _result = null; });

    final age           = int.parse(_ageController.text.trim());
    final dosageMg      = double.tryParse(_dosageController.text.trim()) ?? 5.0;
    final dosageNorm    = (dosageMg / 1000.0).clamp(0.0, 1.0);
    final comorbidities = int.tryParse(_comorbidityController.text.trim()) ?? 0;

    final payload = {
      'patient_id':                widget.patient['id'],
      'Age':                       age,
      'gender_encoded':            _genderEncoded,
      'medication_type_encoded':   _medicationTypeEncoded,
      'dosage_normalized':         dosageNorm,
      'Previous_Adherence':        _previousAdherence,
      'education_encoded':         _educationEncoded,
      'income_normalized':         _incomeNormalized,
      'social_support_encoded':    _socialSupportEncoded,
      'severity_encoded':          _severityEncoded,
      'Comorbidities_Count':       comorbidities,
      'healthcare_access_encoded': _healthcareAccessEncoded,
      'mental_health_encoded':     _mentalHealthEncoded,
      'Insurance_Coverage':        _insuranceCoverage,
    };

    try {
      // Uses predictSmart() from your ApiService → POST /predictions/predict-smart/
      final response = await _apiService.predictSmart(payload);
      if (response['success'] == true) {
        setState(() => _result = response['data']);
        await Future.delayed(const Duration(milliseconds: 300));
        final ctx = _resultKey.currentContext;
        if (ctx != null) {
          Scrollable.ensureVisible(ctx,
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeInOut);
        }
      } else {
        _showError(
            response['message'] ?? response['error'] ?? 'Prediction failed');
      }
    } catch (e) {
      _showError(e.toString().replaceAll('Exception: ', ''));
    } finally {
      setState(() => _isLoading = false);
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Row(children: [
          const Icon(Icons.error_outline, color: Colors.white),
          const SizedBox(width: 8),
          Expanded(child: Text(msg)),
        ]),
        backgroundColor: Colors.red.shade700,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  Color _riskColor(String risk) {
    switch (risk) {
      case 'low':    return Colors.green.shade600;
      case 'medium': return Colors.orange.shade600;
      case 'high':   return Colors.red.shade600;
      default:       return Colors.grey;
    }
  }

  IconData _riskIcon(String risk) {
    switch (risk) {
      case 'low':    return Icons.check_circle_rounded;
      case 'medium': return Icons.warning_amber_rounded;
      case 'high':   return Icons.dangerous_rounded;
      default:       return Icons.help_outline;
    }
  }

  String _riskTitle(String risk) {
    switch (risk) {
      case 'low':    return 'LOW RISK';
      case 'medium': return 'MEDIUM RISK';
      case 'high':   return 'HIGH RISK';
      default:       return risk.toUpperCase();
    }
  }

  String _incomeLabel(double v) {
    if (v <= 0.2) return 'Very Low';
    if (v <= 0.4) return 'Low';
    if (v <= 0.6) return 'Medium';
    if (v <= 0.8) return 'High';
    return 'Very High';
  }

  // ════════════════════════════════════════════════════════════════════════════
  // BUILD
  // ════════════════════════════════════════════════════════════════════════════
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F6FA),
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('AI Adherence Prediction',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          Text(widget.patient['full_name'] ?? '',
              style: const TextStyle(fontSize: 12, color: Colors.white70)),
        ]),
        backgroundColor: Colors.deepPurple,
        foregroundColor: Colors.white,
        elevation: 0,
      ),
      body: SingleChildScrollView(
        controller: _scrollController,
        padding: const EdgeInsets.all(16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [

              // ── Top banner ──────────────────────────────────────────────
              _TopBanner(patientName: widget.patient['full_name'] ?? ''),
              const SizedBox(height: 20),

              // ════════════════════════════════════════════════════════════
              // SECTION 1 — Basic Patient Info
              // ════════════════════════════════════════════════════════════
              _sectionHeader(Icons.person_outline,
                  'Basic Patient Info', Colors.deepPurple),
              const SizedBox(height: 12),

              _InputCard(
                child: TextFormField(
                  controller: _ageController,
                  keyboardType: TextInputType.number,
                  decoration: _inputDecor(
                    icon: Icons.cake_outlined,
                    label: 'Patient Age *',
                    hint: 'e.g. 45',
                    helper: 'Enter the patient\'s current age in years (1–120)',
                  ),
                  validator: (v) {
                    if (v == null || v.isEmpty) return 'Age is required';
                    final n = int.tryParse(v);
                    if (n == null || n < 1 || n > 120)
                      return 'Enter a valid age between 1 and 120';
                    return null;
                  },
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.wc_outlined,
                  label: 'Gender *',
                  helper: 'Select the biological gender of the patient',
                  value: _genderEncoded,
                  items: const [
                    DropdownMenuItem(value: 0, child: Text('Male')),
                    DropdownMenuItem(value: 1, child: Text('Female')),
                    DropdownMenuItem(value: 2, child: Text('Other')),
                  ],
                  onChanged: (v) => setState(() => _genderEncoded = v!),
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.school_outlined,
                  label: 'Highest Education Level *',
                  helper:
                      'Higher education = better understanding of prescriptions and dosage instructions',
                  value: _educationEncoded,
                  items: const [
                    DropdownMenuItem(
                        value: 0, child: Text('No Formal Education')),
                    DropdownMenuItem(
                        value: 1,
                        child: Text('Primary School  (up to Grade 5)')),
                    DropdownMenuItem(
                        value: 2,
                        child: Text('Secondary School  (up to Grade 12)')),
                    DropdownMenuItem(
                        value: 3,
                        child: Text('Higher Education  (College / University)')),
                  ],
                  onChanged: (v) => setState(() => _educationEncoded = v!),
                ),
              ),
              const SizedBox(height: 20),

              // ════════════════════════════════════════════════════════════
              // SECTION 2 — Medication Details
              // ════════════════════════════════════════════════════════════
              _sectionHeader(Icons.medication_outlined,
                  'Medication Details', Colors.blue),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.local_pharmacy_outlined,
                  label: 'Type of Medication *',
                  helper:
                      'Injections & patches generally have better adherence than daily oral tablets',
                  value: _medicationTypeEncoded,
                  items: const [
                    DropdownMenuItem(
                        value: 0,
                        child: Text('Tablet — oral pill taken daily')),
                    DropdownMenuItem(
                        value: 1,
                        child:
                            Text('Injection — given by healthcare worker')),
                    DropdownMenuItem(
                        value: 2,
                        child: Text('Syrup — liquid oral medication')),
                    DropdownMenuItem(
                        value: 3,
                        child: Text('Capsule — encapsulated oral pill')),
                    DropdownMenuItem(
                        value: 4,
                        child:
                            Text('Patch — skin adhesive, weekly or daily')),
                  ],
                  onChanged: (v) =>
                      setState(() => _medicationTypeEncoded = v!),
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: TextFormField(
                  controller: _dosageController,
                  keyboardType:
                      const TextInputType.numberWithOptions(decimal: true),
                  decoration: _inputDecor(
                    icon: Icons.science_outlined,
                    label: 'Total Daily Dosage (mg) *',
                    hint: 'e.g. 500',
                    helper:
                        'Sum of ALL medications per day in milligrams — e.g. 2 × 250 mg tablet = enter 500',
                  ),
                  validator: (v) {
                    if (v == null || v.isEmpty) return 'Dosage is required';
                    final n = double.tryParse(v);
                    if (n == null || n <= 0)
                      return 'Enter a valid positive dosage in mg';
                    return null;
                  },
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: TextFormField(
                  controller: _comorbidityController,
                  keyboardType: TextInputType.number,
                  decoration: _inputDecor(
                    icon: Icons.health_and_safety_outlined,
                    label: 'Number of Other Conditions (Comorbidities) *',
                    hint: 'e.g. 2',
                    helper:
                        'Count of other chronic illnesses besides the main one — e.g. if patient has diabetes AND hypertension, enter 2. Enter 0 if none.',
                  ),
                  validator: (v) {
                    if (v == null || v.isEmpty)
                      return 'Required — enter 0 if none';
                    final n = int.tryParse(v);
                    if (n == null || n < 0)
                      return 'Enter 0 or a positive whole number';
                    return null;
                  },
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.monitor_heart_outlined,
                  label: 'Primary Condition Severity *',
                  helper:
                      'How severe is the patient\'s main condition? Severe conditions with harsh side effects often reduce adherence',
                  value: _severityEncoded,
                  items: const [
                    DropdownMenuItem(
                        value: 0,
                        child:
                            Text('Mild — manageable, minimal impact on life')),
                    DropdownMenuItem(
                        value: 1,
                        child: Text(
                            'Moderate — noticeable symptoms, needs ongoing treatment')),
                    DropdownMenuItem(
                        value: 2,
                        child: Text(
                            'Severe — significantly limits daily activities')),
                  ],
                  onChanged: (v) => setState(() => _severityEncoded = v!),
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _ToggleField(
                  icon: Icons.history_outlined,
                  label: 'Previous Adherence History *',
                  helper:
                      '⭐ Strongest predictor. Did this patient correctly follow their last medication course?',
                  value: _previousAdherence == 1,
                  trueText:
                      '✅  Yes — patient followed treatment correctly before',
                  falseText:
                      '❌  No — patient missed doses or stopped early before',
                  onChanged: (v) =>
                      setState(() => _previousAdherence = v ? 1 : 0),
                ),
              ),
              const SizedBox(height: 20),

              // ════════════════════════════════════════════════════════════
              // SECTION 3 — Financial & Insurance
              // ════════════════════════════════════════════════════════════
              _sectionHeader(Icons.account_balance_wallet_outlined,
                  'Financial & Insurance', Colors.teal),
              const SizedBox(height: 12),

              _InputCard(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  Row(children: [
                    Icon(Icons.attach_money,
                        size: 20, color: Colors.grey.shade600),
                    const SizedBox(width: 10),
                    const Expanded(
                      child: Text('Monthly Household Income Level *',
                          style: TextStyle(
                              fontWeight: FontWeight.w600, fontSize: 14)),
                    ),
                    _Chip(
                        label: _incomeLabel(_incomeNormalized),
                        color: Colors.teal),
                  ]),
                  const SizedBox(height: 4),
                  Padding(
                    padding: const EdgeInsets.only(left: 30),
                    child: Text(
                      'Lower income → higher risk of skipping medication due to cost constraints',
                      style: TextStyle(
                          fontSize: 12, color: Colors.grey.shade500),
                    ),
                  ),
                  SliderTheme(
                    data: SliderTheme.of(context).copyWith(
                      activeTrackColor: Colors.teal,
                      thumbColor: Colors.teal,
                      overlayColor: Colors.teal.withOpacity(0.1),
                      inactiveTrackColor: Colors.teal.shade100,
                    ),
                    child: Slider(
                      value: _incomeNormalized,
                      min: 0.0,
                      max: 1.0,
                      divisions: 10,
                      onChanged: (v) =>
                          setState(() => _incomeNormalized = v),
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                      Text('Very Low\n(< ₹5,000/mo)',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: 10,
                              color: Colors.grey.shade500)),
                      Text('Very High\n(> ₹50,000/mo)',
                          textAlign: TextAlign.center,
                          style: TextStyle(
                              fontSize: 10,
                              color: Colors.grey.shade500)),
                    ]),
                  ),
                  const SizedBox(height: 8),
                ]),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _ToggleField(
                  icon: Icons.verified_user_outlined,
                  label: 'Health Insurance Coverage *',
                  helper:
                      'Insured patients are significantly more likely to collect and continue medication',
                  value: _insuranceCoverage == 1,
                  trueText: '✅  Yes — has active health insurance',
                  falseText:
                      '❌  No — paying entirely out of pocket',
                  onChanged: (v) =>
                      setState(() => _insuranceCoverage = v ? 1 : 0),
                ),
              ),
              const SizedBox(height: 20),

              // ════════════════════════════════════════════════════════════
              // SECTION 4 — Social & Healthcare Support
              // ════════════════════════════════════════════════════════════
              _sectionHeader(Icons.support_agent_outlined,
                  'Social & Healthcare Support', Colors.orange),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.people_outline,
                  label: 'Social Support Level *',
                  helper:
                      'Does the patient have family or friends who actively remind and assist them?',
                  value: _socialSupportEncoded,
                  items: const [
                    DropdownMenuItem(
                        value: 0,
                        child: Text(
                            'Low — lives alone, no one reminding them')),
                    DropdownMenuItem(
                        value: 1,
                        child:
                            Text('Medium — some occasional family support')),
                    DropdownMenuItem(
                        value: 2,
                        child: Text(
                            'High — strong and consistent support network')),
                  ],
                  onChanged: (v) =>
                      setState(() => _socialSupportEncoded = v!),
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.local_hospital_outlined,
                  label: 'Healthcare Facility Access *',
                  helper:
                      'How easily can the patient physically reach a clinic or pharmacy to collect medication?',
                  value: _healthcareAccessEncoded,
                  items: const [
                    DropdownMenuItem(
                        value: 0,
                        child: Text(
                            'Low — far away, rural area, difficult to reach')),
                    DropdownMenuItem(
                        value: 1,
                        child:
                            Text('Medium — reachable but requires effort')),
                    DropdownMenuItem(
                        value: 2,
                        child: Text(
                            'High — nearby clinic or pharmacy, easy access')),
                  ],
                  onChanged: (v) =>
                      setState(() => _healthcareAccessEncoded = v!),
                ),
              ),
              const SizedBox(height: 12),

              _InputCard(
                child: _DropdownField<int>(
                  icon: Icons.psychology_outlined,
                  label: 'Mental Health Status *',
                  helper:
                      'Depression and anxiety are leading causes of non-adherence — assess carefully during consultation',
                  value: _mentalHealthEncoded,
                  items: const [
                    DropdownMenuItem(
                        value: 0,
                        child: Text(
                            'Poor — signs of depression or severe anxiety')),
                    DropdownMenuItem(
                        value: 1,
                        child: Text(
                            'Fair — mild stress, mostly under control')),
                    DropdownMenuItem(
                        value: 2,
                        child: Text(
                            'Good — stable, positive mental state')),
                  ],
                  onChanged: (v) =>
                      setState(() => _mentalHealthEncoded = v!),
                ),
              ),
              const SizedBox(height: 28),

              // ── Predict button ──────────────────────────────────────────
              SizedBox(
                height: 56,
                child: ElevatedButton.icon(
                  onPressed: _isLoading ? null : _runPrediction,
                  icon: _isLoading
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                              color: Colors.white, strokeWidth: 2.5))
                      : const Icon(Icons.bolt_rounded, size: 24),
                  label: Text(
                    _isLoading
                        ? 'Analysing Patient Data...'
                        : 'Run AI Prediction',
                    style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 0.5),
                  ),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.deepPurple,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: Colors.deepPurple.shade200,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                    elevation: 4,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // ── Result ──────────────────────────────────────────────────
              if (_result != null) _buildResult(_result!),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }

  // ── Result section ──────────────────────────────────────────────────────────
  Widget _buildResult(Map<String, dynamic> data) {
    final risk           = data['risk_level'] as String? ?? 'unknown';
    final confidence     = ((data['confidence'] as num?) ?? 0) * 100;
    final adherencePct   =
        (data['adherence_percentage'] as num?)?.toDouble() ?? 0;
    final recommendation = data['recommendation'] as String? ?? '';
    final modelUsed      = data['model_used'] as String? ?? 'XGBoost';
    final riskProbs =
        data['risk_probabilities'] as Map<String, dynamic>? ?? {};
    final riskColor = _riskColor(risk);

    return Column(
      key: _resultKey,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [

        // ── Risk banner ───────────────────────────────────────────────────
        Container(
          padding:
              const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
          decoration: BoxDecoration(
            color: riskColor.withOpacity(0.07),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
                color: riskColor.withOpacity(0.4), width: 2),
          ),
          child: Column(children: [
            Icon(_riskIcon(risk), color: riskColor, size: 64),
            const SizedBox(height: 12),
            Text(_riskTitle(risk),
                style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.bold,
                    color: riskColor,
                    letterSpacing: 1.5)),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: adherencePct / 100,
                backgroundColor: Colors.grey.shade200,
                valueColor:
                    AlwaysStoppedAnimation<Color>(riskColor),
                minHeight: 14,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Adherence Score: ${adherencePct.toStringAsFixed(1)}%',
              style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade800),
            ),
            const SizedBox(height: 4),
            Text(
              'Model: $modelUsed  •  Confidence: ${confidence.toStringAsFixed(1)}%',
              style:
                  TextStyle(fontSize: 12, color: Colors.grey.shade500),
            ),
          ]),
        ),
        const SizedBox(height: 16),

        // ── Probability breakdown ─────────────────────────────────────────
        Card(
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16)),
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              const Text('Risk Probability Breakdown',
                  style: TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(height: 4),
              Text('XGBoost confidence for each risk category',
                  style: TextStyle(
                      fontSize: 12, color: Colors.grey.shade500)),
              const SizedBox(height: 16),
              _ProbBar(
                  label: 'Low Risk — likely to adhere',
                  value: (riskProbs['low'] as num?)?.toDouble() ?? 0,
                  color: Colors.green.shade600),
              const SizedBox(height: 12),
              _ProbBar(
                  label: 'Medium Risk — needs monitoring',
                  value: (riskProbs['medium'] as num?)?.toDouble() ?? 0,
                  color: Colors.orange.shade600),
              const SizedBox(height: 12),
              _ProbBar(
                  label: 'High Risk — immediate action needed',
                  value: (riskProbs['high'] as num?)?.toDouble() ?? 0,
                  color: Colors.red.shade600),
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // ── Recommendation ────────────────────────────────────────────────
        Card(
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(16)),
          color: riskColor.withOpacity(0.05),
          elevation: 1,
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
              Row(children: [
                Icon(Icons.lightbulb_outline, color: riskColor, size: 22),
                const SizedBox(width: 8),
                Text('Clinical Recommendations',
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 15,
                        color: riskColor)),
              ]),
              Divider(
                  height: 20, color: riskColor.withOpacity(0.2)),
              ...recommendation.split('\n').map((line) => Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: Text(line,
                        style: const TextStyle(
                            fontSize: 13, height: 1.5)),
                  )),
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // ── Re-run ────────────────────────────────────────────────────────
        OutlinedButton.icon(
          onPressed: () => setState(() => _result = null),
          icon: const Icon(Icons.refresh_rounded),
          label: const Text('Reset & Run New Prediction'),
          style: OutlinedButton.styleFrom(
            foregroundColor: Colors.deepPurple,
            side:
                const BorderSide(color: Colors.deepPurple, width: 1.5),
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12)),
          ),
        ),
      ],
    );
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────
  Widget _sectionHeader(IconData icon, String title, Color color) {
    return Row(children: [
      Container(
        padding: const EdgeInsets.all(7),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(9),
        ),
        child: Icon(icon, color: color, size: 18),
      ),
      const SizedBox(width: 10),
      Text(title,
          style: TextStyle(
              fontSize: 15,
              fontWeight: FontWeight.bold,
              color: color)),
      const SizedBox(width: 10),
      Expanded(
          child: Divider(
              color: color.withOpacity(0.3), thickness: 1)),
    ]);
  }

  InputDecoration _inputDecor({
    required IconData icon,
    required String label,
    String? hint,
    String? helper,
  }) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      helperText: helper,
      helperMaxLines: 3,
      prefixIcon: Icon(icon, size: 20),
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300)),
      enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: Colors.grey.shade300)),
      focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide:
              const BorderSide(color: Colors.deepPurple, width: 1.5)),
      filled: true,
      fillColor: Colors.white,
      contentPadding:
          const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
    );
  }
}

// ════════════════════════════════════════════════════════════════════════════
// REUSABLE WIDGETS
// ════════════════════════════════════════════════════════════════════════════

class _TopBanner extends StatelessWidget {
  final String patientName;
  const _TopBanner({required this.patientName});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
            colors: [
              Colors.deepPurple.shade700,
              Colors.deepPurple.shade400
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(children: [
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: Colors.white.withOpacity(0.2),
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.psychology,
              color: Colors.white, size: 30),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
            const Text('XGBoost Prediction Engine',
                style: TextStyle(
                    color: Colors.white,
                    fontSize: 15,
                    fontWeight: FontWeight.bold)),
            const SizedBox(height: 3),
            Text(
              'Fill all 13 fields below to predict adherence risk for $patientName',
              style: const TextStyle(
                  color: Colors.white70, fontSize: 12),
            ),
            const SizedBox(height: 8),
            Wrap(spacing: 6, children: const [
              _StatPill(label: '89.42% Accuracy'),
              _StatPill(label: '20 Features'),
              _StatPill(label: '15k Training Records'),
            ]),
          ]),
        ),
      ]),
    );
  }
}

class _StatPill extends StatelessWidget {
  final String label;
  const _StatPill({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.2),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(label,
          style: const TextStyle(
              color: Colors.white,
              fontSize: 10,
              fontWeight: FontWeight.w600)),
    );
  }
}

class _InputCard extends StatelessWidget {
  final Widget child;
  const _InputCard({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
              color: Colors.black.withOpacity(0.04),
              blurRadius: 6,
              offset: const Offset(0, 2))
        ],
      ),
      child: child,
    );
  }
}

class _DropdownField<T> extends StatelessWidget {
  final IconData                  icon;
  final String                    label;
  final String?                   helper;
  final T                         value;
  final List<DropdownMenuItem<T>> items;
  final void Function(T?)         onChanged;

  const _DropdownField({
    required this.icon,
    required this.label,
    this.helper,
    required this.value,
    required this.items,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return DropdownButtonFormField<T>(
      value: value,
      isExpanded: true,
      decoration: InputDecoration(
        labelText: label,
        helperText: helper,
        helperMaxLines: 3,
        prefixIcon: Icon(icon, size: 20),
        border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: BorderSide(color: Colors.grey.shade300)),
        enabledBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: BorderSide(color: Colors.grey.shade300)),
        focusedBorder: OutlineInputBorder(
            borderRadius: BorderRadius.circular(10),
            borderSide: const BorderSide(
                color: Colors.deepPurple, width: 1.5)),
        filled: true,
        fillColor: Colors.white,
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      ),
      items: items,
      onChanged: onChanged,
    );
  }
}

class _ToggleField extends StatelessWidget {
  final IconData            icon;
  final String              label;
  final String?             helper;
  final bool                value;
  final String              trueText;
  final String              falseText;
  final void Function(bool) onChanged;

  const _ToggleField({
    required this.icon,
    required this.label,
    this.helper,
    required this.value,
    required this.trueText,
    required this.falseText,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding:
          const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child:
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, size: 20, color: Colors.grey.shade600),
          const SizedBox(width: 10),
          Expanded(
            child: Text(label,
                style: const TextStyle(
                    fontWeight: FontWeight.w600, fontSize: 14)),
          ),
          Switch(
            value: value,
            onChanged: onChanged,
            activeColor: Colors.deepPurple,
          ),
        ]),
        if (helper != null)
          Padding(
            padding: const EdgeInsets.only(left: 30, bottom: 6),
            child: Text(helper!,
                style: TextStyle(
                    fontSize: 12, color: Colors.grey.shade500)),
          ),
        Padding(
          padding: const EdgeInsets.only(left: 30),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(
                horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: value
                  ? Colors.green.shade50
                  : Colors.red.shade50,
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                  color: value
                      ? Colors.green.shade200
                      : Colors.red.shade200),
            ),
            child: Text(
              value ? trueText : falseText,
              style: TextStyle(
                  fontSize: 12,
                  color: value
                      ? Colors.green.shade700
                      : Colors.red.shade700,
                  fontWeight: FontWeight.w500),
            ),
          ),
        ),
      ]),
    );
  }
}

class _ProbBar extends StatelessWidget {
  final String label;
  final double value;
  final Color  color;
  const _ProbBar(
      {required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(
            child: Text(label,
                style: const TextStyle(
                    fontSize: 13, fontWeight: FontWeight.w500))),
        Text('${(value * 100).toStringAsFixed(1)}%',
            style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.bold,
                color: color)),
      ]),
      const SizedBox(height: 5),
      ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: LinearProgressIndicator(
          value: value.clamp(0.0, 1.0),
          backgroundColor: Colors.grey.shade200,
          valueColor: AlwaysStoppedAnimation<Color>(color),
          minHeight: 11,
        ),
      ),
    ]);
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final Color  color;
  const _Chip({required this.label, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding:
          const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.3)),
      ),
      child: Text(label,
          style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: color.withOpacity(0.9))),
    );
  }
}