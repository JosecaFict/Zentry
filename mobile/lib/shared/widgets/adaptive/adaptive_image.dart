import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:capricho_store/core/connectivity/connectivity_controller.dart';
import 'package:capricho_store/core/theme/app_theme.dart';
import 'package:capricho_store/features/catalog/data/catalog_images.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Componente de imagen robusto y adaptativo:
/// - Muestra un shimmer suave durante la descarga.
/// - Fallback editorial si la URL es nula, vacía o falla (error 404 / sin red).
/// - Soporte opcional de Hero tag para transiciones fluidas.
class AdaptiveImage extends ConsumerStatefulWidget {
  const AdaptiveImage({
    required this.imageUrl,
    super.key,
    this.aspectRatio,
    this.width,
    this.height,
    this.fit = BoxFit.cover,
    this.borderRadius,
    this.heroTag,
  });

  final String? imageUrl;
  final double? aspectRatio;
  final double? width;
  final double? height;
  final BoxFit fit;
  final BorderRadius? borderRadius;
  final Object? heroTag;

  @override
  ConsumerState<AdaptiveImage> createState() => _AdaptiveImageState();
}

class _AdaptiveImageState extends ConsumerState<AdaptiveImage>
    with SingleTickerProviderStateMixin {
  late final AnimationController _shimmerController;

  @override
  void initState() {
    super.initState();
    _shimmerController = AnimationController.unbounded(vsync: this)
      ..repeat(min: -0.5, max: 1.5, period: const Duration(milliseconds: 1200));
  }

  @override
  void dispose() {
    _shimmerController.dispose();
    super.dispose();
  }

  Widget _buildShimmerPlaceholder() {
    return AnimatedBuilder(
      animation: _shimmerController,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: const [
                Color(0xFFE8ECEF),
                Color(0xFFF6F8FA),
                Color(0xFFE8ECEF),
              ],
              stops: [
                (_shimmerController.value - 0.3).clamp(0.0, 1.0),
                _shimmerController.value.clamp(0.0, 1.0),
                (_shimmerController.value + 0.3).clamp(0.0, 1.0),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildErrorPlaceholder() {
    return Container(
      width: widget.width,
      height: widget.height,
      color: AppColors.muted,
      alignment: Alignment.center,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: const [
          Icon(
            Icons.checkroom_rounded,
            size: 32,
            color: AppColors.inkSoft,
          ),
          SizedBox(height: 6),
          Text(
            'CAPRICHO',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w800,
              letterSpacing: 1.5,
              color: AppColors.inkSoft,
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final effectiveRadius = widget.borderRadius ?? BorderRadius.circular(12);

    Widget imageContent;

    final url = widget.imageUrl?.trim() ?? '';
    // Copia guardada para ver sin conexión (fase 4) y estado de la red.
    final savedPath = url.isEmpty
        ? null
        : ref.watch(
            catalogImagesControllerProvider.select((state) => state.paths[url]),
          );
    final offline = ref.watch(
      connectivityControllerProvider.select(
        (state) => state.checked && !state.online,
      ),
    );

    Widget savedOr(Widget Function() fallback) => savedPath == null
        ? fallback()
        : Image.file(
            File(savedPath),
            width: widget.width,
            height: widget.height,
            fit: widget.fit,
            errorBuilder: (context, error, stack) => fallback(),
          );

    if (url.isEmpty) {
      imageContent = _buildErrorPlaceholder();
    } else if (offline && savedPath != null) {
      imageContent = savedOr(_buildErrorPlaceholder);
    } else {
      // Con conexión, calidad completa; si la red falla, la copia guardada.
      imageContent = CachedNetworkImage(
        imageUrl: url,
        cacheManager: catalogImageCacheManager,
        width: widget.width,
        height: widget.height,
        fit: widget.fit,
        placeholder: (context, url) => _buildShimmerPlaceholder(),
        errorWidget: (context, url, error) => savedOr(_buildErrorPlaceholder),
        fadeInDuration: const Duration(milliseconds: 250),
      );
    }

    if (widget.aspectRatio != null) {
      imageContent = AspectRatio(
        aspectRatio: widget.aspectRatio!,
        child: imageContent,
      );
    }

    Widget wrapped = ClipRRect(
      borderRadius: effectiveRadius,
      child: imageContent,
    );

    if (widget.heroTag != null) {
      wrapped = Hero(
        tag: widget.heroTag!,
        child: wrapped,
      );
    }

    return wrapped;
  }
}

/// Widget reutilizable para esqueletos de carga animados (Shimmer skeleton).
class ShimmerBox extends StatefulWidget {
  const ShimmerBox({
    super.key,
    this.width,
    this.height,
    this.borderRadius,
  });

  final double? width;
  final double? height;
  final BorderRadius? borderRadius;

  @override
  State<ShimmerBox> createState() => _ShimmerBoxState();
}

class _ShimmerBoxState extends State<ShimmerBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController.unbounded(vsync: this)
      ..repeat(min: -0.5, max: 1.5, period: const Duration(milliseconds: 1200));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, child) {
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: widget.borderRadius ?? BorderRadius.circular(8),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: const [
                Color(0xFFE8ECEF),
                Color(0xFFF6F8FA),
                Color(0xFFE8ECEF),
              ],
              stops: [
                (_controller.value - 0.3).clamp(0.0, 1.0),
                _controller.value.clamp(0.0, 1.0),
                (_controller.value + 0.3).clamp(0.0, 1.0),
              ],
            ),
          ),
        );
      },
    );
  }
}
