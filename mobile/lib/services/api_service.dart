import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  ApiService._();
  static final ApiService instance = ApiService._();
  static const String baseUrl = String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://10.0.2.2:8000');

  Map<String, String> _headers() => {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      };

  Future<dynamic> _request(String method, String path, {Object? body}) async {
    final uri = Uri.parse('$baseUrl$path');
    final headers = _headers();
    late http.Response response;
    switch (method) {
      case 'POST': response = await http.post(uri, headers: headers, body: jsonEncode(body ?? {})); break;
      case 'PUT': response = await http.put(uri, headers: headers, body: jsonEncode(body ?? {})); break;
      case 'DELETE': response = await http.delete(uri, headers: headers); break;
      default: response = await http.get(uri, headers: headers);
    }
    final data = response.body.isEmpty ? <String, dynamic>{} : jsonDecode(response.body);
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(data is Map ? (data['error'] ?? 'Request failed (${response.statusCode})') : 'Request failed');
    }
    return data;
  }

  Future<Map<String, dynamic>> health() async => Map<String, dynamic>.from(await _request('GET', '/api/health'));
  Future<Map<String, dynamic>> session() async => Map<String, dynamic>.from(await _request('GET', '/api/session'));
  Future<List<dynamic>> collection(String name) async => List<dynamic>.from(await _request('GET', '/api/col/$name'));
  Future<List<dynamic>> history() async => List<dynamic>.from(await _request('GET', '/api/history'));
  Future<Map<String, dynamic>> analytics() async => Map<String, dynamic>.from(await _request('GET', '/api/analytics'));
  Future<Map<String, dynamic>> backup() async => Map<String, dynamic>.from(await _request('GET', '/api/backup'));
  Future<void> save(String collection, String id, Map<String, dynamic> data) async { await _request('PUT', '/api/doc/${Uri.encodeComponent(collection)}/${Uri.encodeComponent(id)}', body: data); }
  Future<void> remove(String collection, String id) async { await _request('DELETE', '/api/doc/${Uri.encodeComponent(collection)}/${Uri.encodeComponent(id)}'); }

}
