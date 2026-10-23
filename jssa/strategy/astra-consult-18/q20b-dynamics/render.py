"""Render saved SVG plots, with Inkscape state restricted to this directory."""
import os
from pathlib import Path
import shutil
import subprocess

out = Path(__file__).resolve().parent
binary = shutil.which("inkscape")
if binary is None:
    raise SystemExit("Inkscape is unavailable; the standalone SVGs remain usable.")
env = dict(os.environ)
env.update({
    "XDG_CONFIG_HOME": str(out / "render-config"),
    "XDG_CACHE_HOME": str(out / "render-cache"),
    "XDG_DATA_HOME": str(out / "render-data"),
    "INKSCAPE_PROFILE_DIR": str(out / "render-config" / "inkscape"),
    "OMP_NUM_THREADS": "1",
})
for name in ("basin-maps", "uncertainty-curves"):
    subprocess.run(
        [binary, str(out / f"{name}.svg"), "--export-type=png",
         "--export-filename=" + str(out / f"{name}.png")],
        env=env, cwd=out, check=True, timeout=60,
    )
    print(f"rendered {name}.png", flush=True)
