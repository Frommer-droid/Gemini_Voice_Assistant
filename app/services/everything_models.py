from dataclasses import dataclass
from typing import Optional


@dataclass
class SearchQuery:
    trigger: str
    target_type: str  # folder | file | unknown
    name: str
    drive: Optional[str]  # 'c', 'd' или None
    extensions: Optional[str] = None  # список расширений для ext: фильтра
