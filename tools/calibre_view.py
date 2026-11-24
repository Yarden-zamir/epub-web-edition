# /// script
# requires-python = ">=3.15"
# dependencies = ["pillow==13.0.0", "python-xlib==0.33"]
# ///
"""Open an EPUB in the real Calibre viewer on a virtual screen, press keys and take screenshots.

Usage: uv run tools/calibre_view.py BOOK.epub OUT_DIR OPEN_AT KEYS...
  OPEN_AT  Calibre --open-at value, for example toc-href:text/a03.xhtml#a03
  KEYS     X key names to press in order, each followed by a screenshot (for example Left Right)

Needs .tools/calibre (Calibre 9.17.0) and .tools/libs (EGL and OpenGL libraries from Ubuntu packages).
Uses a temporary Calibre config folder, so the user's Calibre settings stay untouched.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import ImageGrab
from Xlib import X, XK, display
from Xlib.ext import xtest

TOOLS = Path(__file__).resolve().parent.parent / ".tools"
SCREEN = ":97"


def shot(out: Path, name: str) -> None:
    ImageGrab.grab(xdisplay=SCREEN).save(out / f"{name}.png")


def press(d: display.Display, key: str) -> None:
    code = d.keysym_to_keycode(XK.string_to_keysym(key))
    xtest.fake_input(d, X.KeyPress, code)
    xtest.fake_input(d, X.KeyRelease, code)
    d.sync()


def focus_viewer(d: display.Display) -> None:
    """No window manager runs on the virtual screen, so give the largest mapped window the keyboard focus."""
    windows = [w for w in d.screen().root.query_tree().children if w.get_attributes().map_state == X.IsViewable]
    if not windows:
        raise SystemExit("calibre viewer: no window on the virtual screen")
    target = max(windows, key=lambda w: w.get_geometry().width * w.get_geometry().height)
    target.configure(x=0, y=0, width=1280, height=900)
    target.set_input_focus(X.RevertToParent, X.CurrentTime)
    d.sync()
    time.sleep(2)


def main() -> None:
    book, out, open_at, keys = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], sys.argv[4:]
    out.mkdir(parents=True, exist_ok=True)
    xvfb = subprocess.Popen(["Xvfb", SCREEN, "-screen", "0", "1280x900x24"], stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    with tempfile.TemporaryDirectory() as cfg:
        env = dict(os.environ, DISPLAY=SCREEN, CALIBRE_CONFIG_DIRECTORY=cfg,
                   LD_LIBRARY_PATH=str(TOOLS / "libs/usr/lib/x86_64-linux-gnu"), QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-gpu-compositing", LIBGL_ALWAYS_SOFTWARE="1", QT_QUICK_BACKEND="software")
        viewer = subprocess.Popen([str(TOOLS / "calibre/ebook-viewer"), "--open-at", open_at, str(book)],
                                  env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            time.sleep(20)
            d = display.Display(SCREEN)
            focus_viewer(d)
            press(d, "space")  # Dismiss the first-run welcome overlay.
            time.sleep(3)
            shot(out, "00-open")
            for n, key in enumerate(keys, start=1):
                press(d, key)
                time.sleep(3)
                shot(out, f"{n:02d}-{key}")
        finally:
            viewer.terminate()
            viewer.wait(timeout=20)
            xvfb.terminate()
    print("screenshots in", out)


if __name__ == "__main__":
    main()
