import json
import os
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")


def extract_math(image_path):
    """Extract equations with pix2tex."""
    runner = os.getenv("MATH_PYTHON", "").strip()
    if runner:
        return _extract_math_subprocess(runner, image_path)
    return _extract_math_local(image_path)


def _extract_math_subprocess(python_executable, image_path):
    command = [
        python_executable,
        str(Path(__file__).with_name("math_worker.py")),
        str(image_path),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env=_math_subprocess_env(python_executable),
    )
    if completed.returncode != 0:
        if _is_optional_math_ocr_error(completed.stderr):
            return []
        raise RuntimeError(completed.stderr.strip() or "pix2tex subprocess failed.")
    payload = json.loads(completed.stdout)
    if payload.get("error"):
        if _is_optional_math_ocr_error(payload["error"]):
            return []
        raise RuntimeError(payload["error"])
    return payload.get("equations", [])


def _extract_math_local(image_path):
    _prepare_torch_dll_paths(sys.executable)

    try:
        from PIL import Image
        from pix2tex.cli import LatexOCR
    except (ImportError, OSError, RuntimeError) as exc:
        if _is_optional_math_ocr_error(exc):
            return []
        raise RuntimeError("pix2tex is not installed. Run pip install -r requirements.txt.") from exc

    try:
        model = LatexOCR()
        image = Image.open(image_path).convert("RGB")
        equation = model(image).strip()
    except (OSError, RuntimeError, ValueError) as exc:
        if _is_optional_math_ocr_error(exc):
            return []
        raise

    return [equation] if equation else []


def _math_subprocess_env(python_executable):
    env = os.environ.copy()
    env.setdefault("NO_ALBUMENTATIONS_UPDATE", "1")
    torch_lib = _torch_lib_path(python_executable)

    if torch_lib:
        env["PATH"] = f"{torch_lib}{os.pathsep}{env.get('PATH', '')}"

    return env


def _prepare_torch_dll_paths(python_executable):
    torch_lib = _torch_lib_path(python_executable)

    if not torch_lib:
        return

    os.environ["PATH"] = f"{torch_lib}{os.pathsep}{os.environ.get('PATH', '')}"

    if hasattr(os, "add_dll_directory"):
        os.add_dll_directory(torch_lib)


def _torch_lib_path(python_executable):
    python_path = Path(python_executable).resolve()
    candidates = [
        python_path.parents[1] / "Lib" / "site-packages" / "torch" / "lib",
        Path(sys.prefix) / "Lib" / "site-packages" / "torch" / "lib",
    ]

    for candidate in candidates:
        if (candidate / "shm.dll").exists():
            return str(candidate)

    return ""


def _is_optional_math_ocr_error(error):
    message = str(error).lower()
    return (
        "height and width must be > 0" in message
        or "tile cannot extend outside image" in message
        or "cannot identify image file" in message
        or "shm.dll" in message
        or "specified procedure could not be found" in message
        or "error loading" in message and "torch" in message
    )


if __name__ == "__main__":
    try:
        print(json.dumps({"equations": _extract_math_local(sys.argv[1])}))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(1)
