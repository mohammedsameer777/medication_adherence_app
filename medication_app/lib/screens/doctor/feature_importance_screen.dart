import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class FeatureImportanceScreen extends StatefulWidget {
  const FeatureImportanceScreen({super.key});

  @override
  State<FeatureImportanceScreen> createState() =>
      _FeatureImportanceScreenState();
}

class _FeatureImportanceScreenState extends State<FeatureImportanceScreen> {
  final ApiService _apiService = ApiService();
  bool _isLoading              = true;
  String? _errorMessage;
  List<dynamic> _importances   = [];
  List<String> _selectedFeatures = [];
  int _featuresSelected        = 0;

  static const Map<String, String> _labels = {
    'income_normalized':          'Income Level',
    'dosage_normalized':          'Dosage Amount',
    'Age':                        'Patient Age',
    'Previous_Adherence':         'Previous Adherence',
    'Comorbidities_Count':        'No. of Comorbidities',
    'severity_encoded':           'Condition Severity',
    'healthcare_access_encoded':  'Healthcare Access',
    'mental_health_encoded':      'Mental Health Status',
    'medication_type_encoded':    'Medication Type',
    'education_encoded':          'Education Level',
    'social_support_encoded':     'Social Support',
    'gender_encoded':             'Gender',
    'Insurance_Coverage':         'Insurance Coverage',
  };

  @override
  void initState() {
    super.initState();
    _loadFeatures();
  }

  Future<void> _loadFeatures() async {
    setState(() { _isLoading = true; _errorMessage = null; });
    try {
      final response = await _apiService.getSelectedFeatures();
      if (response['success'] == true) {
        final data = response['data'] as Map<String, dynamic>;
        setState(() {
          _importances       = data['importances_ranked'] as List<dynamic>;
          _selectedFeatures  = List<String>.from(data['selected_features']);
          _featuresSelected  = data['features_selected'] as int;
          _isLoading         = false;
        });
      } else {
        setState(() {
          _errorMessage = response['message'] ?? 'Failed to load features';
          _isLoading    = false;
        });
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString().replaceAll('Exception: ', '');
        _isLoading    = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.grey.shade50,
      appBar: AppBar(
        title: const Text('Feature Importances'),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadFeatures,
              tooltip: 'Refresh'),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.wifi_off, size: 60, color: Colors.grey),
                        const SizedBox(height: 16),
                        Text(_errorMessage!, textAlign: TextAlign.center),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          icon: const Icon(Icons.refresh),
                          label: const Text('Retry'),
                          onPressed: _loadFeatures,
                        ),
                      ]))
              : _buildContent(),
    );
  }

  Widget _buildContent() {
    final maxImp = _importances.isNotEmpty
        ? (_importances.first['importance'] as num).toDouble()
        : 1.0;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        // Header
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
                colors: [Colors.blue.shade700, Colors.blue.shade500]),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Row(children: [
            Container(
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: Colors.white.withOpacity(0.2),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Icon(Icons.bar_chart, color: Colors.white, size: 32),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Random Forest Feature Importances',
                        style: TextStyle(
                            color: Colors.white,
                            fontSize: 16,
                            fontWeight: FontWeight.bold)),
                    Text(
                      'Top $_featuresSelected features selected from 13 available',
                      style: const TextStyle(color: Colors.white70, fontSize: 12),
                    ),
                  ]),
            ),
          ]),
        ),
        const SizedBox(height: 16),

        // Legend
        Row(children: [
          _LegendDot(color: Colors.blue.shade600, label: 'Selected for prediction'),
          const SizedBox(width: 16),
          _LegendDot(color: Colors.grey.shade400, label: 'Not selected'),
        ]),
        const SizedBox(height: 16),

        // Bar chart
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('All 13 Features — Ranked by Importance',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Text(
                'Importance = how much each feature contributes to predictions',
                style: TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
              const Divider(height: 24),
              ..._importances.asMap().entries.map((entry) {
                final rank       = entry.key + 1;
                final item       = entry.value as Map<String, dynamic>;
                final feat       = item['feature'] as String;
                final imp        = (item['importance'] as num).toDouble();
                final isSelected = item['selected'] == true;
                final barWidth   = maxImp > 0 ? imp / maxImp : 0.0;

                return _FeatureBar(
                  rank: rank,
                  label: _labels[feat] ?? feat,
                  importance: imp,
                  barWidth: barWidth,
                  isSelected: isSelected,
                );
              }),
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // Selected features summary
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(Icons.check_circle, color: Colors.blue.shade700),
                const SizedBox(width: 8),
                Text(
                  'Selected Features ($_featuresSelected / 13)',
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.bold),
                ),
              ]),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: _selectedFeatures.map((feat) {
                  return Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(
                      color: Colors.blue.shade50,
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: Colors.blue.shade200),
                    ),
                    child: Text(
                      _labels[feat] ?? feat,
                      style: TextStyle(
                          fontSize: 12,
                          color: Colors.blue.shade700,
                          fontWeight: FontWeight.w600),
                    ),
                  );
                }).toList(),
              ),
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // Info card
        Card(
          color: Colors.amber.shade50,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('What Does This Mean?',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              const SizedBox(height: 8),
              _BulletPoint(
                  'Previous adherence history is the strongest predictor — past behaviour predicts future compliance.'),
              _BulletPoint(
                  'Income level matters — lower income patients have higher non-adherence risk.'),
              _BulletPoint(
                  'Dosage amount — very high or complex dosing leads to more missed doses.'),
              _BulletPoint(
                  'Features with low importance (gender, insurance) were excluded to avoid noise.'),
            ]),
          ),
        ),
        const SizedBox(height: 32),
      ]),
    );
  }
}

