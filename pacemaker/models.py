from dataclasses import asdict, dataclass, field
from typing import Dict, List


@dataclass
class PriceFeatureRecord:
    metal: str
    date: str
    price: float
    return_1d: float
    return_5d: float
    return_20d: float
    volatility_20d: float
    zscore_20d: float
    regime: str
    anomaly_flags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class NewsCluster:
    cluster_id: str
    metal_tags: List[str]
    theme: str
    sentiment: str
    uncertainty: str
    summary: str
    article_count: int
    relevance_score: float
    regions: List[str]
    urgency: str
    article_titles: List[str]
    date: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class EventImpactRecord:
    cluster_id: str
    metal: str
    horizon: str
    avg_reaction: float
    confidence: float
    analog_count: int
    reaction_label: str
    lead_lag_signal: str

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class DecisionRecommendation:
    metal: str
    horizon: str
    decision_date: str
    risk_appetite: str
    action: str
    confidence: float
    confidence_band: str
    pressure_score: float
    risk_score: float
    conviction_score: float
    rationale: List[str]
    counterpoints: List[str]
    triggers_to_watch: List[str]
    scenarios: Dict[str, Dict[str, object]]
    recommended_actions: List[str]
    historical_performance: Dict[str, object]
    why_now: Dict[str, object]

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)
