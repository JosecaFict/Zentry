import 'dart:async';

import 'package:capricho_store/core/network/api_client.dart';
import 'package:capricho_store/core/notifications/fcm_service.dart';
import 'package:capricho_store/features/auth/data/auth_repository.dart';
import 'package:capricho_store/features/auth/domain/app_user.dart';
import 'package:capricho_store/features/commerce/data/commerce_api.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class AuthState {
  const AuthState({
    this.user,
    this.loading = false,
    this.initialized = false,
    this.error,
    this.sessionExpired = false,
  });

  final AppUser? user;
  final bool loading;
  final bool initialized;
  final String? error;
  final bool sessionExpired;

  bool get isAuthenticated => user != null;

  AuthState copyWith({
    AppUser? user,
    bool? loading,
    bool? initialized,
    String? error,
    bool? sessionExpired,
    bool clearUser = false,
    bool clearError = false,
  }) {
    return AuthState(
      user: clearUser ? null : (user ?? this.user),
      loading: loading ?? this.loading,
      initialized: initialized ?? this.initialized,
      error: clearError ? null : (error ?? this.error),
      sessionExpired: sessionExpired ?? this.sessionExpired,
    );
  }
}

final authControllerProvider = NotifierProvider<AuthController, AuthState>(
  AuthController.new,
);

class AuthController extends Notifier<AuthState> {
  StreamSubscription<void>? _sessionSub;

  @override
  AuthState build() {
    _sessionSub?.cancel();
    _sessionSub = sessionExpiredEventProvider.stream.listen((_) {
      state = state.copyWith(
        clearUser: true,
        sessionExpired: true,
        error: 'Tu sesión ha expirado. Por favor ingresa nuevamente.',
      );
    });

    ref.onDispose(() {
      _sessionSub?.cancel();
    });

    return const AuthState();
  }

  void clearError() {
    state = state.copyWith(
      clearError: true,
      sessionExpired: false,
      loading: false,
    );
  }

  Future<void> restore() async {
    if (!await ref.read(authRepositoryProvider).hasSession()) {
      state = const AuthState(initialized: true);
      return;
    }
    try {
      final user = await ref.read(authRepositoryProvider).me();
      state = AuthState(user: user, initialized: true);
      _syncFcmToken();
    } catch (_) {
      await ref.read(authRepositoryProvider).logout();
      state = const AuthState(initialized: true);
    }
  }

  Future<bool> login(String email, String password) async {
    state = state.copyWith(
      loading: true,
      clearError: true,
      sessionExpired: false,
    );
    try {
      final user = await ref
          .read(authRepositoryProvider)
          .login(email.trim().toLowerCase(), password);
      state = AuthState(user: user, initialized: true);
      _syncFcmToken();
      return true;
    } catch (error) {
      state = state.copyWith(
        loading: false,
        initialized: true,
        error: error.toString().replaceAll('ApiException: ', ''),
      );
      return false;
    }
  }

  Future<bool> register({
    required String names,
    required String surnames,
    required String email,
    required String password,
    String? phone,
    String? ci,
  }) async {
    state = state.copyWith(
      loading: true,
      clearError: true,
      sessionExpired: false,
    );
    try {
      final cleanEmail = email.trim().toLowerCase();
      await ref
          .read(authRepositoryProvider)
          .register(
            names: names.trim(),
            surnames: surnames.trim(),
            email: cleanEmail,
            password: password,
            phone: phone,
            ci: ci,
          );
      final user = await ref
          .read(authRepositoryProvider)
          .login(cleanEmail, password);
      state = AuthState(user: user, initialized: true);
      _syncFcmToken();
      return true;
    } catch (error) {
      state = state.copyWith(
        loading: false,
        initialized: true,
        error: error.toString().replaceAll('ApiException: ', ''),
      );
      return false;
    }
  }

  Future<bool> updateProfile({
    required String names,
    required String surnames,
    String? phone,
    String? ci,
  }) async {
    if (state.loading) return false;
    state = state.copyWith(
      loading: true,
      clearError: true,
    );
    try {
      final updatedUser = await ref
          .read(authRepositoryProvider)
          .updateProfile(
            names: names,
            surnames: surnames,
            phone: phone,
            ci: ci,
          );
      state = state.copyWith(
        user: updatedUser,
        loading: false,
      );
      return true;
    } catch (error) {
      state = state.copyWith(
        loading: false,
        error: error.toString(),
      );
      return false;
    }
  }

  Future<bool> uploadAvatar(String filePath) async {
    if (state.loading) return false;
    state = state.copyWith(loading: true, clearError: true);
    try {
      final updatedUser = await ref.read(authRepositoryProvider).uploadAvatar(filePath);
      state = state.copyWith(user: updatedUser, loading: false);
      return true;
    } catch (error) {
      state = state.copyWith(loading: false, error: error.toString());
      return false;
    }
  }

  Future<bool> deleteAvatar() async {
    if (state.loading) return false;
    state = state.copyWith(loading: true, clearError: true);
    try {
      final updatedUser = await ref.read(authRepositoryProvider).deleteAvatar();
      state = state.copyWith(user: updatedUser, loading: false);
      return true;
    } catch (error) {
      state = state.copyWith(loading: false, error: error.toString());
      return false;
    }
  }

  Future<void> logout() async {
    await ref.read(authRepositoryProvider).logout();
    state = const AuthState(initialized: true);
  }

  void _syncFcmToken() {
    try {
      final api = ref.read(commerceApiProvider);
      FcmService().syncTokenWithBackend(api);
    } catch (_) {}
  }
}
