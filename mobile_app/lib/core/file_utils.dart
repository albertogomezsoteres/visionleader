import 'dart:io';

/// Best-effort delete: silently ignores missing files and any I/O errors.
/// Use after a temp file (recording, cropped image) is no longer needed.
Future<void> safeDelete(File? file) async {
  if (file == null) return;
  try {
    if (await file.exists()) await file.delete();
  } catch (_) {}
}
