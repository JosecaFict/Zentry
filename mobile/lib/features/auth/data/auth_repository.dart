import 'package:capricho_store/core/auth/token_storage.dart';
import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/network/api_exception.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/admin/domain/operational_access.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

final authRepositoryProvider = Provider<AuthRepository>((ref) {
  return AuthRepository(
    ref.watch(dioProvider),
    ref.watch(tokenStorageProvider),
  );
});

class AuthRepository {
  AuthRepository(this._dio, this._storage);
  final Dio _dio;
  final TokenStorage _storage;

  Future<AppUser> register({
    // [CU-01] Registro de cliente
    required String names,
    required String surnames,
    required String email,
    required String password,
    String? phone,
    String? ci,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/register',
        data: {
          'nombres': names.trim(),
          'apellidos': surnames.trim(),
          'correo': email.trim().toLowerCase(),
          'password': password,
          'telefono': _optional(phone),
          'ci': _optional(ci),
        },
      );
      return AppUser.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<AppUser> login(String email, String password) async {
    // [CU-01] Inicio de sesión (Login)
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/login',
        data: {'correo': email.trim().toLowerCase(), 'password': password},
      );
      await _storage.write(response.data!['access_token'] as String);
      return await me();
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<AppUser> me() async {
    // [CU-01] Consultar perfil y sesión activa
    try {
      final token = await _storage.read();
      final response = await _dio.get<Map<String, dynamic>>('/auth/me');
      final user = AppUser.fromJson(response.data!);
      if (token != null && await _storage.read() == token) {
        await _storage.cacheProfile(token, response.data!);
      }
      return user;
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<AppUser?> restoreUser() async {
    final connectivity = await Connectivity().checkConnectivity();
    if (!connectivity.contains(ConnectivityResult.none)) {
      try {
        return await me();
      } on ApiException catch (error) {
        final status = error.statusCode;
        if (status != null && status < 500) rethrow;
      }
    }
    final profile = await _storage.readOfflineProfile();
    if (profile == null) return null;
    final user = AppUser.fromJson(profile);
    return user.canAccessOperationalPanel && user.canOpenOffline ? user : null;
  }

  Future<AppUser> updateProfile({
    // [CU-01] Actualizar datos del perfil
    required String names,
    required String surnames,
    String? phone,
    String? ci,
  }) async {
    try {
      final response = await _dio.patch<Map<String, dynamic>>(
        '/auth/me',
        data: {
          'nombres': names.trim(),
          'apellidos': surnames.trim(),
          'telefono': _optional(phone),
          'ci': _optional(ci),
        },
      );
      return AppUser.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<AppUser> uploadAvatar(String filePath) async {
    // [CU-01] Subir foto de perfil a Cloudinary
    try {
      final fileName = filePath.split('/').last.split(r'\').last;
      final formData = FormData.fromMap({
        'file': await MultipartFile.fromFile(filePath, filename: fileName),
      });

      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/me/avatar',
        data: formData,
      );
      return AppUser.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<AppUser> deleteAvatar() async {
    // [CU-01] Eliminar foto de perfil
    try {
      final response = await _dio.delete<Map<String, dynamic>>(
        '/auth/me/avatar',
      );
      return AppUser.fromJson(response.data!);
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<bool> hasSession() async => (await _storage.read()) != null;
  Future<void> logout() => _storage.clear();

  Future<String> requestPasswordRecovery(String email) async {
    // [CU-08] Solicitar código OTP
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/password-recovery/request',
        data: {'correo': email.trim().toLowerCase()},
      );
      return (response.data?['message'] as String?) ??
          'Código de recuperación enviado con éxito.';
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<String> verifyPasswordRecoveryCode({
    // [CU-08] Verificar código OTP
    required String email,
    required String code,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/password-recovery/verify',
        data: {'correo': email.trim().toLowerCase(), 'codigo': code.trim()},
      );
      return response.data!['reset_token'] as String;
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  Future<String> resetPassword({
    // [CU-08] Restablecer contraseña con token OTP
    required String resetToken,
    required String newPassword,
  }) async {
    try {
      final response = await _dio.post<Map<String, dynamic>>(
        '/auth/password-recovery/reset',
        data: {'reset_token': resetToken.trim(), 'password': newPassword},
      );
      return (response.data?['message'] as String?) ??
          'Contraseña restablecida exitosamente.';
    } on DioException catch (error) {
      throw ApiException.fromDio(error);
    }
  }

  static String? _optional(String? value) {
    final cleaned = value?.trim();
    return cleaned == null || cleaned.isEmpty ? null : cleaned;
  }
}
