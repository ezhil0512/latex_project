import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.math_service import _extract_math_local


try:
    print(json.dumps({"equations": _extract_math_local(sys.argv[1])}))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
    sys.exit(1)
