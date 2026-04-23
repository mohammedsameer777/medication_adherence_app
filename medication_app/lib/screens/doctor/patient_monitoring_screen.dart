import 'package:flutter/material.dart';
import '../../services/api_service.dart';

/// Doctor taps a patient → opens this screen to see:
///   • Today's medicines: taken / missed / pending with timeline
///   • Overall medicines left (doses remaining)
///   • 7-day adherence percentage
///   • All active prescriptions and their medicines
class PatientMonitoringScreen extends StatefulWidget {
  final Map<String, dynamic> patient;
  const PatientMonitoringScreen({super.key, required this.patient});

  @override
  State<PatientMonitoringScreen> createState() => _PatientMonitoringScreenState();
}

class _PatientMonitoringScreenState extends State<PatientMonitoringScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  bool _isLoading              = true;
  String? _errorMessage;
  Map<String, dynamic>? _monitoringData;
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadMonitoring();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadMonitoring() async {
    setState(() { _isLoading = true; _errorMessage = null; });
    try {
      final response = await _apiService.getPatientMonitoring(widget.patient['id']);
      if (response['success'] == true) {
        setState(() {
          _monitoringData = response['data'];
          _isLoading      = false;
        });
      } else {
        setState(() {
          _errorMessage = response['message'] ?? 'Failed to load monitoring data';
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
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Patient Monitoring',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          Text(widget.patient['full_name'] ?? '',
              style: const TextStyle(fontSize: 12, color: Colors.white70)),
        ]),
        backgroundColor: Colors.blue,
        foregroundColor: Colors.white,
        actions: [
          IconButton(
              icon: const Icon(Icons.refresh),
              onPressed: _loadMonitoring,
              tooltip: 'Refresh'),
        ],
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white60,
          tabs: const [
            Tab(icon: Icon(Icons.today, size: 18),    text: "Today"),
            Tab(icon: Icon(Icons.medication, size: 18), text: "Medicines"),
            Tab(icon: Icon(Icons.history, size: 18), text: "History"),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? _buildError()
              : TabBarView(
                  controller: _tabController,
                  children: [
                    _buildTodayTab(),
                    _buildMedicinesTab(),
                    _buildHistoryTab(),
                  ],
                ),
    );
  }

  Widget _buildError() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.error_outline, size: 60, color: Colors.red),
          const SizedBox(height: 16),
          Text(_errorMessage!, textAlign: TextAlign.center),
          const SizedBox(height: 16),
          ElevatedButton.icon(
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
            onPressed: _loadMonitoring,
          ),
        ]),
      ),
    );
  }

  // ── TAB 1: TODAY ──────────────────────────────────────────────────────────

  Widget _buildTodayTab() {
    final data     = _monitoringData!;
    final today    = data['today'] as Map<String, dynamic>;
    final adherence = data['adherence'] as Map<String, dynamic>;
    final summary  = data['medicines_summary'] as Map<String, dynamic>;

    final taken   = today['taken'] as int;
    final missed  = today['missed'] as int;
    final pending = today['pending'] as int;
    final total   = today['total_doses'] as int;
    final pct     = (today['completion_pct'] as num).toDouble();
    final medicines = today['medicines'] as List<dynamic>;

    final adherencePct   = (adherence['last_7_days_pct'] as num).toDouble();
    final adherenceLabel = adherence['label'] as String;
    final adherenceColor = _colorFromLabel(adherence['color'] as String);

    return RefreshIndicator(
      onRefresh: _loadMonitoring,
      child: SingleChildScrollView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          // Date banner
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
            decoration: BoxDecoration(
              color: Colors.blue.shade50,
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: Colors.blue.shade100),
            ),
            child: Row(children: [
              Icon(Icons.calendar_today, size: 16, color: Colors.blue.shade700),
              const SizedBox(width: 8),
              Text(today['date'] as String,
                  style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: Colors.blue.shade700,
                      fontSize: 13)),
              const Spacer(),
              Text(data['last_activity'] as String,
                  style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
            ]),
          ),
          const SizedBox(height: 16),

          // Today's summary cards
          Row(children: [
            _SummaryCard(label: 'Taken',   value: taken,   color: Colors.green),
            const SizedBox(width: 8),
            _SummaryCard(label: 'Missed',  value: missed,  color: Colors.red),
            const SizedBox(width: 8),
            _SummaryCard(label: 'Pending', value: pending, color: Colors.orange),
          ]),
          const SizedBox(height: 16),

          // Completion progress
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  const Text("Today's Progress",
                      style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                  const Spacer(),
                  Text('$taken / $total doses',
                      style: TextStyle(
                          fontSize: 13,
                          color: Colors.grey.shade600)),
                ]),
                const SizedBox(height: 10),
                ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: LinearProgressIndicator(
                    value: total > 0 ? pct / 100 : 0,
                    backgroundColor: Colors.grey.shade200,
                    valueColor: AlwaysStoppedAnimation<Color>(
                        pct >= 80 ? Colors.green : pct >= 50 ? Colors.orange : Colors.red),
                    minHeight: 16,
                  ),
                ),
                const SizedBox(height: 6),
                Text('${pct.toStringAsFixed(0)}% completed today',
                    style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey.shade600)),
              ]),
            ),
          ),
          const SizedBox(height: 12),

          // 7-day adherence
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            color: adherenceColor.withOpacity(0.06),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(children: [
                CircleAvatar(
                  radius: 32,
                  backgroundColor: adherenceColor.withOpacity(0.15),
                  child: Text(
                    '${adherencePct.toStringAsFixed(0)}%',
                    style: TextStyle(
                        color: adherenceColor,
                        fontWeight: FontWeight.bold,
                        fontSize: 16),
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    const Text('7-Day Adherence',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 14)),
                    const SizedBox(height: 4),
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 10, vertical: 3),
                      decoration: BoxDecoration(
                        color: adherenceColor.withOpacity(0.15),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Text(adherenceLabel,
                          style: TextStyle(
                              color: adherenceColor,
                              fontWeight: FontWeight.bold,
                              fontSize: 12)),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '${adherence['last_7_days_taken']} of '
                      '${adherence['last_7_days_total']} doses taken',
                      style: TextStyle(
                          fontSize: 12, color: Colors.grey.shade600),
                    ),
                  ]),
                ),
              ]),
            ),
          ),
          const SizedBox(height: 16),

          // Medicines left summary
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Overall Medicines Left',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const SizedBox(height: 12),
                Row(children: [
                  _InfoTile(
                    icon: Icons.medication,
                    label: 'Active\nMedicines',
                    value: summary['active_medicines_count'].toString(),
                    color: Colors.blue,
                  ),
                  const SizedBox(width: 8),
                  _InfoTile(
                    icon: Icons.format_list_numbered,
                    label: 'Doses\nRemaining',
                    value: summary['total_doses_remaining'].toString(),
                    color: Colors.purple,
                  ),
                  const SizedBox(width: 8),
                  _InfoTile(
                    icon: Icons.description,
                    label: 'Active\nPrescriptions',
                    value: summary['active_prescriptions'].toString(),
                    color: Colors.teal,
                  ),
                ]),
              ]),
            ),
          ),
          const SizedBox(height: 16),

          // Today's medicine timeline
          if (medicines.isNotEmpty) ...[
            const Text("Today's Medicine Timeline",
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 10),
            ...medicines.map((med) => _MedicineTimelineCard(med: med as Map<String, dynamic>)),
          ] else ...[
            Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(children: [
                  Icon(Icons.event_available, size: 48, color: Colors.grey.shade400),
                  const SizedBox(height: 8),
                  Text('No medicines scheduled for today',
                      style: TextStyle(color: Colors.grey.shade500)),
                ]),
              ),
            ),
          ],
        ]),
      ),
    );
  }

  // ── TAB 2: MEDICINES ──────────────────────────────────────────────────────

  Widget _buildMedicinesTab() {
    final prescriptions = _monitoringData!['prescriptions'] as List<dynamic>;

    if (prescriptions.isEmpty) {
      return const Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Icon(Icons.description_outlined, size: 60, color: Colors.grey),
          SizedBox(height: 12),
          Text('No prescriptions uploaded yet',
              style: TextStyle(color: Colors.grey)),
        ]),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadMonitoring,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: prescriptions.length,
        itemBuilder: (context, i) {
          final rx = prescriptions[i] as Map<String, dynamic>;
          return _PrescriptionCard(rx: rx);
        },
      ),
    );
  }

  // ── TAB 3: HISTORY (quick summary) ───────────────────────────────────────

  Widget _buildHistoryTab() {
    final adherence = _monitoringData!['adherence'] as Map<String, dynamic>;
    final pct       = (adherence['last_7_days_pct'] as num).toDouble();
    final color     = _colorFromLabel(adherence['color'] as String);
    final patient   = _monitoringData!['patient'] as Map<String, dynamic>;

    return RefreshIndicator(
      onRefresh: _loadMonitoring,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          // Patient info card
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                const Text('Patient Profile',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const Divider(height: 16),
                _ProfileRow(Icons.person,          'Name',    patient['full_name']),
                _ProfileRow(Icons.cake,             'Age',     '${patient['age']} years'),
                _ProfileRow(Icons.wc,               'Gender',  patient['gender']),
                _ProfileRow(Icons.medical_services, 'Disease', patient['disease_type']),
                _ProfileRow(Icons.phone,            'Phone',   patient['phone_number']),
              ]),
            ),
          ),
          const SizedBox(height: 16),

          // Adherence gauge
          Card(
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(children: [
                const Text('Overall Adherence (Last 7 Days)',
                    style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                const SizedBox(height: 20),
                Stack(alignment: Alignment.center, children: [
                  SizedBox(
                    width: 130,
                    height: 130,
                    child: CircularProgressIndicator(
                      value: pct / 100,
                      strokeWidth: 12,
                      backgroundColor: Colors.grey.shade200,
                      valueColor: AlwaysStoppedAnimation<Color>(color),
                    ),
                  ),
                  Column(mainAxisSize: MainAxisSize.min, children: [
                    Text('${pct.toStringAsFixed(0)}%',
                        style: TextStyle(
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                            color: color)),
                    Text(adherence['label'] as String,
                        style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
                  ]),
                ]),
                const SizedBox(height: 16),
                Text(
                  '${adherence['last_7_days_taken']} doses taken '
                  'out of ${adherence['last_7_days_total']} scheduled',
                  style: TextStyle(color: Colors.grey.shade600, fontSize: 13),
                  textAlign: TextAlign.center,
                ),
              ]),
            ),
          ),
          const SizedBox(height: 16),

          // Interpretation
          Card(
            color: color.withOpacity(0.06),
            shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: color.withOpacity(0.3))),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Icon(_iconForAdherence(pct), color: color, size: 20),
                  const SizedBox(width: 8),
                  Text('Clinical Interpretation',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 14,
                          color: color)),
                ]),
                const SizedBox(height: 10),
                Text(
                  _interpretationText(pct),
                  style: const TextStyle(fontSize: 13, height: 1.5),
                ),
              ]),
            ),
          ),
        ]),
      ),
    );
  }

  Color _colorFromLabel(String label) {
    switch (label) {
      case 'green':  return Colors.green;
      case 'orange': return Colors.orange;
      default:       return Colors.red;
    }
  }

  IconData _iconForAdherence(double pct) {
    if (pct >= 80) return Icons.check_circle;
    if (pct >= 50) return Icons.warning_amber_rounded;
    return Icons.error_outline;
  }

  String _interpretationText(double pct) {
    if (pct >= 80) {
      return 'Patient is showing good medication adherence. '
          'Continue current monitoring schedule. Monthly check-ins recommended.';
    } else if (pct >= 50) {
      return 'Patient is showing moderate adherence. Consider scheduling a '
          'call to address any barriers. Weekly SMS reminders may help.';
    }
    return 'Patient has poor adherence over the last 7 days. '
        'Immediate intervention is recommended. Consider home visits, '
        'simplifying the medication schedule, or involving family members.';
  }
}

