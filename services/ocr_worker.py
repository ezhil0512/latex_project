import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.ocr_service import _extract_text_local


try:
    print(json.dumps({"text": _extract_text_local(sys.argv[1])}))
except Exception as exc:
    print(json.dumps({"error": str(exc)}))
    sys.exit(1)
