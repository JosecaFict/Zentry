import 'dart:convert';
import 'dart:typed_data';

import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final assistantApiProvider = Provider<AssistantApi>(
  (ref) => AssistantApi(ref.watch(dioProvider)),
);

enum AssistantMode {
  customer('CLIENTE', 'Asesor de compras'),
  business('EMPRESA', 'Asistente de administración');

  const AssistantMode(this.code, this.title);
  final String code;
  final String title;

  bool allows(List<String>? roles) {
    if (roles == null || roles.contains('SUPERADMIN')) return false;
    return this == business
        ? roles.contains('ADMIN')
        : roles.contains('CLIENTE') && !roles.contains('ADMIN');
  }
}

class AssistantConversation {
  AssistantConversation(Map<String, dynamic> json)
    : id = json['id_conversacion'] as String,
      archived = json['estado'] == 'ARCHIVADA',
      updatedAt = DateTime.tryParse(json['updated_at'] as String? ?? '');

  final String id;
  final bool archived;
  final DateTime? updatedAt;
}

class AssistantMessage {
  AssistantMessage(Map<String, dynamic> json)
    : id = json['id_mensaje'] as int,
      fromUser = json['rol'] == 'USUARIO',
      content = json['contenido'] as String,
      exportable = json['reporte_exportable'] == true,
      products = (json['productos'] as List? ?? const [])
          .cast<Map<String, dynamic>>();

  final int id;
  final bool fromUser;
  final String content;
  final bool exportable;
  final List<Map<String, dynamic>> products;
}

class AssistantApi {
  AssistantApi(this._dio);

  final Dio _dio;
  static const _base = '/assistant/conversations';
  static final _longRequest = Options(
    receiveTimeout: const Duration(seconds: 90),
  );

  Future<List<AssistantConversation>> conversations(AssistantMode mode) =>
      _request(() async {
        final data = (await _dio.get<List<dynamic>>(_base)).data!;
        return data
            .cast<Map<String, dynamic>>()
            .where((item) => item['modo'] == mode.code)
            .map(AssistantConversation.new)
            .toList();
      });

  Future<AssistantConversation> create(AssistantMode mode) =>
      _request(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          _base,
          data: {'modo': mode.code},
        );
        return AssistantConversation(response.data!);
      });

  Future<List<AssistantMessage>> messages(String id) => _request(() async {
    final data = (await _dio.get<List<dynamic>>('$_base/$id/messages')).data!;
    return data.cast<Map<String, dynamic>>().map(AssistantMessage.new).toList();
  });

  Future<List<AssistantMessage>> send(String id, String content) =>
      _request(() async {
        final response = await _dio.post<Map<String, dynamic>>(
          '$_base/$id/messages',
          data: {'contenido': content},
          options: _longRequest,
        );
        final data = response.data!;
        return [
          AssistantMessage(data['usuario'] as Map<String, dynamic>),
          AssistantMessage(data['asistente'] as Map<String, dynamic>),
        ];
      });

  Future<void> archive(String id) => _request(() async {
    await _dio.post<void>('$_base/$id/archive');
  });

  Future<String> transcribe(String path) => _request(() async {
    final response = await _dio.post<Map<String, dynamic>>(
      '/assistant/transcribe',
      data: FormData.fromMap({
        'audio': await MultipartFile.fromFile(
          path,
          filename: 'consulta.m4a',
          contentType: DioMediaType('audio', 'mp4'),
        ),
      }),
      options: _longRequest,
    );
    return response.data!['texto'] as String;
  });

  Future<Uint8List> export(String id, int message, String format) =>
      _request(() async {
        final response = await _dio.get<List<int>>(
          '$_base/$id/messages/$message/export/$format',
          options: Options(responseType: ResponseType.bytes),
        );
        return Uint8List.fromList(response.data!);
      });

  Future<T> _request<T>(Future<T> Function() call) async {
    try {
      return await call();
    } on DioException catch (error) {
      final data = error.response?.data;
      Object? body = data;
      if (data is List<int>) {
        try {
          body = jsonDecode(utf8.decode(data));
        } on FormatException {
          body = null;
        }
      }
      final detail = body is Map ? body['detail'] : null;
      if (detail is String && detail.trim().isNotEmpty) {
        throw ApiException(detail, statusCode: error.response?.statusCode);
      }
      throw ApiException.fromDio(error);
    }
  }
}