// ── Reusable sub-widgets ───────────────────────────────────────────────────

class _SummaryCard extends StatelessWidget {
  final String label;
  final int    value;
  final Color  color;
  const _SummaryCard({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 16),
        decoration: BoxDecoration(
          color: color.withOpacity(0.1),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: color.withOpacity(0.3)),
        ),
        child: Column(children: [
          Text('$value',
              style: TextStyle(
                  fontSize: 26, fontWeight: FontWeight.bold, color: color)),
          const SizedBox(height: 2),
          Text(label,
              style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
        ]),
      ),
    );
  }
}

class _InfoTile extends StatelessWidget {
  final IconData icon;
  final String   label;
  final String   value;
  final Color    color;
  const _InfoTile({required this.icon, required this.label,
                   required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 12),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(10),
        ),
        child: Column(children: [
          Icon(icon, color: color, size: 22),
          const SizedBox(height: 4),
          Text(value,
              style: TextStyle(
                  fontSize: 18, fontWeight: FontWeight.bold, color: color)),
          Text(label,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 10, color: Colors.grey.shade600)),
        ]),
      ),
    );
  }
}

class _MedicineTimelineCard extends StatelessWidget {
  final Map<String, dynamic> med;
  const _MedicineTimelineCard({required this.med});

  @override
  Widget build(BuildContext context) {
    final status    = med['status'] as String;
    final isTaken   = status == 'taken';
    final isOverdue = status == 'overdue';
    final isPending = status == 'pending';

    Color statusColor = isTaken ? Colors.green
                      : isOverdue ? Colors.red
                      : Colors.orange;

    IconData statusIcon = isTaken   ? Icons.check_circle
                        : isOverdue ? Icons.cancel
                        : Icons.pending;

    String statusLabel = isTaken   ? 'Taken'
                       : isOverdue ? 'Missed / Overdue'
                       : 'Pending';

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: statusColor.withOpacity(0.1),
              shape: BoxShape.circle,
            ),
            child: Icon(Icons.medication, color: statusColor, size: 22),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(med['medicine_name'] as String,
                  style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 14)),
              Text('${med['dosage']}  •  ${med['frequency']}',
                  style: TextStyle(
                      fontSize: 12, color: Colors.grey.shade600)),
              if (med['next_reminder_time'] != null)
                Text('Next: ${med['next_reminder_time']}',
                    style: TextStyle(
                        fontSize: 11, color: Colors.grey.shade500)),
            ]),
          ),
          Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
            Icon(statusIcon, color: statusColor, size: 20),
            const SizedBox(height: 2),
            Text(statusLabel,
                style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: statusColor)),
            Text(
              '${med['doses_taken_today']}/${med['doses_total_today']} doses',
              style: TextStyle(fontSize: 10, color: Colors.grey.shade500),
            ),
          ]),
        ]),
      ),
    );
  }
}

