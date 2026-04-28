import 'dart:io';
import 'dart:math';

import 'package:image/image.dart' as img_lib;
import 'package:path_provider/path_provider.dart';

/// Center-crops an image to a square and resizes it before sending it to the
/// VLM. The Colab endpoint expects a square input so portrait photos are not
/// distorted by the model's image processor.
class ImageProcessing {
  ImageProcessing._();

  static Future<File> cropToSquare(File imageFile) async {
    final bytes = await imageFile.readAsBytes();
    final original = img_lib.decodeImage(bytes);
    if (original == null) return imageFile;

    final size = min(original.width, original.height);
    final x = (original.width - size) ~/ 2;
    final y = (original.height - size) ~/ 2;

    final cropped = img_lib.copyCrop(
      original,
      x: x,
      y: y,
      width: size,
      height: size,
    );
    final resized = img_lib.copyResize(
      cropped,
      width: 800,
      interpolation: img_lib.Interpolation.linear,
    );

    final tmpDir = await getTemporaryDirectory();
    final tmpFile = File('${tmpDir.path}/vlm_input.jpg');
    await tmpFile.writeAsBytes(img_lib.encodeJpg(resized, quality: 88));
    return tmpFile;
  }
}
