"""Keep Pillow's core and PNG support without collecting every image plugin.

UnityPy imports Pillow eagerly, but this application extracts text assets only.
The GUI uses Tk's native PNG loader. Keep PNG support for dependency compatibility;
AVIF, WebP, color management, and font rendering are excluded in windows.spec.
"""

hiddenimports = ["PIL.PngImagePlugin"]
