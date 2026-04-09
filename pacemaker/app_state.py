from typing import Dict, List

from pacemaker.decision_engine import build_decision
from pacemaker.models import DecisionRecommendation, EventImpactRecord, NewsCluster, PriceFeatureRecord
from pacemaker.pipeline import build_event_impacts, build_news_clusters, build_price_features
from pacemaker.training import train_directional_model


class AppState:
    def __init__(self) -> None:
        self.refresh()

    def refresh(self) -> None:
        self.price_features: Dict[str, List[PriceFeatureRecord]] = build_price_features()
        self.news_clusters: List[NewsCluster] = build_news_clusters()
        self.event_impacts: List[EventImpactRecord] = build_event_impacts(self.price_features, self.news_clusters)
        self.trained_model = train_directional_model(self.price_features, self.news_clusters, self.event_impacts)

    def get_metals(self) -> List[str]:
        return sorted(self.price_features.keys())

    def get_available_dates(self, metal: str) -> List[str]:
        return [feature.date for feature in self.price_features.get(metal, [])]

    def get_decision(self, metal: str, horizon: str = "10d", as_of_date: str = "", risk_appetite: str = "high") -> DecisionRecommendation:
        return build_decision(
            metal,
            horizon,
            self.price_features,
            self.news_clusters,
            self.event_impacts,
            self.trained_model,
            as_of_date=as_of_date or None,
            risk_appetite=risk_appetite,
        )

    def get_news_clusters(self, metal: str, as_of_date: str = "") -> List[dict]:
        return [cluster.to_dict() for cluster in self.news_clusters if metal in cluster.metal_tags and (not as_of_date or cluster.date <= as_of_date)]

    def get_analog_events(self, metal: str, theme: str = "") -> List[dict]:
        cluster_ids = {
            cluster.cluster_id
            for cluster in self.news_clusters
            if metal in cluster.metal_tags and (not theme or cluster.theme == theme)
        }
        return [impact.to_dict() for impact in self.event_impacts if impact.cluster_id in cluster_ids and impact.metal == metal]

    def get_scenarios(self, metal: str, horizon: str = "10d", as_of_date: str = "", risk_appetite: str = "high") -> dict:
        return self.get_decision(metal, horizon, as_of_date=as_of_date, risk_appetite=risk_appetite).scenarios
