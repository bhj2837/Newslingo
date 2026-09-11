"""pytest 가 newslingo 패키지를 찾도록 프로젝트 루트를 sys.path 에 추가."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]  # .../0909-0911_langchain
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
