import 'package:flutter/material.dart';
import 'screens/home_screen.dart';

class MnhCalendarApp extends StatelessWidget {
  const MnhCalendarApp({super.key});

  static const ink = Color(0xFF111827);
  static const gold = Color(0xFFC7A45B);

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MNH Calendar',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0B1220),
        colorScheme: ColorScheme.fromSeed(seedColor: gold, brightness: Brightness.dark,
          surface: const Color(0xFF111B2B)),
        appBarTheme: const AppBarTheme(backgroundColor: Color(0xFF0B1220), elevation: 0,
          surfaceTintColor: Colors.transparent),
        inputDecorationTheme: InputDecorationTheme(
          filled: true, fillColor: const Color(0xFF172438),
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none)),
      ),
      home: const HomeScreen(),
    );
  }
}