class _PrescriptionCard extends StatelessWidget {
  final Map<String, dynamic> rx;
  const _PrescriptionCard({required this.rx});

  @override
  Widget build(BuildContext context) {
    final medicines = rx['medicines'] as List<dynamic>;

    return Card(
      margin: const EdgeInsets.only(bottom: 14),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        childrenPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        title: Row(children: [
          Icon(Icons.description, color: Colors.blue.shade700, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(rx['disease'] as String? ?? 'Prescription',
                style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 14)),
          ),
        ]),
        subtitle: Text(
          '${rx['date_uploaded']}  •  ${rx['total_medicines']} medicines  '
          '•  ${rx['treatment_duration']} days',
          style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
        ),
        children: medicines.isEmpty
            ? [const ListTile(
                title: Text('No medicines found', style: TextStyle(color: Colors.grey)))]
            : medicines.map((med) {
                final m        = med as Map<String, dynamic>;
                final pct      = (m['adherence_pct'] as num).toDouble();
                final dLeft    = m['doses_left'] as int;
                final barColor = pct >= 80 ? Colors.green
                               : pct >= 50 ? Colors.orange
                               : Colors.red;

                return Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Row(children: [
                      const Icon(Icons.circle, size: 6, color: Colors.blue),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(m['medicine_name'] as String,
                            style: const TextStyle(
                                fontWeight: FontWeight.w600, fontSize: 13)),
                      ),
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: dLeft > 0
                              ? Colors.blue.shade50
                              : Colors.green.shade50,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Text(
                          dLeft > 0 ? '$dLeft doses left' : 'Complete',
                          style: TextStyle(
                              fontSize: 10,
                              fontWeight: FontWeight.w600,
                              color: dLeft > 0
                                  ? Colors.blue.shade700
                                  : Colors.green.shade700),
                        ),
                      ),
                    ]),
                    const SizedBox(height: 4),
                    Text('${m['dosage']}  •  ${m['frequency']}',
                        style: TextStyle(fontSize: 11, color: Colors.grey.shade500)),
                    const SizedBox(height: 6),
                    Row(children: [
                      Expanded(
                        child: ClipRRect(
                          borderRadius: BorderRadius.circular(4),
                          child: LinearProgressIndicator(
                            value: (m['doses_taken'] as int) /
                                   ((m['doses_total'] as int).clamp(1, 9999)),
                            backgroundColor: Colors.grey.shade200,
                            valueColor: AlwaysStoppedAnimation<Color>(barColor),
                            minHeight: 8,
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Text('${pct.toStringAsFixed(0)}%',
                          style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: barColor)),
                    ]),
                  ]),
                );
              }).toList(),
      ),
    );
  }
}

class _ProfileRow extends StatelessWidget {
  final IconData icon;
  final String   label;
  final dynamic  value;
  const _ProfileRow(this.icon, this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(children: [
        Icon(icon, size: 16, color: Colors.grey.shade500),
        const SizedBox(width: 8),
        Text('$label: ',
            style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        Text('$value', style: const TextStyle(fontSize: 13)),
      ]),
    );
  }
}