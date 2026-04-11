import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../providers/auth_provider.dart';
import '../../services/api_service.dart';

class PatientDashboard extends StatefulWidget {
  const PatientDashboard({super.key});

  @override
  State<PatientDashboard> createState() => _PatientDashboardState();
}

class _PatientDashboardState extends State<PatientDashboard> {
  final ApiService _apiService = ApiService();
  List<dynamic> _prescriptions = [];
  List<dynamic> _reminders     = [];
  bool _isLoading              = true;
  int  _selectedIndex          = 0;
  String _reminderFilter       = 'today'; // today | upcoming | all

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() => _isLoading = true);
    try {
      final authProvider = Provider.of<AuthProvider>(context, listen: false);
      final patientId    = authProvider.userData!['id'];

      final prescriptions = await _apiService.getPatientPrescriptions(patientId);
      final reminders     = await _apiService.getPatientRemindersFiltered(
          patientId, _reminderFilter);

      setState(() {
        _prescriptions = prescriptions['data']['prescriptions'];
        _reminders     = reminders['data']['reminders'];
        _isLoading     = false;
      });
    } catch (e) {
      setState(() => _isLoading = false);
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  Future<void> _markAsTaken(int reminderId, String medicineName) async {
    try {
      await _apiService.markReminderTaken(reminderId);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('✅ $medicineName marked as taken!'),
        backgroundColor: Colors.green,
      ));
      _loadData();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text('Error: $e'),
        backgroundColor: Colors.red,
      ));
    }
  }

  @override
  Widget build(BuildContext context) {
    final authProvider = Provider.of<AuthProvider>(context);
    final patient      = authProvider.userData;

    return Scaffold(
      appBar: AppBar(
        title: const Text('My Health'),
        backgroundColor: Colors.green,
        foregroundColor: Colors.white,
        actions: [
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
      body: Column(children: [
        _buildHeader(patient),
        Expanded(
          child: _selectedIndex == 0
              ? _buildPrescriptionsTab()
              : _buildRemindersTab(),
        ),
      ]),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _selectedIndex,
        onTap: (index) {
          setState(() => _selectedIndex = index);
          _loadData();
        },
        items: const [
          BottomNavigationBarItem(
              icon: Icon(Icons.medical_services), label: 'Prescriptions'),
          BottomNavigationBarItem(
              icon: Icon(Icons.notifications), label: 'Reminders'),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _loadData,
        backgroundColor: Colors.green,
        child: const Icon(Icons.refresh),
      ),
    );
  }

  Widget _buildHeader(Map<String, dynamic>? patient) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      color: Colors.green,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Hello, ${patient?['full_name'] ?? 'Patient'}!',
            style: const TextStyle(
                fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
        const SizedBox(height: 4),
        Text('Age: ${patient?['age']} | ${patient?['disease_type']}',
            style: const TextStyle(fontSize: 14, color: Colors.white70)),
      ]),
    );
  }

  // ── Prescriptions tab ─────────────────────────────────────────────────────

  Widget _buildPrescriptionsTab() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());
    if (_prescriptions.isEmpty) {
      return const Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Icon(Icons.medical_services, size: 80, color: Colors.grey),
          SizedBox(height: 16),
          Text('No prescriptions yet'),
          Text('Your doctor will add prescriptions',
              style: TextStyle(color: Colors.grey)),
        ]),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadData,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _prescriptions.length,
        itemBuilder: (context, index) =>
            _PrescriptionCard(prescription: _prescriptions[index]),
      ),
    );
  }

  // ── Reminders tab ─────────────────────────────────────────────────────────

  Widget _buildRemindersTab() {
    if (_isLoading) return const Center(child: CircularProgressIndicator());

    return Column(children: [
      // ── Filter bar ────────────────────────────────────────────────────────
      Container(
        color: Colors.grey.shade100,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        child: Row(children: [
          const Text('Show: ',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
          const SizedBox(width: 8),
          _filterChip('Today', 'today'),
          const SizedBox(width: 8),
          _filterChip('Upcoming', 'upcoming'),
          const SizedBox(width: 8),
          _filterChip('All', 'all'),
        ]),
      ),

      // ── Reminder list ─────────────────────────────────────────────────────
      Expanded(
        child: _reminders.isEmpty
            ? Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.check_circle_outline,
                        size: 80, color: Colors.green),
                    const SizedBox(height: 16),
                    Text(
                      _reminderFilter == 'today'
                          ? 'No reminders for today! 🎉'
                          : 'No reminders found',
                      style: const TextStyle(fontSize: 16),
                    ),
                    const SizedBox(height: 4),
                    const Text('All caught up!',
                        style: TextStyle(color: Colors.grey)),
                  ],
                ),
              )
            : RefreshIndicator(
                onRefresh: _loadData,
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    // Summary card
                    _buildSummaryCard(),
                    const SizedBox(height: 16),

                    // Pending reminders
                    ..._buildReminderSection(
                      'Pending',
                      _reminders
                          .where((r) =>
                              r['status'] == 'scheduled' ||
                              r['status'] == 'sent' ||
                              r['status'] == 'failed')
                          .toList(),
                      showTakenButton: true,
                    ),

                    // Taken reminders
                    ..._buildReminderSection(
                      'Taken ✅',
                      _reminders
                          .where((r) => r['status'] == 'taken')
                          .toList(),
                      showTakenButton: false,
                    ),
                  ],
                ),
              ),
      ),
    ]);
  }

  Widget _filterChip(String label, String value) {
    final isSelected = _reminderFilter == value;
    return GestureDetector(
      onTap: () {
        setState(() => _reminderFilter = value);
        _loadData();
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? Colors.green : Colors.white,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
              color: isSelected ? Colors.green : Colors.grey.shade300),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: isSelected ? Colors.white : Colors.grey.shade700,
            fontWeight:
                isSelected ? FontWeight.bold : FontWeight.normal,
          ),
        ),
      ),
    );
  }

  Widget _buildSummaryCard() {
    final pending = _reminders
        .where((r) =>
            r['status'] == 'scheduled' ||
            r['status'] == 'sent' ||
            r['status'] == 'failed')
        .length;
    final taken = _reminders.where((r) => r['status'] == 'taken').length;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.green.shade50,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.green.shade200),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _summaryItem(pending.toString(), 'Pending', Colors.orange),
          Container(width: 1, height: 40, color: Colors.green.shade200),
          _summaryItem(taken.toString(), 'Taken', Colors.green),
          Container(width: 1, height: 40, color: Colors.green.shade200),
          _summaryItem(_reminders.length.toString(), 'Total', Colors.blue),
        ],
      ),
    );
  }

  Widget _summaryItem(String count, String label, Color color) {
    return Column(children: [
      Text(count,
          style: TextStyle(
              fontSize: 22, fontWeight: FontWeight.bold, color: color)),
      Text(label,
          style: TextStyle(fontSize: 12, color: Colors.grey.shade600)),
    ]);
  }

  List<Widget> _buildReminderSection(
    String title,
    List<dynamic> items, {
    required bool showTakenButton,
  }) {
    if (items.isEmpty) return [];
    return [
      Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(title,
            style: const TextStyle(
                fontWeight: FontWeight.bold, fontSize: 15)),
      ),
      ...items.map((r) => _ReminderCard(
            reminder: r,
            onMarkTaken: showTakenButton
                ? () => _markAsTaken(r['id'], r['medicine_name'])
                : null,
          )),
      const SizedBox(height: 16),
    ];
  }
}

