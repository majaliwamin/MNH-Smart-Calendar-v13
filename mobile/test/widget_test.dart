import 'package:flutter_test/flutter_test.dart';
import 'package:mnh_calendar/app.dart';

void main() {
  testWidgets('MNH Calendar app loads successfully', (WidgetTester tester) async {
    await tester.pumpWidget(const MnhCalendarApp());

    expect(find.byType(MnhCalendarApp), findsOneWidget);
  });
}