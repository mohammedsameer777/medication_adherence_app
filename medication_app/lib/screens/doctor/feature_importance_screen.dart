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
  bool _isLoading                 = true;
  String? _errorMessage;
  List<dynamic> _importances      = [];
  List<String> _selectedFeatures  = [];
  int _featuresSelected           = 0;
  int _totalFeaturesAvailable     = 34;

  // ── Labels for all 34 features (13 original + 21 engineered) ──────────────
  static const Map<String, String> _labels = {
    // ── Original 13 ──────────────────────────────────────────────────────────
    'Age':                        'Patient Age',
    'gender_encoded':             'Gender',
    'medication_type_encoded':    'Medication Type',
    'dosage_normalized':          'Dosage Amount',
    'Previous_Adherence':         'Previous Adherence',
    'education_encoded':          'Education Level',
    'income_normalized':          'Income Level',
    'social_support_encoded':     'Social Support',
    'severity_encoded':           'Condition Severity',
    'Comorbidities_Count':        'No. of Comorbidities',
    'healthcare_access_encoded':  'Healthcare Access',
    'mental_health_encoded':      'Mental Health Status',
    'Insurance_Coverage':         'Insurance Coverage',
    // ── Engineered 21 ────────────────────────────────────────────────────────
    'vulnerability_score':        'Vulnerability Score',
    'support_gap':                'Support Gap',
    'adherence_capacity':         'Adherence Capacity',
    'stress_index':               'Stress Index',
    'dosage_burden':              'Dosage Burden',
    'history_support':            'History × Support',
    'comorbidity_severity':       'Comorbidity Severity',
    'risk_composite':             'Risk Composite',
    'adherence_risk_score':       'Adherence Risk Score',
    'barrier_index':              'Barrier Index',
    'protective_score':           'Protective Score',
    'combined_risk':              'Combined Risk',
    'net_risk_score':             'Net Risk Score',
    'income_x_adherence':         'Income × Adherence',
    'severity_x_comorbid':        'Severity × Comorbidity',
    'access_x_support':           'Access × Support',
    'dosage_x_severity':          'Dosage × Severity',
    'age_x_comorbid':             'Age × Comorbidity',
    'mental_x_income':            'Mental Health × Income',
    'prev_adh_x_severity':        'Prev. Adherence × Severity',
    'insurance_x_income':         'Insurance × Income',
  };

  @override
  void initState() {
    super.initState();
    _loadFeatures();
  }

  Future<void> _loadFeatures() async {
    setState(() {
      _isLoading    = true;
      _errorMessage = null;
    });
    try {
      final response = await _apiService.getSelectedFeatures();
      if (response['success'] == true) {
        final data = response['data'] as Map<String, dynamic>;
        setState(() {
          _importances            = data['importances_ranked'] as List<dynamic>;
          _selectedFeatures       = List<String>.from(data['selected_features']);
          _featuresSelected       = data['features_selected'] as int;
          _totalFeaturesAvailable = (data['total_features_available'] as num?)?.toInt() ?? 34;
          _isLoading              = false;
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
            tooltip: 'Refresh',
          ),
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
                    ],
                  ),
                )
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

        // ── Header card ───────────────────────────────────────────────────────
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
                  const Text(
                    'XGBoost — Feature Importances',
                    style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.bold),
                  ),
                  Text(
                    '$_featuresSelected selected from $_totalFeaturesAvailable engineered features',
                    style: const TextStyle(color: Colors.white70, fontSize: 12),
                  ),
                ],
              ),
            ),
          ]),
        ),
        const SizedBox(height: 12),

        // ── Model accuracy banner ─────────────────────────────────────────────
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.green.shade50,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.green.shade200),
          ),
          child: Row(children: [
            Icon(Icons.emoji_events, color: Colors.green.shade700, size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Primary Model: XGBoost',
                    style: TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 13,
                        color: Colors.green.shade800),
                  ),
                  Text(
                    'Accuracy: 89.42%  •  F1 Score: 89.25%  •  CV F1: 89.45%',
                    style: TextStyle(fontSize: 11, color: Colors.green.shade700),
                  ),
                ],
              ),
            ),
          ]),
        ),
        const SizedBox(height: 16),

        // ── Legend ────────────────────────────────────────────────────────────
        Row(children: [
          _LegendDot(
              color: Colors.blue.shade600,
              label: 'Selected (RFE top $_featuresSelected)'),
          const SizedBox(width: 16),
          _LegendDot(color: Colors.grey.shade400, label: 'Not selected'),
        ]),
        const SizedBox(height: 16),

        // ── Bar chart card ────────────────────────────────────────────────────
        Card(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(
                'All $_totalFeaturesAvailable Features — Ranked by Importance',
                style: const TextStyle(
                    fontSize: 15, fontWeight: FontWeight.bold),
              ),
              const SizedBox(height: 4),
              Text(
                'Importance = how much each feature contributes to XGBoost predictions',
                style:
                    TextStyle(fontSize: 12, color: Colors.grey.shade600),
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

        // ── Selected features chips ───────────────────────────────────────────
        Card(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(Icons.check_circle, color: Colors.blue.shade700),
                const SizedBox(width: 8),
                Text(
                  'RFE Selected Features ($_featuresSelected / $_totalFeaturesAvailable)',
                  style: const TextStyle(
                      fontSize: 15, fontWeight: FontWeight.bold),
                ),
              ]),
              const SizedBox(height: 6),
              Text(
                'Recursive Feature Elimination chose these $_featuresSelected features '
                'from $_totalFeaturesAvailable engineered inputs for maximum XGBoost accuracy.',
                style:
                    TextStyle(fontSize: 12, color: Colors.grey.shade600),
              ),
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

        // ── Feature groups info ───────────────────────────────────────────────
        Card(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 2,
          child: Padding(
            padding: const EdgeInsets.all(20),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Feature Engineering Summary',
                  style: TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)),
              const SizedBox(height: 12),
              _GroupRow(
                color: Colors.blue,
                icon: Icons.person,
                title: '13 Original Features',
                subtitle:
                    'Age, income, dosage, comorbidities, previous adherence, etc.',
              ),
              const SizedBox(height: 8),
              _GroupRow(
                color: Colors.purple,
                icon: Icons.auto_fix_high,
                title: '21 Engineered Features',
                subtitle:
                    'Composite scores: risk index, barrier index, interaction terms, etc.',
              ),
              const SizedBox(height: 8),
              _GroupRow(
                color: Colors.green,
                icon: Icons.filter_alt,
                title: '$_featuresSelected Selected via RFE',
                subtitle:
                    'Recursive Feature Elimination retained the highest-signal features.',
              ),
            ]),
          ),
        ),
        const SizedBox(height: 16),

        // ── Insights card ─────────────────────────────────────────────────────
        Card(
          color: Colors.amber.shade50,
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child:
                Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('Key Insights',
                  style: TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 14)),
              const SizedBox(height: 8),
              const _BulletPoint(
                  'Previous adherence history is the strongest predictor — past behaviour predicts future compliance.'),
              const _BulletPoint(
                  'Composite risk scores (risk_composite, barrier_index) outperform raw features alone.'),
              const _BulletPoint(
                  'Income level matters — lower income patients have higher non-adherence risk.'),
              const _BulletPoint(
                  'Interaction terms (income × adherence, dosage × severity) capture combined patient risk.'),
              const _BulletPoint(
                  'Features with low RFE rank (gender, medication type) were excluded to reduce noise.'),
            ]),
          ),
        ),
        const SizedBox(height: 32),
      ]),
    );
  }
}

