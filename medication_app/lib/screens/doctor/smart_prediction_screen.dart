import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class SmartPredictionScreen extends StatefulWidget {
  final Map<String, dynamic> patient;
  const SmartPredictionScreen({super.key, required this.patient});

  @override
  State<SmartPredictionScreen> createState() => _SmartPredictionScreenState();
}

class _SmartPredictionScreenState extends State<SmartPredictionScreen> {
  final ApiService _apiService    = ApiService();
  final _formKey                  = GlobalKey<FormState>();
  final _ageController            = TextEditingController();
  final _comorbiditiesController  = TextEditingController();

  double _incomeNormalized        = 0.5;
  double _dosageNormalized        = 0.5;
  int    _previousAdherence       = 1;
  int    _severityEncoded         = 1;
  int    _healthcareAccessEncoded = 1;

  bool _isPredicting              = false;
  Map<String, dynamic>? _result;
  String? _errorMessage;
  final GlobalKey _resultKey      = GlobalKey();

  @override
  void initState() {
    super.initState();
    if (widget.patient['age'] != null) {
      _ageController.text = widget.patient['age'].toString();
    }
  }

  @override
  void dispose() {
    _ageController.dispose();
    _comorbiditiesController.dispose();
    super.dispose();
  }

  Future<void> _predict() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() {
      _isPredicting = true;
      _result       = null;
      _errorMessage = null;
    });

    try {
      final featureData = <String, dynamic>{
        'patient_id':               widget.patient['id'],
        'Age':                      int.parse(_ageController.text.trim()),
        'income_normalized':        double.parse(_incomeNormalized.toStringAsFixed(2)),
        'dosage_normalized':        double.parse(_dosageNormalized.toStringAsFixed(2)),
        'Previous_Adherence':       _previousAdherence,
        'Comorbidities_Count':      int.parse(_comorbiditiesController.text.trim()),
        'severity_encoded':         _severityEncoded,
        'healthcare_access_encoded': _healthcareAccessEncoded,
      };

      final response = await _apiService.predictSmart(featureData);

      if (response['success'] == true) {
        setState(() {
          _result       = response['data'];
          _isPredicting = false;
        });
        Future.delayed(const Duration(milliseconds: 300), () {
          if (_resultKey.currentContext != null) {
            Scrollable.ensureVisible(_resultKey.currentContext!,
                duration: const Duration(milliseconds: 500),
                curve: Curves.easeInOut);
          }
        });
      } else {
        setState(() {
          _errorMessage = response['error'] ?? 'Prediction failed';
          _isPredicting = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
        _isPredicting = false;
      });
    }
  }

  Color _riskColor(String risk) {
    switch (risk.toLowerCase()) {
      case 'high':   return Colors.red;
      case 'medium': return Colors.orange;
      default:       return Colors.green;
    }
  }

  IconData _riskIcon(String risk) {
    switch (risk.toLowerCase()) {
      case 'high':   return Icons.warning_rounded;
      case 'medium': return Icons.info_rounded;
      default:       return Icons.check_circle_rounded;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey.shade50,
      appBar: AppBar(
        title: const Text('AI Smart Prediction'),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          // Patient banner
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                  colors: [Colors.blue.shade700, Colors.blue.shade400]),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(children: [
              CircleAvatar(
                backgroundColor: Colors.white,
                radius: 28,
                child: Text(
                  (widget.patient['full_name'] as String? ?? 'P')[0].toUpperCase(),
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
                      Text(widget.patient['full_name'] ?? 'Patient',
                          style: const TextStyle(
                              color: Colors.white,
                              fontSize: 18,
                              fontWeight: FontWeight.bold)),
                      Text(
                          'Age: ${widget.patient['age']}  |  ${widget.patient['gender'] ?? ''}',
                          style: const TextStyle(
                              color: Colors.white70, fontSize: 13)),
                      Text(widget.patient['disease_type'] ?? '',
                          style: const TextStyle(
                              color: Colors.white70, fontSize: 13)),
                    ]),
              ),
            ]),
          ),
          const SizedBox(height: 12),

          // Info card
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.blue.shade100),
            ),
            child: Row(children: [
              Icon(Icons.auto_awesome, color: Colors.blue.shade700, size: 22),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('AI Feature Selection Active',
                          style: TextStyle(
                              fontWeight: FontWeight.bold,
                              color: Colors.blue.shade700,
                              fontSize: 13)),
                      Text(
                        'Random Forest selected the 7 most predictive features. '
                        'Results are saved to patient history.',
                        style: TextStyle(
                            fontSize: 12, color: Colors.blue.shade600),
                      ),
                    ]),
              ),
            ]),
          ),
          const SizedBox(height: 12),

          // Form
          Card(
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(16)),
            elevation: 2,
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Form(
                key: _formKey,
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                  const Text('Patient Feature Inputs',
                      style: TextStyle(
                          fontSize: 16, fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Text(
                    'Fill in the 7 most important features selected by the AI',
                    style:
                        TextStyle(fontSize: 12, color: Colors.grey.shade600),
                  ),
                  const Divider(height: 24),

                  // Age
                  _buildNumberField(
                    controller: _ageController,
                    label: 'Age (years)',
                    hint: 'e.g. 45',
                    icon: Icons.cake,
                    tooltip: 'Patient age in years (1-120)',
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'Required';
                      final n = int.tryParse(v);
                      if (n == null || n < 1 || n > 120) {
                        return 'Enter valid age (1-120)';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 20),

                  // Income slider
                  _buildSliderField(
                    label: 'Income Level',
                    value: _incomeNormalized,
                    icon: Icons.attach_money,
                    tooltip: '0 = Very low income  to  1 = Very high income',
                    leftLabel: 'Very Low',
                    rightLabel: 'Very High',
                    onChanged: (v) => setState(() => _incomeNormalized = v),
                  ),
                  const SizedBox(height: 20),

                  // Dosage slider
                  _buildSliderField(
                    label: 'Dosage Level',
                    value: _dosageNormalized,
                    icon: Icons.medication,
                    tooltip: '0 = Very low dose  to  1 = Very high dose',
                    leftLabel: 'Low Dose',
                    rightLabel: 'High Dose',
                    onChanged: (v) => setState(() => _dosageNormalized = v),
                  ),
                  const SizedBox(height: 20),

                  // Previous adherence toggle
                  _buildToggleField(
                    label: 'Previous Adherence History',
                    icon: Icons.history,
                    tooltip:
                        'Has this patient followed prescriptions well in the past?',
                    value: _previousAdherence == 1,
                    trueLabel: 'Good History',
                    falseLabel: 'Poor History',
                    onChanged: (v) =>
                        setState(() => _previousAdherence = v ? 1 : 0),
                  ),
                  const SizedBox(height: 20),

                  // Comorbidities
                  _buildNumberField(
                    controller: _comorbiditiesController,
                    label: 'Number of Other Diseases',
                    hint: 'e.g. 2',
                    icon: Icons.medical_information,
                    tooltip: 'How many other medical conditions?',
                    validator: (v) {
                      if (v == null || v.isEmpty) return 'Required';
                      final n = int.tryParse(v);
                      if (n == null || n < 0 || n > 20) {
                        return 'Enter 0-20';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 20),

                  // Condition severity
                  _buildThreeWaySelector(
                    label: 'Condition Severity',
                    icon: Icons.monitor_heart,
                    tooltip:
                        'How severe is the patient\'s main medical condition?',
                    options: const ['Mild', 'Moderate', 'Severe'],
                    selectedIndex: _severityEncoded,
                    colors: const [
                      Colors.green,
                      Colors.orange,
                      Colors.red
                    ],
                    onChanged: (i) => setState(() => _severityEncoded = i),
                  ),
                  const SizedBox(height: 20),

                  // Healthcare access
                  _buildThreeWaySelector(
                    label: 'Healthcare Access',
                    icon: Icons.local_hospital,
                    tooltip:
                        'How easily can the patient access hospitals/pharmacies?',
                    options: const ['Poor', 'Average', 'Good'],
                    selectedIndex: _healthcareAccessEncoded,
                    colors: const [Colors.red, Colors.orange, Colors.green],
                    onChanged: (i) =>
                        setState(() => _healthcareAccessEncoded = i),
                  ),
                  const SizedBox(height: 28),

                  // Submit
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton.icon(
                      onPressed: _isPredicting ? null : _predict,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.blue,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                      icon: _isPredicting
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                  strokeWidth: 2, color: Colors.white),
                            )
                          : const Icon(Icons.psychology),
                      label: Text(
                        _isPredicting
                            ? 'Analysing...'
                            : 'Predict Adherence Risk',
                        style: const TextStyle(
                            fontSize: 16, fontWeight: FontWeight.bold),
                      ),
                    ),
                  ),
                ]),
              ),
            ),
          ),
          const SizedBox(height: 12),

          // Error
          if (_errorMessage != null)
            Container(
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: Colors.red.shade50,
                border: Border.all(color: Colors.red.shade200),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(children: [
                Icon(Icons.error_outline, color: Colors.red.shade700),
                const SizedBox(width: 10),
                Expanded(
                    child: Text(_errorMessage!,
                        style: TextStyle(color: Colors.red.shade700))),
              ]),
            ),

          // Result
          if (_result != null) ...[
            const SizedBox(height: 8),
            _ResultCard(
              key: _resultKey,
              result: _result!,
              riskColor: _riskColor(_result!['risk_level'] ?? 'medium'),
              riskIcon:  _riskIcon(_result!['risk_level'] ?? 'medium'),
            ),
          ],

          const SizedBox(height: 32),
        ]),
      ),
    );
  }

  Widget _buildNumberField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    required String tooltip,
    required String? Function(String?) validator,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Icon(icon, size: 18, color: Colors.blue),
        const SizedBox(width: 6),
        Text(label,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        const SizedBox(width: 4),
        Tooltip(
          message: tooltip,
          child: Icon(Icons.info_outline,
              size: 15, color: Colors.grey.shade500),
        ),
      ]),
      const SizedBox(height: 8),
      TextFormField(
        controller: controller,
        keyboardType: TextInputType.number,
        decoration: InputDecoration(
          hintText: hint,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        ),
        validator: validator,
      ),
    ]);
  }

  Widget _buildSliderField({
    required String label,
    required double value,
    required IconData icon,
    required String tooltip,
    required String leftLabel,
    required String rightLabel,
    required ValueChanged<double> onChanged,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Icon(icon, size: 18, color: Colors.blue),
        const SizedBox(width: 6),
        Text(label,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        const SizedBox(width: 4),
        Tooltip(
          message: tooltip,
          child: Icon(Icons.info_outline,
              size: 15, color: Colors.grey.shade500),
        ),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(8)),
          child: Text(value.toStringAsFixed(2),
              style: TextStyle(
                  color: Colors.blue.shade700,
                  fontWeight: FontWeight.bold,
                  fontSize: 13)),
        ),
      ]),
      Slider(
          value: value,
          min: 0.0,
          max: 1.0,
          divisions: 20,
          activeColor: Colors.blue,
          onChanged: onChanged),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12),
        child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(leftLabel,
              style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
          Text(rightLabel,
              style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
        ]),
      ),
    ]);
  }

  Widget _buildToggleField({
    required String label,
    required IconData icon,
    required String tooltip,
    required bool value,
    required String trueLabel,
    required String falseLabel,
    required ValueChanged<bool> onChanged,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Icon(icon, size: 18, color: Colors.blue),
        const SizedBox(width: 6),
        Text(label,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        const SizedBox(width: 4),
        Tooltip(
          message: tooltip,
          child: Icon(Icons.info_outline,
              size: 15, color: Colors.grey.shade500),
        ),
      ]),
      const SizedBox(height: 8),
      Row(children: [
        Expanded(
          child: GestureDetector(
            onTap: () => onChanged(false),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: !value ? Colors.red.shade100 : Colors.grey.shade100,
                border: Border.all(
                    color: !value ? Colors.red : Colors.grey.shade300),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(10),
                  bottomLeft: Radius.circular(10),
                ),
              ),
              child: Center(
                child: Text(falseLabel,
                    style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: !value ? Colors.red : Colors.grey,
                        fontSize: 13)),
              ),
            ),
          ),
        ),
        Expanded(
          child: GestureDetector(
            onTap: () => onChanged(true),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: value ? Colors.green.shade100 : Colors.grey.shade100,
                border: Border.all(
                    color: value ? Colors.green : Colors.grey.shade300),
                borderRadius: const BorderRadius.only(
                  topRight: Radius.circular(10),
                  bottomRight: Radius.circular(10),
                ),
              ),
              child: Center(
                child: Text(trueLabel,
                    style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: value ? Colors.green : Colors.grey,
                        fontSize: 13)),
              ),
            ),
          ),
        ),
      ]),
    ]);
  }

  Widget _buildThreeWaySelector({
    required String label,
    required IconData icon,
    required String tooltip,
    required List<String> options,
    required int selectedIndex,
    required List<Color> colors,
    required ValueChanged<int> onChanged,
  }) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Icon(icon, size: 18, color: Colors.blue),
        const SizedBox(width: 6),
        Text(label,
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 14)),
        const SizedBox(width: 4),
        Tooltip(
          message: tooltip,
          child: Icon(Icons.info_outline,
              size: 15, color: Colors.grey.shade500),
        ),
      ]),
      const SizedBox(height: 8),
      Row(
        children: List.generate(options.length, (i) {
          final isSelected = selectedIndex == i;
          return Expanded(
            child: GestureDetector(
              onTap: () => onChanged(i),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12),
                margin: EdgeInsets.only(
                  left: i == 0 ? 0 : 2,
                  right: i == options.length - 1 ? 0 : 2,
                ),
                decoration: BoxDecoration(
                  color: isSelected
                      ? colors[i].withOpacity(0.15)
                      : Colors.grey.shade100,
                  border: Border.all(
                      color: isSelected ? colors[i] : Colors.grey.shade300,
                      width: isSelected ? 2 : 1),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Center(
                  child: Text(options[i],
                      style: TextStyle(
                          fontWeight: FontWeight.w600,
                          color: isSelected ? colors[i] : Colors.grey,
                          fontSize: 13)),
                ),
              ),
            ),
          );
        }),
      ),
    ]);
  }
}

