import math
import re
import statistics
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Sequence, Tuple

from pacemaker.data_loader import METAL_SYNONYMS, load_news_rows, load_price_rows
from pacemaker.models import EventImpactRecord, NewsCluster, PriceFeatureRecord


THEME_RULES = {
    "supply disruption": {"strike", "outage", "shutdown", "disruption", "smelter", "mine", "flood"},
    "sanctions": {"sanction", "tariff", "ban", "restriction"},
    "macro slowdown": {"slowdown", "recession", "weakness", "downturn", "manufacturing"},
    "energy shock": {"energy", "power", "gas", "electricity", "coal"},
    "labor strike": {"union", "labor", "strike", "walkout"},
    "china demand": {"china", "construction", "property", "stimulus"},
    "inventory/logistics": {"inventory", "warehouse", "shipping", "freight", "logistics", "stockpile"},
    "policy/regulation": {"policy", "regulation", "permit", "government", "compliance"},
}

POSITIVE_WORDS = {"surge", "recover", "growth", "improve", "support", "tighten", "stimulus"}
NEGATIVE_WORDS = {"drop", "fall", "slowdown", "weak", "risk", "disruption", "strike", "sanction"}
UNCERTAINTY_WORDS = {"may", "could", "uncertain", "volatile", "risk", "possible", "warning"}


def _rolling_return(prices: Sequence[float], index: int, window: int) -> float:
    if index - window < 0 or prices[index - window] == 0:
        return 0.0
    return (prices[index] - prices[index - window]) / prices[index - window]


def _rolling_volatility(prices: Sequence[float], index: int, window: int) -> float:
    if index < 1:
        return 0.0
    start = max(1, index - window + 1)
    returns = []
    for pointer in range(start, index + 1):
        previous = prices[pointer - 1]
        current = prices[pointer]
        if previous:
            returns.append((current - previous) / previous)
    if len(returns) < 2:
        return 0.0
    return statistics.pstdev(returns)


def _rolling_zscore(prices: Sequence[float], index: int, window: int) -> float:
    start = max(0, index - window + 1)
    sample = prices[start : index + 1]
    if len(sample) < 2:
        return 0.0
    mean = statistics.fmean(sample)
    std_dev = statistics.pstdev(sample)
    if std_dev == 0:
        return 0.0
    return (prices[index] - mean) / std_dev


def _classify_regime(return_5d: float, return_20d: float, volatility_20d: float) -> str:
    if return_5d > 0.03 and return_20d > 0.05:
        return "bullish breakout"
    if return_5d < -0.03 and return_20d < -0.05:
        return "bearish slide"
    if volatility_20d > 0.025:
        return "volatile"
    return "range-bound"


