package store.zentrysaas.app

import android.app.ActivityManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import androidx.exifinterface.media.ExifInterface
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.pose.PoseDetection
import com.google.mlkit.vision.pose.PoseDetector
import com.google.mlkit.vision.pose.PoseLandmark
import com.google.mlkit.vision.pose.defaults.PoseDetectorOptions
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.File
import kotlin.math.atan2
import kotlin.math.sqrt

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.capricho.store/body_pose"
    private var poseDetector: PoseDetector? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Inicializar detector de pose en modo SINGLE_IMAGE
        // Este modo es ultra eficiente (30-120 ms) y corre con total fluidez en gama baja, media y alta.
        val options = PoseDetectorOptions.Builder()
            .setDetectorMode(PoseDetectorOptions.SINGLE_IMAGE_MODE)
            .build()
        poseDetector = PoseDetection.getClient(options)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL).setMethodCallHandler { call, result ->
            when (call.method) {
                "detectPose" -> {
                    val imagePath = call.argument<String>("imagePath")
                    val gender = call.argument<String>("gender") ?: "HOMBRE"

                    if (imagePath.isNullOrEmpty()) {
                        result.error("INVALID_ARGS", "Falta el parámetro imagePath", null)
                        return@setMethodCallHandler
                    }

                    analyzePose(imagePath, gender, result)
                }
                "bringToFront" -> {
                    try {
                        val activityManager = getSystemService(Context.ACTIVITY_SERVICE) as? ActivityManager
                        activityManager?.moveTaskToFront(taskId, ActivityManager.MOVE_TASK_WITH_HOME)

                        val intent = Intent(this, MainActivity::class.java).apply {
                            flags = Intent.FLAG_ACTIVITY_REORDER_TO_FRONT or
                                    Intent.FLAG_ACTIVITY_SINGLE_TOP or
                                    Intent.FLAG_ACTIVITY_CLEAR_TOP
                        }
                        startActivity(intent)
                        result.success(true)
                    } catch (e: Exception) {
                        result.success(false)
                    }
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }

    private fun analyzePose(imagePath: String, gender: String, result: MethodChannel.Result) {
        val file = File(imagePath)
        if (!file.exists()) {
            result.success(
                mapOf(
                    "detected" to false,
                    "reason" to "FILE_NOT_FOUND",
                    "message" to "No se encontró el archivo de captura."
                )
            )
            return
        }

        try {
            // Decodificación adaptativa: Se calcula el factor de escala antes de cargar en RAM
            // para que fotos de alta resolución (ej. 64MP en Poco X3 o 108MP en S21 Ultra)
            // nunca excedan 1280px, protegiendo dispositivos de gama baja (2-3 GB RAM) contra OutOfMemory.
            val boundsOptions = BitmapFactory.Options().apply { inJustDecodeBounds = true }
            BitmapFactory.decodeFile(imagePath, boundsOptions)

            val maxDimension = 1280
            var sampleSize = 1
            while (boundsOptions.outWidth / sampleSize > maxDimension || boundsOptions.outHeight / sampleSize > maxDimension) {
                sampleSize *= 2
            }

            val decodeOptions = BitmapFactory.Options().apply {
                inSampleSize = sampleSize
                inPreferredConfig = Bitmap.Config.ARGB_8888
            }

            var bitmap = BitmapFactory.decodeFile(imagePath, decodeOptions)
            if (bitmap == null) {
                result.success(
                    mapOf(
                        "detected" to false,
                        "reason" to "DECODE_ERROR",
                        "message" to "No se pudo procesar la imagen de la cámara."
                    )
                )
                return
            }

            // Corrección de rotación EXIF nativa según la orientación de la cámara
            val exif = ExifInterface(imagePath)
            val orientation = exif.getAttributeInt(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_NORMAL)
            val rotationDegrees = when (orientation) {
                ExifInterface.ORIENTATION_ROTATE_90 -> 90f
                ExifInterface.ORIENTATION_ROTATE_180 -> 180f
                ExifInterface.ORIENTATION_ROTATE_270 -> 270f
                else -> 0f
            }

            if (rotationDegrees != 0f) {
                val matrix = Matrix().apply { postRotate(rotationDegrees) }
                val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
                if (rotated != bitmap) {
                    bitmap.recycle()
                    bitmap = rotated
                }
            }

            val inputImage = InputImage.fromBitmap(bitmap, 0)
            poseDetector?.process(inputImage)
                ?.addOnSuccessListener { pose ->
                    val leftShoulder = pose.getPoseLandmark(PoseLandmark.LEFT_SHOULDER)
                    val rightShoulder = pose.getPoseLandmark(PoseLandmark.RIGHT_SHOULDER)

                    if (leftShoulder == null || rightShoulder == null ||
                        leftShoulder.inFrameLikelihood < 0.50f || rightShoulder.inFrameLikelihood < 0.50f) {
                        result.success(
                            mapOf(
                                "detected" to false,
                                "reason" to "SHOULDERS_NOT_VISIBLE",
                                "message" to "Hombros no detectados con claridad. Por favor párate de pie y erguido frente a la cámara a ~1.7 metros."
                            )
                        )
                        bitmap.recycle()
                        return@addOnSuccessListener
                    }

                    val leftEye = pose.getPoseLandmark(PoseLandmark.LEFT_EYE)
                    val rightEye = pose.getPoseLandmark(PoseLandmark.RIGHT_EYE)
                    val nose = pose.getPoseLandmark(PoseLandmark.NOSE)

                    // Filtro Anti-Fantasmas Estricto: Exigir rostro visible mirando al frente
                    val hasFace = (nose != null && nose.inFrameLikelihood > 0.45f) ||
                                  (leftEye != null && leftEye.inFrameLikelihood > 0.45f) ||
                                  (rightEye != null && rightEye.inFrameLikelihood > 0.45f)

                    if (!hasFace) {
                        result.success(
                            mapOf(
                                "detected" to false,
                                "reason" to "NO_FACE_FOUND",
                                "message" to "No se detectó un rostro humano de frente. Asegúrate de encuadrarte de pie mirando a la cámara a ~1.7 metros."
                            )
                        )
                        bitmap.recycle()
                        return@addOnSuccessListener
                    }

                    val imageWidth = bitmap.width.toDouble()
                    val imageHeight = bitmap.height.toDouble()

                    // Coordenadas normalizadas [0.0 - 1.0]
                    val lx = leftShoulder.position.x / imageWidth
                    val ly = leftShoulder.position.y / imageHeight
                    val rx = rightShoulder.position.x / imageWidth
                    val ry = rightShoulder.position.y / imageHeight

                    // Identificar hombro izquierdo y derecho según la vista en pantalla (X menor a la izquierda)
                    val screenLeftX = kotlin.math.min(lx, rx)
                    val screenLeftY = if (lx < rx) ly else ry
                    val screenRightX = kotlin.math.max(lx, rx)
                    val screenRightY = if (lx < rx) ry else ly

                    val screenDx = screenRightX - screenLeftX // Siempre positivo de izquierda a derecha
                    val screenDy = screenRightY - screenLeftY

                    val dxPixels = screenDx * imageWidth
                    val dyPixels = screenDy * imageHeight
                    val shoulderPixelDist = sqrt(dxPixels * dxPixels + dyPixels * dyPixels)
                    val shoulderRatio = shoulderPixelDist / imageWidth

                    // Estimar distancia física real a partir de la relación de encuadre
                    val estimatedDistanceMeters = kotlin.math.round((0.48 / kotlin.math.max(shoulderRatio, 0.08)) * 10.0) / 10.0

                    // Validar distancia razonable
                    if (shoulderRatio < 0.15) {
                        result.success(
                            mapOf(
                                "detected" to false,
                                "reason" to "TOO_FAR",
                                "message" to "Estás demasiado lejos (~${estimatedDistanceMeters}m). Acércate a ~1.7 metros para medir con precisión."
                            )
                        )
                        bitmap.recycle()
                        return@addOnSuccessListener
                    }

                    if (shoulderRatio > 0.48) {
                        result.success(
                            mapOf(
                                "detected" to false,
                                "reason" to "TOO_CLOSE",
                                "message" to "Estás demasiado cerca. Da un paso atrás para encuadrar tu torso completo a ~1.7 metros."
                            )
                        )
                        bitmap.recycle()
                        return@addOnSuccessListener
                    }

                    // Ángulo de hombros en RADIANES para Transform.rotate en Flutter (horizontal ≈ 0.0 rad)
                    val shoulderAngleRad = atan2(screenDy, screenDx)

                    // Centro del cuello: punto medio entre hombros ligeramente elevado
                    val neckX = (lx + rx) / 2.0
                    val neckY = ((ly + ry) / 2.0) - (0.038 * (if (imageHeight > imageWidth) 1.0 else 1.25))

                    // --- CÁLCULO ANTROPOMÉTRICO ROBUSTO CALIBRADO (TALLAS REALES S, M, L, XL) ---
                    val isFemale = gender.equals("MUJER", ignoreCase = true)
                    val baseCm = if (isFemale) 36.0 else 47.0
                    val refIpd = if (isFemale) 6.0 else 6.35      // Distancia interpupilar humana adulta promedio en cm
                    val refHeadH = if (isFemale) 14.5 else 16.5  // Distancia nariz-cuello promedio en cm
                    val minRange = if (isFemale) 32.0 else 38.0
                    val maxRange = if (isFemale) 48.0 else 56.0

                    // Factor de expansión deltoidea anatómica (de articulación ósea a borde exterior)
                    val deltoidExpansion = if (isFemale) 1.15 else 1.25

                    // Compensación óptica por distancia: mantiene invariante el cálculo en cm
                    val distanceComp = (estimatedDistanceMeters / 1.70).coerceIn(0.85, 1.20)

                    var estimatedCm = baseCm
                    var methodApplied = false

                    // 1. Método Interpupilar: Invariante a la distancia de la persona a la cámara
                    if (leftEye != null && rightEye != null &&
                        leftEye.inFrameLikelihood > 0.35f && rightEye.inFrameLikelihood > 0.35f) {
                        val ex1 = leftEye.position.x / imageWidth
                        val ey1 = leftEye.position.y / imageHeight
                        val ex2 = rightEye.position.x / imageWidth
                        val ey2 = rightEye.position.y / imageHeight
                        val edx = (ex2 - ex1)
                        val edy = (ey2 - ey1)
                        val eyeDist = sqrt(edx * edx + edy * edy)

                        if (eyeDist > 0.015) {
                            val anthropometricScale = refIpd / eyeDist
                            val rawCm = shoulderRatio * anthropometricScale * deltoidExpansion
                            if (rawCm in minRange..maxRange) {
                                estimatedCm = rawCm
                                methodApplied = true
                            }
                        }
                    }

                    // 2. Método Nariz-Cuello si los ojos no dieron lectura fiable
                    if (!methodApplied && nose != null && nose.inFrameLikelihood > 0.35f) {
                        val ny = nose.position.y / imageHeight
                        val headDy = kotlin.math.abs(neckY - ny)
                        if (headDy > 0.035) {
                            val headScale = refHeadH / headDy
                            val rawHeadCm = shoulderRatio * headScale * deltoidExpansion
                            if (rawHeadCm in minRange..maxRange) {
                                estimatedCm = rawHeadCm
                                methodApplied = true
                            }
                        }
                    }

                    // 3. Método FOV Calibrado según proporción en encuadre de torso compensado por distancia métrica (168cm / 148cm a 1.70m)
                    if (!methodApplied) {
                        val fovFactor = (if (isFemale) 148.0 else 168.0) * distanceComp
                        estimatedCm = (shoulderRatio * fovFactor).coerceIn(minRange, maxRange)
                    }

                    val finalShouldersCm = (kotlin.math.round(estimatedCm * 10.0) / 10.0).coerceIn(minRange, maxRange)

                    // Liberación inmediata de memoria RAM
                    bitmap.recycle()

                    result.success(
                        mapOf(
                            "detected" to true,
                            "estimatedShouldersCm" to finalShouldersCm,
                            "estimatedDistanceMeters" to estimatedDistanceMeters,
                            "shoulderRatio" to shoulderRatio,
                            "shoulderAngle" to shoulderAngleRad,
                            "neck" to mapOf("x" to neckX, "y" to neckY),
                            "gender" to gender
                        )
                    )
                }
                ?.addOnFailureListener { e ->
                    bitmap.recycle()
                    result.success(
                        mapOf(
                            "detected" to false,
                            "reason" to "MLKIT_ERROR",
                            "message" to "Error al analizar la postura: ${e.localizedMessage}"
                        )
                    )
                }
        } catch (e: Throwable) {
            result.error("PROCESSING_EXCEPTION", e.localizedMessage, null)
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        poseDetector?.close()
    }
}
