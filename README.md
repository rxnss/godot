# Cardiac Keyframe Extractor

A collection of Python tools for processing cardiac ultrasound video files.

## Tools

### cardiac_keyframes.py

Extracts bright (systole) and dim (diastole) keyframes from cardiac ultrasound videos by analyzing per-frame brightness. Detects local maxima/minima in the brightness signal to identify cardiac cycles and saves the corresponding frames as images.

```bash
python cardiac_keyframes.py <source_dir> <output_dir> [options]
```

Options include `--neighborhood`, `--min-gap`, `--min-contrast`, `--image-format`, `--jpeg-quality`, `--dry-run`, and `--max-videos`.

### avi_md5_renamer.py

Renames AVI files to MD5-based filenames (derived from their relative paths) and records the original-to-new name mapping in a manifest file.

```bash
python avi_md5_renamer.py <source_dir> <destination_dir> <manifest> [options]
```

### vlc_reencode.py

Re-encodes video files into MP4 (H.264 + AAC) using VLC's command-line interface. Supports single files or batch processing of entire directories.

```bash
python vlc_reencode.py <input> [-o output] [options]
```

## Requirements

- Python 3.10+
- OpenCV (`cv2`)
- NumPy
- VLC (for `vlc_reencode.py`)
