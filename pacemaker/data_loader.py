import csv
import os
from datetime import datetime
from typing import Dict, List, Optional


DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
LME_DIR = os.path.join(DATA_ROOT, "lme")
GDELT_DIR = os.path.join(DATA_ROOT, "gdelt")
ROOT_PRICE_FILE = os.path.join(DATA_ROOT, "prices.csv")
ROOT_NEWS_FILE = os.path.join(DATA_ROOT, "news.csv")

METAL_SYNONYMS = {
    "copper": {"copper", "cu"},
    "aluminum": {"aluminum", "aluminium", "alu", "al"},
    "nickel": {"nickel", "ni"},
    "zinc": {"zinc", "zn"},
    "lead": {"lead", "pb"},
    "tin": {"tin", "sn"},
}


def normalize_metal(raw_value: str) -> str:
    value = (raw_value or "").strip().lower()
    if value.endswith("_lme"):
        value = value[:-4]
    for canonical, aliases in METAL_SYNONYMS.items():
        if value == canonical or value in aliases:
            return canonical
    return value


def _parse_date(raw_value: str) -> Optional[str]:
    candidates = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y%m%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    raw_value = (raw_value or "").strip()
    for fmt in candidates:
        try:
            return datetime.strptime(raw_value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _read_csv_files(directory: str) -> List[Dict[str, str]]:
    if not os.path.isdir(directory):
        return []
    rows: List[Dict[str, str]] = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".csv"):
            continue
        path = os.path.join(directory, filename)
        with open(path, "r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row["_source_file"] = filename
                rows.append(row)
    return rows


def _read_single_csv_file(path: str) -> List[Dict[str, str]]:
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def load_price_rows() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    source_rows = _read_single_csv_file(ROOT_PRICE_FILE) or _read_csv_files(LME_DIR)
    for row in source_rows:
        metal = normalize_metal(row.get("metal", row.get("commodity", "")))
        date = _parse_date(row.get("date", row.get("Date", "")))
        raw_price = row.get("price", row.get("close", row.get("Close", "")))
        if not metal or not date or raw_price in ("", None):
            continue
        try:
            price = float(raw_price)
        except ValueError:
            continue
        rows.append({"metal": metal, "date": date, "price": price})
    rows.sort(key=lambda item: (item["metal"], item["date"]))
    return rows


def load_news_rows() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    source_rows = _read_single_csv_file(ROOT_NEWS_FILE) or _read_csv_files(GDELT_DIR)
    for row in source_rows:
        date = _parse_date(row.get("date", row.get("DATE", row.get("published_at", ""))))
        title = (row.get("title", row.get("Title", "")) or "").strip()
        source = (row.get("source", row.get("Source", row.get("url", ""))) or "").strip()
        region = (row.get("region", row.get("location", row.get("country", "Global"))) or "Global").strip()
        tone = (row.get("tone", row.get("Tone", "neutral")) or "neutral").strip().lower()
        body = (row.get("body", row.get("text", row.get("summary", title))) or "").strip()
        impacted_commodity = (row.get("impacted_commodity", "") or "").strip()
        if not date or not title:
            continue
        rows.append(
            {
                "date": date,
                "title": title,
                "source": source or "Unknown",
                "region": region,
                "tone": tone,
                "body": body,
                "impacted_commodity": impacted_commodity,
            }
        )
    rows.sort(key=lambda item: item["date"])
    return rows
