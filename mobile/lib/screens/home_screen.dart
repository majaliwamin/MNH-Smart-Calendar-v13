import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final api = ApiService.instance;
  bool loading = true, editing = true;
  bool analyticsUnlocked = true;
  String? error;
  String role = 'public';
  int selected = 1;
  Map<String, dynamic> health = {}, analytics = {};
  final Map<String, List<dynamic>> records = {
    'modules': [],
    'cells': [],
    'resources': [],
    'facilitators': [],
    'examinations': [],
    'recurring': [],
    'communications': [],
  };
  List<dynamic> history = [];

  static const _labels = [
    'Dashboard',
    'Weekly Schedule',
    'Monthly Calendar',
    'Upcoming Academic Activities',
    'Modules',
    'Facilitators',
    'Examinations',
    'Recurring Activities',
    'WhatsApp & Communications',
    'Analytics Dashboard',
    'Activity History',
    'Export & Sharing',
    'Settings'
  ];
  static const _icons = [
    Icons.dashboard_outlined,
    Icons.calendar_view_week_outlined,
    Icons.calendar_month_outlined,
    Icons.event_note_outlined,
    Icons.menu_book_outlined,
    Icons.people_outline,
    Icons.school_outlined,
    Icons.repeat,
    Icons.forum_outlined,
    Icons.query_stats_outlined,
    Icons.history,
    Icons.ios_share_outlined,
    Icons.settings_outlined
  ];
  static const _fields = {
    'modules': ['code', 'title', 'facilitator'],
    'facilitators': ['name', 'title', 'department', 'email', 'phone'],
    'examinations': ['title', 'date', 'time', 'venue', 'notes'],
    'recurring': ['title', 'frequency', 'day', 'time', 'venue', 'notes'],
    'communications': ['title', 'message', 'url'],
  };

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final names = records.keys.toList();
      final results = await Future.wait([
        api.health(),
        api.session(),
        api.history(),
        ...names.map(api.collection),
      ]);
      if (!mounted) {
        return;
      }
      setState(() {
        health = Map<String, dynamic>.from(results[0] as Map);
        editing = true;
        role = 'public';
        history = results[2] as List<dynamic>;
        for (var i = 0; i < names.length; i++) {
          records[names[i]] = results[i + 3] as List<dynamic>;
        }
        loading = false;
      });
      if (selected == 9 && analyticsUnlocked) {
        await loadAnalytics();
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString();
        });
      }
    }
  }

  Future<void> loadAnalytics() async {
    try {
      final data = await api.analytics();
      if (mounted) {
        setState(() => analytics = data);
      }
    } catch (e) {
      if (mounted) {
        setState(() => analytics = {'error': e.toString()});
      }
    }
  }

  Future<void> openAnalytics() async {
    if (!mounted) return;
    setState(() {
      analyticsUnlocked = true;
      selected = 9;
    });
    await loadAnalytics();
  }

  Future<void> _pickDate(
      BuildContext context, TextEditingController controller) async {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final picked = await showDatePicker(
        context: context,
        initialDate: today,
        firstDate: today,
        lastDate: DateTime(now.year + 3, now.month, now.day),
        helpText: 'Select activity date');
    if (picked != null) {
      controller.text = DateFormat('yyyy-MM-dd').format(picked);
    }
  }

  Future<void> _pickTime(
      BuildContext context, TextEditingController controller) async {
    final parts = controller.text.split(':');
    final initial = parts.length == 2
        ? TimeOfDay(
            hour: int.tryParse(parts[0]) ?? 8,
            minute: int.tryParse(parts[1]) ?? 0)
        : const TimeOfDay(hour: 8, minute: 0);
    final picked = await showTimePicker(
        context: context,
        initialTime: initial,
        helpText: 'Select activity time');
    if (picked != null) {
      controller.text =
          '${picked.hour.toString().padLeft(2, '0')}:${picked.minute.toString().padLeft(2, '0')}';
    }
  }

  Future<void> addRecord(String collection) async {
    final fields = _fields[collection] ?? ['title', 'facilitator'];
    final controllers = {
      for (final field in fields) field: TextEditingController()
    };
    final accepted = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => AlertDialog(
                title: Text(
                    'Add ${collection == 'communications' ? 'communication' : collection == 'facilitators' ? 'facilitator' : collection == 'examinations' ? 'examination' : collection == 'recurring' ? 'recurring activity' : 'module'}'),
                content: SizedBox(
                    width: 440,
                    child: SingleChildScrollView(
                        child:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                      for (final field in fields)
                        Padding(
                            padding: const EdgeInsets.only(bottom: 9),
                            child: collection == 'recurring' && field == 'day'
                                ? DropdownButtonFormField<String>(
                                    initialValue: '',
                                    decoration: const InputDecoration(labelText: 'Weekday'),
                                    items: const [
                                      DropdownMenuItem(value: '', child: Text('Choose weekday')),
                                      DropdownMenuItem(value: 'Monday', child: Text('Monday')),
                                      DropdownMenuItem(value: 'Tuesday', child: Text('Tuesday')),
                                      DropdownMenuItem(value: 'Wednesday', child: Text('Wednesday')),
                                      DropdownMenuItem(value: 'Thursday', child: Text('Thursday')),
                                      DropdownMenuItem(value: 'Friday', child: Text('Friday')),
                                    ],
                                    onChanged: (value) => controllers[field]!.text = value ?? '')
                                : field == 'facilitator'
                                ? DropdownButtonFormField<String>(
                                    initialValue: '',
                                    decoration: const InputDecoration(
                                        labelText: 'Assigned lecturer'),
                                    items: [
                                      const DropdownMenuItem(
                                          value: '',
                                          child: Text('No lecturer assigned')),
                                      for (final row in records['facilitators']!)
                                        if ((row['data']?['name'] ?? '').toString().isNotEmpty)
                                          DropdownMenuItem(
                                              value: row['id'].toString(),
                                              child: Text(row['data']['name'].toString()))
                                    ],
                                    onChanged: (value) =>
                                        controllers[field]!.text = value ?? '')
                                : field == 'date'
                                ? TextField(
                                    controller: controllers[field],
                                    readOnly: true,
                                    onTap: () => _pickDate(
                                        dialogContext, controllers[field]!),
                                    decoration: const InputDecoration(
                                        labelText: 'Date',
                                        hintText:
                                            'Today up to three years ahead',
                                        suffixIcon: Icon(
                                            Icons.calendar_month_outlined)))
                                : field == 'time'
                                    ? TextField(
                                        controller: controllers[field],
                                        readOnly: true,
                                        onTap: () => _pickTime(
                                            dialogContext, controllers[field]!),
                                        decoration: const InputDecoration(
                                            labelText: 'Time',
                                            suffixIcon:
                                                Icon(Icons.schedule_outlined)))
                                    : TextField(
                                        controller: controllers[field],
                                        maxLines: field == 'message' ||
                                                field == 'notes'
                                            ? 3
                                            : 1,
                                        decoration: InputDecoration(
                                            labelText: field[0].toUpperCase() +
                                                field.substring(1)))),
                    ]))),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Save'))
                ]));
    if (accepted != true) {
      return;
    }
    final data = <String, dynamic>{
      for (final field in fields) field: controllers[field]!.text.trim()
    };
    final requiredField = collection == 'facilitators' ? 'name' : 'title';
    if ((data[requiredField] ?? '').toString().isEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('$requiredField is required.')));
      }
      return;
    }
    if (collection == 'modules') {
      final facilitatorId = (data['facilitator'] ?? '').toString();
      final assigned = records['facilitators']!.where((row) => row['id'].toString() == facilitatorId).toList();
      data['facilitatorId'] = assigned.isEmpty ? '' : facilitatorId;
      data['facilitator'] = assigned.isEmpty
          ? 'Not specified'
          : (assigned.first['data']['name'] ?? 'Not specified').toString();
    }
    try {
      final id = collection == 'modules'
          ? data['code']?.toString() ?? ''
          : '${collection.substring(0, 3)}-${DateTime.now().microsecondsSinceEpoch}';
      if (id.isEmpty) {
        throw Exception('Module code is required.');
      }
      if (collection == 'modules' &&
          records['modules']!.any((row) => row['id'].toString() == id)) {
        throw Exception('That module code already exists.');
      }
      await api.save(collection, id, data);
      await refresh();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Saved and shared with everyone.')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  int? _clockMinutes(String value) {
    final match = RegExp(r'^(\d{1,2}):(\d{2})$').firstMatch(value);
    if (match == null) {
      return null;
    }
    final hour = int.parse(match.group(1)!);
    final minute = int.parse(match.group(2)!);
    if (hour > 23 || minute > 59) {
      return null;
    }
    return hour * 60 + minute;
  }

  String _clockText(int minutes) =>
      '${(minutes ~/ 60).toString().padLeft(2, '0')}:${(minutes % 60).toString().padLeft(2, '0')}';

  Map<String, dynamic>? _sessionFromRow(dynamic source) {
    final row = Map<String, dynamic>.from(source as Map);
    final data = Map<String, dynamic>.from(row['data'] ?? {});
    final id = row['id'].toString();
    final parts = id.split('_');
    int? dayIndex;
    String? startTime = data['startTime']?.toString();
    String? endTime = data['endTime']?.toString();
    if (parts.length == 2 && int.tryParse(parts[0]) != null && int.tryParse(parts[1]) != null) {
      final slot = int.parse(parts[0]);
      dayIndex = int.parse(parts[1]);
      if (slot < 0 || slot >= 7 || dayIndex < 0 || dayIndex >= 5) {
        return null;
      }
      final legacyTimes = [
        '08:00 – 10:00', '10:00 – 12:00', '12:00 – 13:30',
        '13:30 – 15:30', '15:30 – 17:30', '17:30 – 19:00', '19:00 – 21:00'
      ];
      final label = data['timeLabel']?.toString() ?? '';
      final range = RegExp(r'^(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})$').firstMatch(label);
      final fallback = legacyTimes[slot].split(' – ');
      startTime ??= range?.group(1) ?? fallback[0];
      endTime ??= range?.group(2) ?? fallback[1];
    } else {
      dayIndex = int.tryParse(data['dayIndex']?.toString() ?? '');
      if (dayIndex == null || dayIndex < 0 || dayIndex >= 5) {
        return null;
      }
      startTime ??= '08:00';
      endTime ??= '10:00';
    }
    final start = _clockMinutes(startTime ?? '');
    final end = _clockMinutes(endTime ?? '');
    if (start == null || end == null || end <= start) {
      return null;
    }
    final moduleCode = (data['moduleCode'] ?? '').toString();
    final code = moduleCode.isNotEmpty ? moduleCode : (data['code'] ?? '').toString();
    final module = records['modules']!.where((item) => item['id'].toString() == code).toList();
    final moduleData = module.isEmpty ? <String, dynamic>{} : Map<String, dynamic>.from(module.first['data'] ?? {});
    final configuredLecturer = (moduleData['facilitator'] ?? data['facilitator'] ?? '').toString();
    final configuredLecturerId = (moduleData['facilitatorId'] ?? '').toString();
    final lecturerRecord = records['facilitators']!.where((item) {
      final facilitator = Map<String, dynamic>.from(item['data'] ?? {});
      return item['id'].toString() == configuredLecturerId ||
          item['id'].toString() == configuredLecturer ||
          facilitator['name']?.toString().toLowerCase() == configuredLecturer.toLowerCase();
    }).toList();
    final lecturer = lecturerRecord.isNotEmpty
        ? (lecturerRecord.first['data']['name'] ?? '').toString()
        : configuredLecturer;
    return {
      'id': id,
      'row': row,
      'data': data,
      'dayIndex': dayIndex,
      'startTime': startTime,
      'endTime': endTime,
      'startMinutes': start,
      'endMinutes': end,
      'code': code,
      'title': (data['title'] ?? moduleData['title'] ?? data['code'] ?? data['text'] ?? 'Scheduled session').toString(),
      'lecturer': lecturer == 'Not specified' ? '' : lecturer,
    };
  }

  List<Map<String, dynamic>> _sessionEntries() {
    final entries = <Map<String, dynamic>>[];
    for (final row in records['cells']!) {
      final entry = _sessionFromRow(row);
      if (entry != null) {
        entries.add(entry);
      }
    }
    if (!entries.any((item) => item['title'] == 'Journal Club' && item['dayIndex'] == 1)) {
      entries.add({
        'id': 'journal-club-fixed', 'dayIndex': 1, 'startTime': '13:00',
        'endTime': '14:00', 'startMinutes': 780, 'endMinutes': 840,
        'title': 'Journal Club', 'lecturer': '', 'fixed': true,
      });
    }
    entries.sort((a, b) => (a['dayIndex'] as int).compareTo(b['dayIndex'] as int) != 0
        ? (a['dayIndex'] as int).compareTo(b['dayIndex'] as int)
        : (a['startMinutes'] as int).compareTo(b['startMinutes'] as int));
    return entries;
  }

  Future<void> addSession({Map<String, dynamic>? existingRow}) async {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    final existing = existingRow == null ? null : _sessionFromRow(existingRow);
    final activity = TextEditingController(text: existing?['code']?.toString() ?? '');
    final title = TextEditingController(text: existing?['title']?.toString() ?? '');
    final start = TextEditingController(text: existing?['startTime']?.toString() ?? '08:00');
    final end = TextEditingController(text: existing?['endTime']?.toString() ?? '10:00');
    var day = existing?['dayIndex'] as int? ?? 0;
    var selectedModule = records['modules']!.any((row) => row['id'].toString() == (existing?['code']?.toString() ?? '')) ? (existing?['code']?.toString() ?? '') : '';
    var mode = (existing?['data']?['mode'] ?? 'unspecified').toString();
    var colour = (existing?['data']?['colour'] ?? '').toString();
    String lecturerFor(String code) {
      final matches = records['modules']!.where((row) => row['id'].toString() == code).toList();
      if (matches.isEmpty) {
        return '';
      }
      final moduleData = Map<String, dynamic>.from(matches.first['data'] ?? {});
      final configured = (moduleData['facilitator'] ?? '').toString();
      final configuredId = (moduleData['facilitatorId'] ?? '').toString();
      final people = records['facilitators']!.where((row) {
        final d = Map<String, dynamic>.from(row['data'] ?? {});
        return row['id'].toString() == configuredId || row['id'].toString() == configured || d['name']?.toString().toLowerCase() == configured.toLowerCase();
      }).toList();
      if (people.isNotEmpty) {
        return (people.first['data']['name'] ?? '').toString();
      }
      return configured == 'Not specified' ? '' : configured;
    }
    final accepted = await showDialog<bool>(
        context: context,
        builder: (dialogContext) => StatefulBuilder(
            builder: (context, setDialogState) => AlertDialog(
                    title: Text(existing == null ? 'Add timetable session' : 'Edit timetable session'),
                    content: SizedBox(
                        width: 440,
                        child: SingleChildScrollView(
                            child: Column(mainAxisSize: MainAxisSize.min, children: [
                              DropdownButtonFormField<int>(
                                  initialValue: day,
                                  decoration: const InputDecoration(labelText: 'Weekday'),
                                  items: [for (var i = 0; i < days.length; i++) DropdownMenuItem(value: i, child: Text(days[i]))],
                                  onChanged: (value) => setDialogState(() => day = value ?? 0)),
                              TextField(
                                  controller: start, readOnly: true,
                                  onTap: () async { await _pickTime(dialogContext, start); setDialogState(() {}); },
                                  decoration: const InputDecoration(labelText: 'Start time', suffixIcon: Icon(Icons.schedule_outlined))),
                              TextField(
                                  controller: end, readOnly: true,
                                  onTap: () async { await _pickTime(dialogContext, end); setDialogState(() {}); },
                                  decoration: const InputDecoration(labelText: 'End time', suffixIcon: Icon(Icons.schedule_outlined))),
                              DropdownButtonFormField<String>(
                                  initialValue: selectedModule,
                                  decoration: const InputDecoration(labelText: 'Module (optional)'),
                                  items: [
                                    const DropdownMenuItem(value: '', child: Text('Other activity')),
                                    for (final row in records['modules']!)
                                      DropdownMenuItem(value: row['id'].toString(), child: Text(row['id'].toString()))
                                  ],
                                  onChanged: (value) => setDialogState(() => selectedModule = value ?? '')),
                              TextField(controller: activity, decoration: const InputDecoration(labelText: 'Activity label (required if no module)')),
                              TextField(controller: title, decoration: const InputDecoration(labelText: 'Session title (optional)')),
                              Align(alignment: Alignment.centerLeft, child: Padding(
                                  padding: const EdgeInsets.only(top: 8),
                                  child: Text('Lecturer: ${selectedModule.isEmpty ? 'Not assigned' : (lecturerFor(selectedModule).isEmpty ? 'Not assigned' : lecturerFor(selectedModule))}', style: const TextStyle(color: Color(0xFFC7A45B))))),
                              DropdownButtonFormField<String>(
                                  initialValue: mode,
                                  decoration: const InputDecoration(labelText: 'Delivery mode'),
                                  items: const [
                                    DropdownMenuItem(value: 'unspecified', child: Text('Not specified')),
                                    DropdownMenuItem(value: 'online', child: Text('Online')),
                                    DropdownMenuItem(value: 'face_to_face', child: Text('Face-to-face')),
                                  ],
                                  onChanged: (value) => setDialogState(() => mode = value ?? 'unspecified')),
                              DropdownButtonFormField<String>(
                                  initialValue: colour,
                                  decoration: const InputDecoration(labelText: 'Entry colour'),
                                  items: const [
                                    DropdownMenuItem(value: '', child: Text('No colour — use current theme')),
                                    DropdownMenuItem(value: '#2F5D8C', child: Text('Navy blue')),
                                    DropdownMenuItem(value: '#3C7A5A', child: Text('Green')),
                                    DropdownMenuItem(value: '#8A6D2F', child: Text('Gold')),
                                    DropdownMenuItem(value: '#7B3F61', child: Text('Plum')),
                                    DropdownMenuItem(value: '#4B5D7A', child: Text('Slate')),
                                  ],
                                  onChanged: (value) => setDialogState(() => colour = value ?? '')),
                            ]))),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
                      FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Save session')),
                    ])));
    if (accepted != true) {
      return;
    }
    final label = selectedModule.isEmpty ? activity.text.trim() : selectedModule;
    final startMinutes = _clockMinutes(start.text), endMinutes = _clockMinutes(end.text);
    if (label.isEmpty || startMinutes == null || endMinutes == null || endMinutes <= startMinutes) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Enter an activity and choose an end time later than the start time.')));
      }
      return;
    }
    final conflict = _sessionEntries().where((item) => item['id'] != (existing?['id'] ?? '') && item['dayIndex'] == day && startMinutes < (item['endMinutes'] as int) && endMinutes > (item['startMinutes'] as int)).toList();
    if (conflict.isNotEmpty) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('This overlaps ${conflict.first['title']} (${conflict.first['startTime']}–${conflict.first['endTime']}).')));
      }
      return;
    }
    final moduleRows = records['modules']!.where((row) => row['id'].toString() == selectedModule).toList();
    final moduleData = moduleRows.isEmpty ? <String, dynamic>{} : Map<String, dynamic>.from(moduleRows.first['data'] ?? {});
    final lecturer = selectedModule.isEmpty ? '' : lecturerFor(selectedModule);
    final oldId = existing?['id']?.toString();
    var id = oldId ?? 'session-${DateTime.now().microsecondsSinceEpoch}';
    if (oldId != null && RegExp(r'^\d+_\d+$').hasMatch(oldId) && day != existing?['dayIndex']) {
      id = 'session-${DateTime.now().microsecondsSinceEpoch}';
    }
    try {
      await api.save('cells', id, {
        'dayIndex': day, 'startTime': start.text, 'endTime': end.text,
        'moduleCode': selectedModule, 'code': label,
        'title': title.text.trim().isNotEmpty ? title.text.trim() : (moduleData['title'] ?? (activity.text.trim().isNotEmpty ? activity.text.trim() : label)),
        'facilitator': lecturer, 'mode': mode, if (colour.isNotEmpty) 'colour': colour
      });
      if (oldId != null && oldId != id) {
        await api.remove('cells', oldId);
      }
      await refresh();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> removeRecord(String collection, String id) async {
    final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
                title: const Text('Remove shared record?'),
                content: const Text('This removes the record for all users.'),
                actions: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel')),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Remove'))
                ]));
    if (yes != true) {
      return;
    }
    try {
      await api.remove(collection, id);
      await refresh();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  void selectPage(int index, {bool closeDrawer = true}) {
    if (closeDrawer) {
      Navigator.pop(context);
    }
    if (index == 9) {
      openAnalytics();
      return;
    }
    setState(() => selected = index);
  }

  @override
  Widget build(BuildContext context) {
    const canAnalytics = true;
    return Scaffold(
      appBar: AppBar(
          titleSpacing: 18,
          title: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('PhD in Maternal and Neonatal Health : 3rd Block',
                    style:
                        TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                Text('Academic Calendar 2026',
                    style: TextStyle(fontSize: 11, color: Color(0xFFC7A45B)))
              ]),
          actions: [
            IconButton(
                tooltip: 'Refresh',
                onPressed: refresh,
                icon: const Icon(Icons.refresh))
          ]),
      drawer: Drawer(
          child: SafeArea(
              child: Column(children: [
        const Padding(
            padding: EdgeInsets.fromLTRB(20, 20, 16, 14),
            child: Row(children: [
              Icon(Icons.calendar_month_outlined,
                  color: Color(0xFFC7A45B), size: 25),
              SizedBox(width: 12),
              Expanded(
                  child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                    Text('MNH CALENDAR',
                        style: TextStyle(
                            fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                    Text('Academic workspace',
                        style: TextStyle(fontSize: 11, color: Colors.white60))
                  ]))
            ])),
        const Divider(height: 1),
        Expanded(
            child: ListView(
                padding: const EdgeInsets.symmetric(vertical: 8),
                children: [
              for (var i = 2; i < _labels.length - 1; i++)
                if (i != 3 && i != 9)
                  ListTile(
                      selected: selected == i,
                      leading: Icon(_icons[i]),
                      title: Text(_labels[i]),
                      onTap: () => selectPage(i),
                      dense: true,
                      minLeadingWidth: 24),
            ])),
        const Divider(height: 1),
        ListTile(
            selected: selected == 12,
            leading: Icon(_icons[12]),
            title: const Text('Settings'),
            onTap: () => selectPage(12)),
        Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            child: Text(
                editing
                    ? 'Editing access: ${_roleLabel(role)}'
                    : 'Viewing access',
                style: const TextStyle(color: Colors.white54, fontSize: 11))),
      ]))),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? _errorView()
              : RefreshIndicator(
                  onRefresh: refresh,
                  child: ListView(
                      padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                      children: [
                        Row(children: [
                          Expanded(
                              child: Text(_labels[selected],
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleLarge
                                      ?.copyWith(fontWeight: FontWeight.w700))),
                          const Chip(
                              label: Text('Open access'),
                              avatar: Icon(Icons.public, size: 16))
                        ]),
                        const SizedBox(height: 8),
                        Wrap(spacing: 8, runSpacing: 8, children: [
                          ChoiceChip(
                              label: const Text('Dashboard'),
                              selected: selected == 0,
                              onSelected: (_) =>
                                  selectPage(0, closeDrawer: false)),
                          ChoiceChip(
                              label: const Text('Weekly Schedule'),
                              selected: selected == 1,
                              onSelected: (_) =>
                                  selectPage(1, closeDrawer: false)),
                          ChoiceChip(
                              label: const Text('Upcoming Academic Activities'),
                              selected: selected == 3,
                              onSelected: (_) =>
                                  selectPage(3, closeDrawer: false)),
                          ChoiceChip(
                              label: const Text('Analytics'),
                              selected: selected == 9,
                              onSelected: (_) => openAnalytics()),
                        ]),
                        const SizedBox(height: 8),
                        ..._pageContent(canAnalytics),
                        const SizedBox(height: 26),
                        Center(
                            child: Text(
                                'Penrose ScholarMW  ·  Advancing academic excellence',
                                style: TextStyle(
                                    color: Colors.white.withValues(alpha: .42),
                                    fontSize: 11))),
                      ])),
    );
  }

  List<Widget> _pageContent(bool canAnalytics) {
    switch (selected) {
      case 0:
        return _dashboard();
      case 1:
        return _timetable();
      case 2:
        return _monthly();
      case 3:
        return _upcoming();
      case 4:
        return _managed('modules');
      case 5:
        return _managed('facilitators');
      case 6:
        return _managed('examinations');
      case 7:
        return _managed('recurring');
      case 8:
        return _managed('communications');
      case 9:
        return _analytics();
      case 10:
        return _history();
      case 11:
        return _exports();
      case 12:
        return _settings();
      default:
        return _dashboard();
    }
  }

  List<Widget> _dashboard() => [
        Text('Shared academic workspace',
            style: TextStyle(color: Colors.white.withValues(alpha: .65))),
        const SizedBox(height: 14),
        GridView.count(
            crossAxisCount: MediaQuery.of(context).size.width > 650 ? 4 : 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            childAspectRatio: 1.25,
            children: [
              _metric('Modules', '${records['modules']!.length}',
                  Icons.menu_book_outlined),
              _metric('Scheduled sessions', '${records['cells']!.length}',
                  Icons.calendar_month_outlined),
              _metric('Examinations', '${records['examinations']!.length}',
                  Icons.school_outlined),
              _metric('Backups', '${health['backup_count'] ?? 0}',
                  Icons.backup_outlined),
            ]),
        const SizedBox(height: 18),
        _panel('Upcoming academic activities', _upcoming().take(5).toList()),
        const SizedBox(height: 14),
        _panel('Recent additions', _history().take(5).toList()),
      ];

  Widget _metric(String title, String value, IconData icon) => Card(
      child: Padding(
          padding: const EdgeInsets.all(14),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(icon, color: const Color(0xFFC7A45B)),
            const Spacer(),
            Text(value,
                style:
                    const TextStyle(fontSize: 25, fontWeight: FontWeight.bold)),
            Text(title,
                style: const TextStyle(fontSize: 12, color: Colors.white70))
          ])));

  List<Widget> _managed(String collection) {
    final rows = records[collection] ?? [];
    final widgets = <Widget>[];
    if (editing && collection != 'modules') {
      widgets.add(Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
              onPressed: () => addRecord(collection),
              icon: const Icon(Icons.add),
              label: const Text('Add record'))));
    }
    if (collection == 'modules' && editing) {
      widgets.add(Align(
          alignment: Alignment.centerRight,
          child: FilledButton.icon(
              onPressed: () => addRecord('modules'),
              icon: const Icon(Icons.add),
              label: const Text('Add module'))));
    }
    if (rows.isEmpty) {
      widgets.add(_panel('No records yet',
          [const Text('No shared records have been added.')]));
    }
    for (final row in rows) {
      final data = Map<String, dynamic>.from(row['data'] ?? {});
      final title = (data['title'] ?? data['name'] ?? row['id']).toString();
      final subtitle = data.entries
          .where((e) =>
              e.key != 'title' &&
              e.key != 'name' &&
              e.value.toString().isNotEmpty)
          .map((e) => '${e.key}: ${e.value}')
          .join(' · ');
      widgets.add(Card(
          child: ListTile(
              title: Text(title),
              subtitle: subtitle.isEmpty ? null : Text(subtitle),
              trailing: editing
                  ? IconButton(
                      tooltip: 'Remove',
                      icon: const Icon(Icons.delete_outline),
                      onPressed: () =>
                          removeRecord(collection, row['id'].toString()))
                  : null,
              onTap: collection == 'communications'
                  ? () async {
                      await Clipboard.setData(ClipboardData(
                          text:
                              '${data['title'] ?? ''}\n${data['message'] ?? ''}\n${data['url'] ?? ''}'));
                      if (mounted) {
                        ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                                content: Text('Communication copied.')));
                      }
                    }
                  : null)));
    }
    return widgets;
  }

  List<Widget> _timetable() {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    final entries = _sessionEntries();
    final grouped = <int, List<Map<String, dynamic>>>{};
    for (final entry in entries) {
      grouped.putIfAbsent(entry['dayIndex'] as int, () => []).add(entry);
    }
    return [
      Text('Week beginning Monday, 9 November 2026',
          style: TextStyle(color: Colors.white.withValues(alpha: .65))),
      const SizedBox(height: 8),
      if (editing)
        Align(alignment: Alignment.centerRight,
            child: FilledButton.icon(onPressed: () => addSession(), icon: const Icon(Icons.add), label: const Text('Add session'))),
      for (var day = 0; day < days.length; day++)
        Card(child: Padding(padding: const EdgeInsets.all(14), child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('${days[day]} ${DateFormat('d MMM yyyy').format(DateTime(2026, 11, 9 + day))}',
                style: const TextStyle(color: Color(0xFFC7A45B), fontWeight: FontWeight.bold)),
            for (final item in (grouped[day] ?? [])..sort((a, b) => (a['startMinutes'] as int).compareTo(b['startMinutes'] as int)))
              ListTile(
                dense: true, contentPadding: EdgeInsets.zero,
                title: Text(item['title'].toString()),
                subtitle: Text('${item['startTime']}–${item['endTime']}${(item['lecturer'] as String).isNotEmpty ? ' · ${item['lecturer']}' : ''}'),
                onTap: editing && item['row'] != null ? () => addSession(existingRow: Map<String, dynamic>.from(item['row'] as Map)) : null,
                trailing: editing && item['id'] != 'journal-club-fixed'
                    ? IconButton(tooltip: 'Remove session', icon: const Icon(Icons.delete_outline), onPressed: () => removeRecord('cells', item['id'].toString()))
                    : null,
              ),
            if ((grouped[day] ?? []).isEmpty) const Text('No sessions scheduled', style: TextStyle(color: Colors.white54, fontSize: 12)),
          ],
        ))),
    ];
  }

  List<Widget> _monthly() {
    final entriesByDay = <int, int>{};
    for (final entry in _sessionEntries()) {
      final date = DateTime(2026, 11, 9 + (entry['dayIndex'] as int)).day;
      entriesByDay[date] = (entriesByDay[date] ?? 0) + 1;
    }
    return [
      const Text('November 2026 · Weekdays', style: TextStyle(color: Color(0xFFC7A45B), fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      Row(children: [for (final label in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']) Expanded(child: Center(child: Text(label, style: const TextStyle(color: Color(0xFFC7A45B), fontSize: 11, fontWeight: FontWeight.bold))))]),
      const SizedBox(height: 4),
      GridView.count(crossAxisCount: 5, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(), childAspectRatio: .9,
        children: [for (final day in List<int>.generate(30, (i) => i + 1).where((day) => DateTime(2026, 11, day).weekday <= 5)) Card(child: Padding(padding: const EdgeInsets.all(5), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('$day', style: const TextStyle(fontWeight: FontWeight.bold)),
          if (entriesByDay.containsKey(day)) Text('${entriesByDay[day]} session(s)', style: const TextStyle(color: Color(0xFFC7A45B), fontSize: 9)),
        ])))]),
      const SizedBox(height: 8),
      const Text('The teaching week is Monday 9 to Friday 13 November 2026. Other dates populate when dated records are added.'),
    ];
  }

  List<Widget> _upcoming() {
    const days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
    final rows = <Widget>[];
    for (final entry in _sessionEntries()) {
      final day = entry['dayIndex'] as int;
      final date = DateTime(2026, 11, 9 + day);
      rows.add(ListTile(
        dense: true,
        leading: const Icon(Icons.event_outlined, color: Color(0xFFC7A45B)),
        title: Text(entry['title'].toString()),
        subtitle: Text('${days[day]} ${DateFormat('d MMM yyyy').format(date)} · ${entry['startTime']}–${entry['endTime']}${(entry['lecturer'] as String).isNotEmpty ? ' · ${entry['lecturer']}' : ''}'),
      ));
    }
    for (final row in records['examinations']!) {
      final d = row['data'] ?? {};
      rows.add(ListTile(leading: const Icon(Icons.school_outlined), title: Text((d['title'] ?? 'Examination').toString()), subtitle: Text([d['date'], d['time'], d['venue']].where((x) => x != null && x.toString().isNotEmpty).join(' · '))));
    }
    for (final row in records['recurring']!) {
      final d = row['data'] ?? {};
      final recurringTitle = (d['title'] ?? 'Recurring activity').toString();
      if ((d['day'] ?? '').toString().trim().toLowerCase() == 'saturday' ||
          (d['day'] ?? '').toString().trim().toLowerCase() == 'sat') {
        continue;
      }
      if (recurringTitle == 'Journal Club' &&
          _sessionEntries().any((entry) => entry['title'] == 'Journal Club')) {
        continue;
      }
      rows.add(ListTile(leading: const Icon(Icons.repeat), title: Text(recurringTitle), subtitle: Text([d['frequency'], d['day'], d['time']].where((x) => x != null && x.toString().isNotEmpty).join(' · '))));
    }
    return rows.isEmpty ? [const Text('No upcoming activities have been recorded.')] : rows;
  }

  List<Widget> _analytics() {
    if (analytics['error'] != null) {
      return [Text(analytics['error'].toString())];
    }
    final counts = Map<String, dynamic>.from(analytics['counts'] ?? {});
    final modes = Map<String, dynamic>.from(analytics['delivery_modes'] ?? {});
    return [
      GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 1.8,
          children: counts.entries
              .map(
                  (e) => _metric(e.key, '${e.value}', Icons.analytics_outlined))
              .toList()),
      _panel('Online vs face-to-face sessions', [
        _bar('Online', (modes['online'] as num?)?.toInt() ?? 0),
        _bar('Face-to-face', (modes['face_to_face'] as num?)?.toInt() ?? 0),
        _bar('Unspecified', (modes['unspecified'] as num?)?.toInt() ?? 0),
      ]),
      _panel('Attendance and concerns', [
        Text(analytics['note']?.toString() ??
            'Attendance data is not yet available.'),
        const Text(
            'Missed sessions: not measurable until attendance is recorded.')
      ]),
    ];
  }

  int _modeTotal() {
    final values = Map<String, dynamic>.from(analytics['delivery_modes'] ?? {});
    return values.values
        .fold<int>(0, (total, item) => total + (item as num).toInt());
  }

  Widget _bar(String label, int value) {
    final total = _modeTotal();
    return ListTile(
        title: Text('$label · $value'),
        subtitle:
            LinearProgressIndicator(value: total == 0 ? 0.0 : value / total),
        dense: true);
  }

  List<Widget> _history() => history.isEmpty
      ? [const Text('No new sessions or activities have been recorded.')]
      : history.map((row) {
          final at = DateTime.fromMillisecondsSinceEpoch(
              (row['at'] as num?)?.toInt() ?? 0);
          return ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.add_circle_outline,
                  color: Color(0xFFC7A45B)),
              title: Text(row['summary']?.toString() ?? 'Added an item'),
              subtitle: Text(
                  '${row['role'] ?? 'Staff'} · ${DateFormat('d MMM yyyy, HH:mm').format(at)}'));
        }).toList();

  List<Widget> _exports() => [
        _panel('Share calendar data', [
          FilledButton.icon(
              onPressed: () async {
                final data = await api.backup();
                await Clipboard.setData(ClipboardData(
                    text: const JsonEncoder.withIndent('  ').convert(data)));
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                      content: Text('JSON backup copied to clipboard.')));
                }
              },
              icon: const Icon(Icons.copy),
              label: const Text('Copy shared JSON backup')),
          OutlinedButton.icon(
              onPressed: () async {
                final lines = [
                  'id,title,details',
                  ...records.entries.expand((entry) => entry.value.map((r) =>
                      '${r['id']},${(r['data']['title'] ?? r['data']['name'] ?? '').toString().replaceAll(',', ' ')},${jsonEncode(r['data'])}'))
                ];
                await Clipboard.setData(ClipboardData(text: lines.join('\n')));
                if (mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
                      content: Text('Calendar CSV copied to clipboard.')));
                }
              },
              icon: const Icon(Icons.table_chart_outlined),
              label: const Text('Copy calendar CSV')),
          Text(
              'Backups are copied from the shared server. Use the web Settings page to restore a backup.',
              style: TextStyle(
                  color: Colors.white.withValues(alpha: .6), fontSize: 12)),
        ])
      ];

  List<Widget> _settings() => [
        _panel('Access and security', [
          const Text('Open access is enabled. Anyone with the app or website link can view and change shared programme records and view Analytics.'),
        ]),
        _panel('Server and backups', [
          Text('Shared records: ${health['documents'] ?? '—'}'),
          Text('Automatic backups: ${health['backup_count'] ?? '—'}'),
          Text(
              'Latest backup: ${health['last_backup'] == null ? 'Pending' : DateTime.fromMillisecondsSinceEpoch(((health['last_backup'] as num).toDouble() * 1000).round()).toLocal()}'),
          TextButton.icon(
              onPressed: refresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh server status')),
        ]),
      ];

  Widget _panel(String title, List<Widget> children) => Card(
      child: Padding(
          padding: const EdgeInsets.all(16),
          child:
              Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title,
                style:
                    const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
            const SizedBox(height: 10),
            ...children
          ])));
  String _roleLabel(String value) =>
      {
        'administrator': 'Rep',
        'lecturer': 'Staff',
        'hod': 'HOD',
        'coordinator': 'Coordinator',
        'executive_dean': 'Executive Dean',
        'public': 'Open access'
      }[value] ??
      value;
  Widget _errorView() => Center(
      child: Padding(
          padding: const EdgeInsets.all(28),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.cloud_off_outlined,
                size: 42, color: Color(0xFFC7A45B)),
            const SizedBox(height: 14),
            const Text('Calendar server unavailable',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(error!,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white70)),
            const SizedBox(height: 16),
            FilledButton.icon(
                onPressed: refresh,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'))
          ])));
}