class _FeatureBar extends StatelessWidget {
  final int rank;
  final String label;
  final double importance;
  final double barWidth;
  final bool isSelected;

  const _FeatureBar({
    required this.rank,
    required this.label,
    required this.importance,
    required this.barWidth,
    required this.isSelected,
  });

  @override
  Widget build(BuildContext context) {
    final barColor =
        isSelected ? Colors.blue.shade600 : Colors.grey.shade400;

    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            width: 26,
            height: 26,
            decoration: BoxDecoration(
              color: isSelected
                  ? Colors.blue.shade100
                  : Colors.grey.shade200,
              borderRadius: BorderRadius.circular(6),
            ),
            child: Center(
              child: Text('$rank',
                  style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: isSelected
                          ? Colors.blue.shade700
                          : Colors.grey.shade600)),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Row(children: [
              Expanded(
                child: Text(label,
                    style: TextStyle(
                        fontSize: 13,
                        fontWeight: isSelected
                            ? FontWeight.w700
                            : FontWeight.w400,
                        color: isSelected
                            ? Colors.blue.shade800
                            : Colors.grey.shade700)),
              ),
              if (isSelected)
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.blue.shade600,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text('SELECTED',
                      style: TextStyle(
                          fontSize: 9,
                          color: Colors.white,
                          fontWeight: FontWeight.bold)),
                ),
              const SizedBox(width: 8),
              Text('${(importance * 100).toStringAsFixed(1)}%',
                  style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: barColor)),
            ]),
          ),
        ]),
        const SizedBox(height: 6),
        Row(children: [
          const SizedBox(width: 34),
          Expanded(
            child: Stack(children: [
              Container(
                height: 12,
                decoration: BoxDecoration(
                  color: Colors.grey.shade200,
                  borderRadius: BorderRadius.circular(6),
                ),
              ),
              FractionallySizedBox(
                widthFactor: barWidth.clamp(0.02, 1.0),
                child: Container(
                  height: 12,
                  decoration: BoxDecoration(
                    color: barColor,
                    borderRadius: BorderRadius.circular(6),
                    gradient: isSelected
                        ? LinearGradient(colors: [
                            Colors.blue.shade400,
                            Colors.blue.shade700
                          ])
                        : null,
                  ),
                ),
              ),
            ]),
          ),
        ]),
      ]),
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Container(
          width: 14,
          height: 14,
          decoration: BoxDecoration(
              color: color, borderRadius: BorderRadius.circular(3))),
      const SizedBox(width: 6),
      Text(label,
          style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
    ]);
  }
}

class _BulletPoint extends StatelessWidget {
  final String text;
  const _BulletPoint(this.text);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('• ',
            style: TextStyle(
                color: Colors.amber.shade700, fontWeight: FontWeight.bold)),
        Expanded(
            child: Text(text,
                style: const TextStyle(fontSize: 12, height: 1.4))),
      ]),
    );
  }
}