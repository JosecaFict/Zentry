import 'package:flutter/cupertino.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

abstract final class AppColors {
  static const canvas = Color(0xFFF7F6F3);
  static const surface = Color(0xFFFFFFFF);
  static const muted = Color(0xFFECEEF1);
  static const ink = Color(0xFF121418);
  static const inkSoft = Color(0xFF565D67);
  static const line = Color(0xFFCBD0D6);
  static const cobalt = Color(0xFF064FE8);
  static const cobaltDark = Color(0xFF0039B8);
  static const cobaltLight = Color(0xFFE3EDFF);
  static const danger = Color(0xFFB42318);
  static const warning = Color(0xFF7A4B00);
  static const success = Color(0xFF027A48);
}

abstract final class AppTheme {
  static ThemeData forTenant(Color? primary) {
    if (primary == null) return light;
    final base = light;
    final scheme = ColorScheme.fromSeed(
      seedColor: primary,
      brightness: Brightness.light,
      surface: AppColors.canvas,
    ).copyWith(
      primary: primary,
      onPrimary: Colors.white,
      error: AppColors.danger,
      onSurface: AppColors.ink,
      outline: AppColors.line,
      surfaceContainerHighest: AppColors.muted,
    );
    return base.copyWith(
      colorScheme: scheme,
      filledButtonTheme: FilledButtonThemeData(
        style: base.filledButtonTheme.style?.copyWith(
          backgroundColor: WidgetStatePropertyAll(primary),
        ),
      ),
    );
  }

  static ThemeData get light {
    final scheme =
        ColorScheme.fromSeed(
          seedColor: AppColors.cobalt,
          brightness: Brightness.light,
          surface: AppColors.canvas,
        ).copyWith(
          primary: AppColors.cobalt,
          onPrimary: Colors.white,
          error: AppColors.danger,
          onSurface: AppColors.ink,
          outline: AppColors.line,
          surfaceContainerHighest: AppColors.muted,
        );

    final isIOS = defaultTargetPlatform == TargetPlatform.iOS;

    final base = ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      // Usar fuente nativa del sistema (SF Pro en iOS, Roboto en Android)
      splashFactory: isIOS ? NoSplash.splashFactory : InkRipple.splashFactory,
      pageTransitionsTheme: const PageTransitionsTheme(
        builders: {
          TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
          TargetPlatform.android: ZoomPageTransitionsBuilder(),
          TargetPlatform.macOS: CupertinoPageTransitionsBuilder(),
        },
      ),
    );

    final squircleCardRadius = BorderRadius.circular(16);
    final squircleControlRadius = BorderRadius.circular(10);

    return base.copyWith(
      scaffoldBackgroundColor: AppColors.canvas,
      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.canvas,
        foregroundColor: AppColors.ink,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: false,
      ),
      textTheme: base.textTheme.copyWith(
        displaySmall: base.textTheme.displaySmall?.copyWith(
          fontSize: 34,
          height: 1.05,
          fontWeight: FontWeight.w800,
          letterSpacing: isIOS ? -1.2 : -0.8,
          color: AppColors.ink,
        ),
        headlineMedium: base.textTheme.headlineMedium?.copyWith(
          fontSize: 24,
          height: 1.1,
          fontWeight: FontWeight.w800,
          letterSpacing: isIOS ? -0.8 : -0.4,
          color: AppColors.ink,
        ),
        titleLarge: base.textTheme.titleLarge?.copyWith(
          fontSize: 20,
          fontWeight: FontWeight.w700,
          letterSpacing: isIOS ? -0.5 : 0.0,
          color: AppColors.ink,
        ),
        titleMedium: base.textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.w700,
          color: AppColors.ink,
        ),
        bodyLarge: base.textTheme.bodyLarge?.copyWith(
          color: AppColors.ink,
          height: 1.5,
        ),
        bodyMedium: base.textTheme.bodyMedium?.copyWith(
          color: AppColors.inkSoft,
          height: 1.5,
        ),
        labelLarge: base.textTheme.labelLarge?.copyWith(
          fontWeight: FontWeight.w700,
          letterSpacing: 0.2,
        ),
        labelSmall: base.textTheme.labelSmall?.copyWith(
          fontWeight: FontWeight.w700,
          letterSpacing: 1.2,
          color: AppColors.inkSoft,
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        border: OutlineInputBorder(
          borderRadius: squircleControlRadius,
          borderSide: const BorderSide(color: AppColors.line),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: squircleControlRadius,
          borderSide: const BorderSide(color: AppColors.line),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: squircleControlRadius,
          borderSide: const BorderSide(color: AppColors.cobalt, width: 2),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 15,
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          minimumSize: const Size(48, 48),
          backgroundColor: AppColors.cobalt,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(borderRadius: squircleControlRadius),
          textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          minimumSize: const Size(48, 48),
          foregroundColor: AppColors.ink,
          side: const BorderSide(color: AppColors.line),
          shape: RoundedRectangleBorder(borderRadius: squircleControlRadius),
          textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 14),
        ),
      ),
      navigationBarTheme: const NavigationBarThemeData(
        backgroundColor: AppColors.surface,
        indicatorColor: AppColors.cobaltLight,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        height: 68,
      ),
      cardTheme: CardThemeData(
        color: AppColors.surface,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: squircleCardRadius,
          side: const BorderSide(color: AppColors.line, width: 0.8),
        ),
      ),
    );
  }
}
