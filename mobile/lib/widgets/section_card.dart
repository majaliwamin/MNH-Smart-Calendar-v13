import 'package:flutter/material.dart';

class SectionCard extends StatelessWidget {
  const SectionCard({super.key, required this.title, required this.value, required this.caption, required this.icon});
  final String title;
  final String value;
  final String caption;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Card(
    child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start,
      children: [Icon(icon, color: const Color(0xFFC7A45B), size: 20), const SizedBox(height: 14),
        Text(value, style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w700)),
        const SizedBox(height: 4), Text(title, style: const TextStyle(fontWeight: FontWeight.w600)),
        const SizedBox(height: 3), Text(caption, style: TextStyle(color: Colors.white.withValues(alpha: .58), fontSize: 12))])));
}