// ── Feature bar ───────────────────────────────────────────────────────────────

class _FeatureBar extends StatelessWidget {
  final int    rank;
  final String label;
  final double importance;
  final double barWidth;
  final bool   isSelected;

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
              child: Text(
                '$rank',
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                    color: isSelected
                        ? Colors.blue.shade700
                        : Colors.grey.shade600),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Row(children: [
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                      fontSize: 13,
                      fontWeight: isSelected
                          ? FontWeight.w700
                          : FontWeight.w400,
                      color: isSelected
                          ? Colors.blue.shade800
                          : Colors.grey.shade700),
                ),
              ),
              if (isSelected)
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: Colors.blue.shade600,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: const Text(
                    'SELECTED',
                    style: TextStyle(
                        fontSize: 9,
                        color: Colors.white,
                        fontWeight: FontWeight.bold),
                  ),
                ),
              const SizedBox(width: 8),
              Text(
                '${(importance * 100).toStringAsFixed(1)}%',
                style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: barColor),
              ),
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
                            Colors.blue.shade700,
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

// ── Helper widgets ────────────────────────────────────────────────────────────

class _LegendDot extends StatelessWidget {
  final Color  color;
  final String label;
  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      Container(
        width: 14,
        height: 14,
        decoration: BoxDecoration(
            color: color, borderRadius: BorderRadius.circular(3)),
      ),
      const SizedBox(width: 6),
      Text(label,
          style: TextStyle(fontSize: 12, color: Colors.grey.shade700)),
    ]);
  }
}

class _GroupRow extends StatelessWidget {
  final Color    color;
  final IconData icon;
  final String   title;
  final String   subtitle;

  const _GroupRow({
    required this.color,
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  @override
  Widget build(BuildContext context) {
    return Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(icon, color: color, size: 18),
      ),
      const SizedBox(width: 12),
      Expanded(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(title,
              style: const TextStyle(
                  fontWeight: FontWeight.w600, fontSize: 13)),
          const SizedBox(height: 2),
          Text(subtitle,
              style: TextStyle(
                  fontSize: 12, color: Colors.grey.shade600, height: 1.3)),
        ]),
      ),
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
                color: Colors.amber.shade700,
                fontWeight: FontWeight.bold)),
        Expanded(
          child: Text(text,
              style: const TextStyle(fontSize: 12, height: 1.4)),
        ),
      ]),
    );
  }
}