def build_price_features() -> Dict[str, List[PriceFeatureRecord]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in load_price_rows():
        grouped[row["metal"]].append(row)

    results: Dict[str, List[PriceFeatureRecord]] = {}
    for metal, rows in grouped.items():
        rows.sort(key=lambda item: item["date"])
        prices = [float(row["price"]) for row in rows]
        feature_rows: List[PriceFeatureRecord] = []
        for index, row in enumerate(rows):
            return_1d = _rolling_return(prices, index, 1)
            return_5d = _rolling_return(prices, index, 5)
            return_20d = _rolling_return(prices, index, 20)
            volatility_20d = _rolling_volatility(prices, index, 20)
            zscore_20d = _rolling_zscore(prices, index, 20)
            regime = _classify_regime(return_5d, return_20d, volatility_20d)
            anomaly_flags = []
            if abs(return_1d) > 0.03:
                anomaly_flags.append("large daily move")
            if abs(zscore_20d) > 1.5:
                anomaly_flags.append("price dislocated vs trailing mean")
            feature_rows.append(
                PriceFeatureRecord(
                    metal=metal,
                    date=row["date"],
                    price=float(row["price"]),
                    return_1d=return_1d,
                    return_5d=return_5d,
                    return_20d=return_20d,
                    volatility_20d=volatility_20d,
                    zscore_20d=zscore_20d,
                    regime=regime,
                    anomaly_flags=anomaly_flags,
                )
            )
        results[metal] = feature_rows
    return results


def _detect_metal_tags(text: str) -> List[str]:
    lowered = text.lower()
    tokens = set(re.findall(r"[a-z]+", lowered))
    matches = []
    for canonical, aliases in METAL_SYNONYMS.items():
        for alias in aliases | {canonical}:
            alias_tokens = set(re.findall(r"[a-z]+", alias))
            if alias_tokens and alias_tokens.issubset(tokens):
                matches.append(canonical)
                break
    return sorted(set(matches))


def _detect_metal_tags_from_hint(hint: str) -> List[str]:
    if not hint:
        return []
    parts = [normalize.strip() for normalize in hint.lower().split(",")]
    matches = [metal for metal in (METAL_SYNONYMS.keys()) if metal in parts]
    if matches:
        return sorted(set(matches))
    normalized = []
    for part in parts:
        cleaned = part.strip()
        if cleaned.endswith("_lme"):
            cleaned = cleaned[:-4]
        if cleaned == "aluminium":
            cleaned = "aluminum"
        if cleaned in METAL_SYNONYMS:
            normalized.append(cleaned)
    return sorted(set(normalized))


def _infer_theme(text: str) -> str:
    lowered_words = set(text.lower().split())
    best_theme = "policy/regulation"
    best_score = -1
    for theme, keywords in THEME_RULES.items():
        score = sum(1 for keyword in keywords if keyword in lowered_words or keyword in text.lower())
        if score > best_score:
            best_theme = theme
            best_score = score
    return best_theme


def _classify_sentiment(text: str, tone: str) -> str:
    lowered = text.lower()
    positive = sum(1 for word in POSITIVE_WORDS if word in lowered)
    negative = sum(1 for word in NEGATIVE_WORDS if word in lowered)
    if "positive" in tone or positive > negative:
        return "positive"
    if "negative" in tone or negative > positive:
        return "negative"
    return "neutral"


def _classify_uncertainty(text: str) -> str:
    lowered = text.lower()
    score = sum(1 for word in UNCERTAINTY_WORDS if word in lowered)
    if score >= 3:
        return "high"
    if score >= 1:
        return "medium"
    return "low"


def _classify_urgency(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["urgent", "immediate", "now", "warning"]):
        return "high"
    if any(word in lowered for word in ["watch", "monitor", "possible"]):
        return "medium"
    return "low"


def _summarize_cluster(theme: str, metal_tags: List[str], sentiment: str, uncertainty: str, titles: List[str]) -> str:
    metal_phrase = ", ".join(metal_tags) if metal_tags else "metal markets"
    cue = "may tighten near-term supply" if theme in {"supply disruption", "labor strike", "sanctions"} else "may soften near-term demand"
    if sentiment == "positive":
        cue = "supports near-term upside bias"
    if theme == "inventory/logistics":
        cue = "changes physical availability and inventory planning"
    if uncertainty == "high":
        cue += " but confidence is limited by elevated uncertainty"
    return f"{theme.title()} headlines around {metal_phrase} suggest this theme {cue}. Lead story: {titles[0]}"


def build_news_clusters() -> List[NewsCluster]:
    buckets: Dict[Tuple[str, str, str], Dict[str, object]] = {}
    for row in load_news_rows():
        combined_text = f"{row['title']} {row['body']}"
        metal_tags = _detect_metal_tags_from_hint(row.get("impacted_commodity", "")) or _detect_metal_tags(combined_text)
        if not metal_tags:
            continue
        theme = _infer_theme(combined_text)
        key = (row["date"], ",".join(metal_tags), theme)
        bucket = buckets.setdefault(
            key,
            {
                "titles": [],
                "regions": set(),
                "tones": [],
                "texts": [],
            },
        )
        title_key = row["title"].strip().lower()
        if title_key in {existing.strip().lower() for existing in bucket["titles"]}:
            continue
        bucket["titles"].append(row["title"])
        bucket["regions"].add(row["region"])
        bucket["tones"].append(row["tone"])
        bucket["texts"].append(combined_text)

    clusters: List[NewsCluster] = []
    for index, ((date, metal_key, theme), bucket) in enumerate(sorted(buckets.items()), start=1):
        text_blob = " ".join(bucket["texts"])
        titles = bucket["titles"]
        metal_tags = metal_key.split(",")
        sentiment = _classify_sentiment(text_blob, " ".join(bucket["tones"]))
        uncertainty = _classify_uncertainty(text_blob)
        urgency = _classify_urgency(text_blob)
        summary = _summarize_cluster(theme, metal_tags, sentiment, uncertainty, titles)
        article_count = len(titles)
        relevance_score = round(min(1.0, 0.3 + article_count * 0.15 + len(metal_tags) * 0.1), 2)
        clusters.append(
            NewsCluster(
                cluster_id=f"cluster-{index}",
                metal_tags=metal_tags,
                theme=theme,
                sentiment=sentiment,
                uncertainty=uncertainty,
                summary=summary,
                article_count=article_count,
                relevance_score=relevance_score,
                regions=sorted(bucket["regions"]),
                urgency=urgency,
                article_titles=titles,
                date=date,
            )
        )
    return clusters


def _date_diff_days(start: str, end: str) -> int:
    start_dt = datetime.strptime(start, "%Y-%m-%d")
    end_dt = datetime.strptime(end, "%Y-%m-%d")
    return (end_dt - start_dt).days


def _find_feature_index(features: List[PriceFeatureRecord], date: str) -> int:
    for index, feature in enumerate(features):
        if feature.date >= date:
            return index
    return len(features) - 1


def build_event_impacts(
    price_features: Dict[str, List[PriceFeatureRecord]], news_clusters: List[NewsCluster]
) -> List[EventImpactRecord]:
    records: List[EventImpactRecord] = []
    for cluster in news_clusters:
        for metal in cluster.metal_tags:
            features = price_features.get(metal, [])
            if len(features) < 2:
                continue
            index = _find_feature_index(features, cluster.date)
            same_day = features[index].return_1d
            follow_through_samples = []
            for offset in (3, 5, 10):
                future_index = min(len(features) - 1, index + offset)
                if future_index > index and features[index].price:
                    move = (features[future_index].price - features[index].price) / features[index].price
                    follow_through_samples.append(move)
            avg_reaction = statistics.fmean(follow_through_samples) if follow_through_samples else same_day
            confidence = min(0.95, 0.35 + cluster.relevance_score * 0.4 + len(follow_through_samples) * 0.05)
            if abs(avg_reaction) < 0.01:
                reaction_label = "muted"
            elif avg_reaction > 0:
                reaction_label = "positive follow-through"
            else:
                reaction_label = "negative follow-through"
            if same_day == 0 and follow_through_samples:
                lead_lag_signal = "news leads price"
            elif abs(same_day) > 0.015 and abs(avg_reaction) < 0.01:
                lead_lag_signal = "price moved before narrative broadened"
            else:
                lead_lag_signal = "no consistent relationship"
            records.append(
                EventImpactRecord(
                    cluster_id=cluster.cluster_id,
                    metal=metal,
                    horizon="10d",
                    avg_reaction=round(avg_reaction, 4),
                    confidence=round(confidence, 2),
                    analog_count=max(1, cluster.article_count),
                    reaction_label=reaction_label,
                    lead_lag_signal=lead_lag_signal,
                )
            )
    return records