// ── Prescription Card ──────────────────────────────────────────────────────

class _PrescriptionCard extends StatelessWidget {
  final Map<String, dynamic> prescription;
  const _PrescriptionCard({required this.prescription});

  @override
  Widget build(BuildContext context) {
    final medicines = prescription['medicines'] as List?;
    final date      = DateTime.parse(prescription['created_at']);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ExpansionTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
              color: Colors.green.shade50,
              borderRadius: BorderRadius.circular(8)),
          child: const Icon(Icons.medical_services, color: Colors.green),
        ),
        title: Text('Dr. ${prescription['doctor_name']}',
            style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(DateFormat('MMM dd, yyyy').format(date)),
            if (prescription['disease_extracted'] != null)
              Text(prescription['disease_extracted'],
                  style: TextStyle(color: Colors.green.shade700)),
          ],
        ),
        children: [
          if (medicines != null && medicines.isNotEmpty)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Medicines:',
                      style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  ...medicines.map((med) => Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Row(children: [
                          const Icon(Icons.medication,
                              size: 16, color: Colors.green),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(med['medicine_name'],
                                    style: const TextStyle(
                                        fontWeight: FontWeight.bold)),
                                Text(
                                  '${med['dosage']} - ${med['frequency']}',
                                  style: TextStyle(
                                      fontSize: 12,
                                      color: Colors.grey.shade600),
                                ),
                              ],
                            ),
                          ),
                        ]),
                      )),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

// ── Reminder Card ──────────────────────────────────────────────────────────

class _ReminderCard extends StatelessWidget {
  final Map<String, dynamic> reminder;
  final VoidCallback? onMarkTaken;

  const _ReminderCard({required this.reminder, required this.onMarkTaken});

  @override
  Widget build(BuildContext context) {
    final scheduledTime = DateTime.parse(reminder['scheduled_time']).toLocal();
    final status        = reminder['status'] as String;
    final now           = DateTime.now();
    final isOverdue     = scheduledTime.isBefore(now) && status == 'scheduled';

    Color statusColor;
    IconData statusIcon;

    switch (status) {
      case 'taken':
        statusColor = Colors.green;
        statusIcon  = Icons.check_circle;
        break;
      case 'sent':
        statusColor = Colors.blue;
        statusIcon  = Icons.notifications_active;
        break;
      case 'failed':
        statusColor = Colors.red;
        statusIcon  = Icons.error;
        break;
      default:
        statusColor = isOverdue ? Colors.red : Colors.orange;
        statusIcon  = isOverdue ? Icons.warning : Icons.schedule;
    }

    return Card(
      margin: const EdgeInsets.only(bottom: 10),
      shape:
          RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      color: isOverdue ? Colors.red.shade50 : null,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Icon(statusIcon, color: statusColor, size: 28),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(reminder['medicine_name'],
                    style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 15)),
                const SizedBox(height: 2),
                Text(
                  DateFormat('MMM dd, yyyy - hh:mm a')
                      .format(scheduledTime),
                  style: TextStyle(
                      fontSize: 12, color: Colors.grey.shade600),
                ),
                const SizedBox(height: 2),
                Text(
                  isOverdue
                      ? 'MISSED ⚠️'
                      : status == 'taken'
                          ? 'TAKEN ✅'
                          : status.toUpperCase(),
                  style: TextStyle(
                      color: statusColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 12),
                ),
              ],
            ),
          ),
          if (onMarkTaken != null)
            ElevatedButton(
              onPressed: onMarkTaken,
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                    horizontal: 10, vertical: 6),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8)),
                minimumSize: const Size(0, 0),
              ),
              child: const Text('Taken', style: TextStyle(fontSize: 12)),
            ),
        ]),
      ),
    );
  }
}