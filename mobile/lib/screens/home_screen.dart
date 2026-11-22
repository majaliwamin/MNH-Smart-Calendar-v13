import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:webview_flutter/webview_flutter.dart';

import '../services/api_service.dart';
import '../services/meeting_alarm_service.dart';

/// Native shell for the hosted PWA.
///
/// The timetable, CRARA chat and all new AI features are delivered by the web
/// app, so they update without replacing the installed APK. Native code here
/// is intentionally limited to hosting the WebView, checking the build marker
/// and keeping the existing local meeting alarms synchronised.
class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  static const String webUrl = String.fromEnvironment(
    'MNH_WEB_URL',
    defaultValue: 'https://mnh-smart-calendar-v13.onrender.com',
  );

  final ApiService api = ApiService.instance;
  late final WebViewController _controller;
  Timer? _buildTimer;
  String? _build;
  bool _loading = true;
  String? _error;

  DateTime get _malawiNow => DateTime.now().toUtc().add(const Duration(hours: 2));

  DateTime get _currentWeekMonday {
    final now = _malawiNow;
    return DateTime.utc(now.year, now.month, now.day - (now.weekday - 1));
  }

  bool _isCurrentSlot(int day, Map<String, dynamic> entry) {
    final now = _malawiNow;
    if (day != now.weekday - 1) return false;
    final start = entry['startMinutes'];
    final end = entry['endMinutes'];
    if (start is! int || end is! int) return false;
    final minute = now.hour * 60 + now.minute;
    return minute >= start && minute < end;
  }

  Future<void> _pickDate(
    BuildContext context,
    TextEditingController controller,
  ) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final picked = await showDatePicker(
      context: context,
      initialDate: today,
      firstDate: today,
      lastDate: DateTime(now.year + 3, now.month, now.day),
      helpText: 'Select activity date',
    );
    if (picked != null) {
      controller.text =
          '${picked.year.toString().padLeft(4, "0")}-'
          '${picked.month.toString().padLeft(2, "0")}-'
          '${picked.day.toString().padLeft(2, "0")}';
    }
  }

  Future<void> _pickTime(
    BuildContext context,
    TextEditingController controller,
  ) async {
    final parts = controller.text.split(':');
    final initial = TimeOfDay(
      hour: int.tryParse(parts.first) ?? 8,
      minute: int.tryParse(parts.length > 1 ? parts[1] : '0') ?? 0,
    );
    final picked = await showTimePicker(
      context: context,
      initialTime: initial,
      helpText: 'Select activity time',
    );
    if (picked != null) {
      controller.text =
          '${picked.hour.toString().padLeft(2, "0")}:'
          '${picked.minute.toString().padLeft(2, "0")}';
    }
  }

  Future<void> _syncAlarmsIfAccepted(bool accepted) async {
    if (accepted != true) {
      return;
    }
    await _syncAlarms();
  }

  @override
  void initState() {
    super.initState();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF0B1220))
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (String url) async {
          if (!mounted) {
            return;
          }
          setState(() => _loading = false);
          await _syncAlarmsIfAccepted(true);
        },
        onWebResourceError: (WebResourceError error) {
          if (!mounted) return;
          setState(() {
            _loading = false;
            _error = 'Could not load the hosted timetable: ${error.description}';
          });
        },
      ))
      ..loadRequest(Uri.parse(webUrl));

    _buildTimer = Timer.periodic(const Duration(hours: 1), (_) => _checkBuild());
    _checkBuild();
  }

  @override
  void dispose() {
    _buildTimer?.cancel();
    super.dispose();
  }

  /// Compare the native shell's remembered build with the server marker.
  /// A mismatch clears the WebView cache and reloads the hosted PWA.
  Future<void> _checkBuild() async {
    try {
      final response = await http
          .get(Uri.parse('$webUrl/api/health'))
          .timeout(const Duration(seconds: 10));
      if (response.statusCode != 200 || !mounted) return;
      final data = jsonDecode(response.body);
      final servedBuild = data is Map ? data['build']?.toString() : null;
      if (servedBuild == null || servedBuild.isEmpty) return;
      final previous = _build;
      setState(() => _build = servedBuild);
      if (previous != null && previous != servedBuild) {
        await _controller.clearCache();
        await _controller.reload();
      }
    } catch (_) {
      // Offline or slow networks must never break the installed shell; the
      // service worker remains network-first and retries on the next load.
    }
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    await _checkBuild();
    await _controller.reload();
  }

  Future<void> _syncAlarms() async {
    try {
      final cells = await api.collection('cells');
      await MeetingAlarmService.instance.synchronize(
        cellRows: cells,
        currentWeekMonday: _currentWeekMonday,
      );
    } catch (_) {
      // Alarm synchronisation is best-effort; the WebView keeps working.
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      appBar: AppBar(
        title: const Text('MNH Calendar'),
        actions: [
          const Icon(Icons.calendar_month_outlined, size: 16, color: Color(0x88C7A45B)),
          const Icon(Icons.schedule_outlined, size: 16, color: Color(0x88C7A45B)),
          Center(
            child: Padding(
              padding: const EdgeInsets.only(right: 12),
              child: Text(
                _build ?? 'checking…',
                style: const TextStyle(fontSize: 10, color: Color(0xFFC7A45B)),
              ),
            ),
          ),
        ],
      ),
      body: Stack(
        children: [
          WebViewWidget(controller: _controller),
          if (_loading)
            const Center(
              child: CircularProgressIndicator(color: Color(0xFFC7A45B)),
            ),
          if (_error != null)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _error!,
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: Color(0xFFFFB4B4)),
                    ),
                    const SizedBox(height: 12),
                    FilledButton(
                      onPressed: _reload,
                      child: const Text('Try again'),
                    ),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}