// ── Result Card ────────────────────────────────────────────────────────────

class _ResultCard extends StatelessWidget {
  final Map<String, dynamic> result;
  final Color riskColor;
  final IconData riskIcon;

  const _ResultCard({
    super.key,
    required this.result,
    required this.riskColor,
    required this.riskIcon,
  });

  @override
  Widget build(BuildContext context) {
    final riskLevel     = (result['risk_level'] ?? 'unknown').toString();
    final confidence    = (result['confidence'] as num? ?? 0).toDouble();
    final adherencePct  = (result['adherence_percentage'] as num? ?? 0).toDouble();
    final probabilities = result['risk_probabilities'] as Map<String, dynamic>? ?? {};
    final savedToDB     = result['saved_to_db'] == true;

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 4,
      child: Column(children: [
        // Risk header
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: riskColor.withOpacity(0.1),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(16),
              topRight: Radius.circular(16),
            ),
            border: Border.all(color: riskColor.withOpacity(0.3)),
          ),
          child: Column(children: [
            Icon(riskIcon, color: riskColor, size: 48),
            const SizedBox(height: 8),
            Text('${riskLevel.toUpperCase()} RISK',
                style: TextStyle(
                    fontSize: 24,
                    fontWeight: FontWeight.w900,
                    color: riskColor)),
            const SizedBox(height: 4),
            Text('Confidence: ${(confidence * 100).toStringAsFixed(1)}%',
                style: TextStyle(fontSize: 14, color: Colors.grey.shade600)),
          ]),
        ),

