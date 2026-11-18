import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

class MeetingAlarmService {
  MeetingAlarmService._();
  static final instance = MeetingAlarmService._();
  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _ready = false;
  static const channelId = 'mnh_meeting_alarms';
  static const channelName = 'Meeting alarms';

  Future<void> initialize() async {
    if (_ready || kIsWeb) return;
    tzdata.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Africa/Blantyre'));
    const settings = InitializationSettings(android: AndroidInitializationSettings('@mipmap/ic_launcher'));
    await _plugin.initialize(settings: settings);
    final android = _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>();
    await android?.requestNotificationsPermission();
    await android?.requestExactAlarmsPermission();
    await android?.createNotificationChannel(const AndroidNotificationChannel(
      channelId, channelName, description: 'Audible reminders five minutes before MNH meetings',
      importance: Importance.max, playSound: true, enableVibration: true));
    _ready = true;
  }

  int _id(String value) {
    var hash = 0x811c9dc5;
    for (final unit in value.codeUnits) { hash = ((hash ^ unit) * 0x01000193) & 0x7fffffff; }
    return hash;
  }

  Future<void> synchronize({required List<dynamic> cellRows, required DateTime currentWeekMonday}) async {
    if (kIsWeb) return;
    await initialize();
    await _plugin.cancelAll();
    final now = tz.TZDateTime.now(tz.local);
    final horizon = now.add(const Duration(days: 35));
    Future<void> schedule(String key, String title, DateTime meeting) async {
      final fireAt = meeting.subtract(const Duration(minutes: 5));
      if (!fireAt.isAfter(now) || meeting.isAfter(horizon)) return;
      final meetingTime = '${meeting.hour.toString().padLeft(2, "0")}:${meeting.minute.toString().padLeft(2, "0")}';
      await _plugin.zonedSchedule(
        id: _id(key),
        title: 'Meeting in 5 minutes',
        body: '$title starts at $meetingTime',
        scheduledDate: tz.TZDateTime.from(fireAt, tz.local),
        notificationDetails: const NotificationDetails(android: AndroidNotificationDetails(
          channelId, channelName, channelDescription: 'Audible reminders five minutes before meetings',
          importance: Importance.max, priority: Priority.max, category: AndroidNotificationCategory.alarm,
          playSound: true, enableVibration: true, audioAttributesUsage: AudioAttributesUsage.alarm)),
        androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle, payload: key);
    }

    for (final raw in cellRows) {
      if (raw is! Map) continue;
      final row = Map<String, dynamic>.from(raw);
      final data = Map<String, dynamic>.from(row['data'] ?? const {});
      final day = int.tryParse((data['dayIndex'] ?? '').toString());
      final time = (data['startTime'] ?? '').toString().split(':');
      if (day == null || day < 0 || day > 4 || time.length != 2) continue;
      final hour = int.tryParse(time[0]), minute = int.tryParse(time[1]);
      if (hour == null || minute == null || hour > 23 || minute > 59) continue;
      final title = (data['title'] ?? data['code'] ?? 'Scheduled meeting').toString();
      if (title == 'Journal Club' || title == 'Seminar in MNH') continue;
      final saved = DateTime.tryParse((data['weekStart'] ?? '').toString());
      final monday = saved == null ? currentWeekMonday : DateTime(saved.year, saved.month, saved.day);
      final date = monday.add(Duration(days: day));
      final rowId = row['id'].toString();
      await schedule('cell:$rowId:${date.toIso8601String()}', title,
        DateTime(date.year, date.month, date.day, hour, minute));
    }

    final recurring = [
      (id: 'journal-club', title: 'Journal Club', weekday: 2, hour: 13, minute: 0),
      (id: 'mnh-seminar', title: 'Seminar in MNH', weekday: 4, hour: 10, minute: 0),
    ];
    for (final item in recurring) {
      var date = DateTime(now.year, now.month, now.day);
      while (date.weekday != item.weekday) { date = date.add(const Duration(days: 1)); }
      for (var week = 0; week < 6; week++) {
        final d = date.add(Duration(days: 7 * week));
        await schedule('recurring:${item.id}:${d.toIso8601String()}', item.title,
          DateTime(d.year, d.month, d.day, item.hour, item.minute));
      }
    }
  }
}