        Padding(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            // Adherence score
            const Text('Adherence Score',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: adherencePct / 100,
                    backgroundColor: Colors.grey.shade200,
                    valueColor: AlwaysStoppedAnimation<Color>(riskColor),
                    minHeight: 14,
                  ),
                ),
              ),
              const SizedBox(width: 12),
              Text('${adherencePct.toStringAsFixed(1)}%',
                  style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 16,
                      color: riskColor)),
            ]),
            const SizedBox(height: 4),
            Text('Higher % = better adherence likelihood',
                style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),

            const Divider(height: 24),

            // Probability bars
            const Text('Risk Probabilities',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 12),
            ...['high', 'medium', 'low'].map((level) {
              final prob = (probabilities[level] as num? ?? 0).toDouble();
              final color = level == 'high'
                  ? Colors.red
                  : level == 'medium'
                      ? Colors.orange
                      : Colors.green;
              return Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Column(children: [
                  Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(level[0].toUpperCase() + level.substring(1),
                            style: TextStyle(
                                fontSize: 13,
                                fontWeight: FontWeight.w600,
                                color: color)),
                        Text('${(prob * 100).toStringAsFixed(1)}%',
                            style: TextStyle(
                                fontSize: 13,
                                color: Colors.grey.shade600)),
                      ]),
                  const SizedBox(height: 4),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(
                      value: prob,
                      backgroundColor: Colors.grey.shade200,
                      valueColor: AlwaysStoppedAnimation<Color>(color),
                      minHeight: 10,
                    ),
                  ),
                ]),
              );
            }),

            const Divider(height: 24),

            // Recommendations
            const Text('Doctor Recommendations',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(height: 10),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: riskColor.withOpacity(0.05),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: riskColor.withOpacity(0.2)),
              ),
              child: Text(result['recommendation'] ?? '',
                  style: const TextStyle(fontSize: 13, height: 1.6)),
            ),

            const SizedBox(height: 16),

            // Footer
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Row(children: [
                Icon(Icons.smart_toy, size: 14, color: Colors.grey.shade500),
                const SizedBox(width: 4),
                Text('Model: ${result['model_used'] ?? 'Random Forest'}',
                    style: TextStyle(
                        fontSize: 12, color: Colors.grey.shade500)),
              ]),
              if (savedToDB)
                Row(children: [
                  Icon(Icons.cloud_done,
                      size: 14, color: Colors.green.shade600),
                  const SizedBox(width: 4),
                  Text('Saved to history',
                      style: TextStyle(
                          fontSize: 12, color: Colors.green.shade600)),
                ]),
            ]),
          ]),
        ),
      ]),
    );
  }
}