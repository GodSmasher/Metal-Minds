import math
from collections import defaultdict
from typing import Dict, List, Tuple

from pacemaker.models import EventImpactRecord, NewsCluster, PriceFeatureRecord


def _sigmoid(value: float) -> float:
    if value < -35:
        return 0.0
    if value > 35:
        return 1.0
    return 1.0 / (1.0 + math.exp(-value))


def _recent_news_features(metal: str, date: str, news_clusters: List[NewsCluster]) -> Dict[str, float]:
    relevant = [cluster for cluster in news_clusters if metal in cluster.metal_tags and cluster.date <= date][-8:]
    features = {
        "news_volume": float(len(relevant)),
        "positive_news_ratio": 0.0,
        "negative_news_ratio": 0.0,
        "high_uncertainty_ratio": 0.0,
        "supply_signal": 0.0,
        "macro_signal": 0.0,
    }
    if not relevant:
        return features
    positive = sum(1 for cluster in relevant if cluster.sentiment == "positive")
    negative = sum(1 for cluster in relevant if cluster.sentiment == "negative")
    uncertainty = sum(1 for cluster in relevant if cluster.uncertainty == "high")
    supply_signal = sum(1 for cluster in relevant if cluster.theme in {"supply disruption", "labor strike", "sanctions", "inventory/logistics", "energy shock"})
    macro_signal = sum(1 for cluster in relevant if cluster.theme in {"macro slowdown", "china demand"})
    total = float(len(relevant))
    features["positive_news_ratio"] = positive / total
    features["negative_news_ratio"] = negative / total
    features["high_uncertainty_ratio"] = uncertainty / total
    features["supply_signal"] = supply_signal / total
    features["macro_signal"] = macro_signal / total
    return features


def _impact_features(metal: str, date: str, event_impacts: List[EventImpactRecord], news_clusters: List[NewsCluster]) -> Dict[str, float]:
    cluster_dates = {cluster.cluster_id: cluster.date for cluster in news_clusters}
    relevant = [
        impact
        for impact in event_impacts
        if impact.metal == metal and cluster_dates.get(impact.cluster_id, "9999-99-99") <= date
    ][-8:]
    if not relevant:
        return {"analog_avg_reaction": 0.0, "analog_confidence": 0.0}
    avg_reaction = sum(impact.avg_reaction for impact in relevant) / len(relevant)
    avg_confidence = sum(impact.confidence for impact in relevant) / len(relevant)
    return {"analog_avg_reaction": avg_reaction, "analog_confidence": avg_confidence}


def build_training_examples(
    price_features: Dict[str, List[PriceFeatureRecord]],
    news_clusters: List[NewsCluster],
    event_impacts: List[EventImpactRecord],
    horizon_days: int = 5,
) -> Tuple[List[List[float]], List[int], List[str]]:
    feature_names = [
        "bias",
        "return_1d",
        "return_5d",
        "return_20d",
        "volatility_20d",
        "zscore_20d",
        "news_volume",
        "positive_news_ratio",
        "negative_news_ratio",
        "high_uncertainty_ratio",
        "supply_signal",
        "macro_signal",
        "analog_avg_reaction",
        "analog_confidence",
    ]
    vectors: List[List[float]] = []
    labels: List[int] = []
    for metal, series in price_features.items():
        for index in range(20, len(series) - horizon_days):
            current = series[index]
            future = series[index + horizon_days]
            label = 1 if future.price > current.price else 0
            news = _recent_news_features(metal, current.date, news_clusters)
            impacts = _impact_features(metal, current.date, event_impacts, news_clusters)
            vectors.append(
                [
                    1.0,
                    current.return_1d,
                    current.return_5d,
                    current.return_20d,
                    current.volatility_20d,
                    current.zscore_20d,
                    news["news_volume"] / 10.0,
                    news["positive_news_ratio"],
                    news["negative_news_ratio"],
                    news["high_uncertainty_ratio"],
                    news["supply_signal"],
                    news["macro_signal"],
                    impacts["analog_avg_reaction"],
                    impacts["analog_confidence"],
                ]
            )
            labels.append(label)
    return vectors, labels, feature_names


def train_directional_model(
    price_features: Dict[str, List[PriceFeatureRecord]],
    news_clusters: List[NewsCluster],
    event_impacts: List[EventImpactRecord],
    horizon_days: int = 5,
    epochs: int = 250,
    learning_rate: float = 0.35,
) -> Dict[str, object]:
    vectors, labels, feature_names = build_training_examples(price_features, news_clusters, event_impacts, horizon_days)
    if not vectors:
        return {"weights": [0.0] * len(feature_names), "feature_names": feature_names, "train_accuracy": 0.0, "sample_count": 0}

    weights = [0.0] * len(feature_names)
    for _ in range(epochs):
        gradients = [0.0] * len(feature_names)
        for features, label in zip(vectors, labels):
            prediction = _sigmoid(sum(weight * value for weight, value in zip(weights, features)))
            error = prediction - label
            for idx, value in enumerate(features):
                gradients[idx] += error * value
        sample_count = float(len(vectors))
        for idx in range(len(weights)):
            weights[idx] -= learning_rate * gradients[idx] / sample_count

    correct = 0
    for features, label in zip(vectors, labels):
        prediction = _sigmoid(sum(weight * value for weight, value in zip(weights, features)))
        if (prediction >= 0.5) == bool(label):
            correct += 1
    accuracy = correct / len(vectors)
    return {
        "weights": weights,
        "feature_names": feature_names,
        "train_accuracy": round(accuracy, 3),
        "sample_count": len(vectors),
        "horizon_days": horizon_days,
    }


def score_directional_bias(
    model: Dict[str, object],
    metal: str,
    current: PriceFeatureRecord,
    news_clusters: List[NewsCluster],
    event_impacts: List[EventImpactRecord],
) -> Dict[str, float]:
    if not model or not model.get("weights"):
        return {"up_probability": 0.5}
    news = _recent_news_features(metal, current.date, news_clusters)
    impacts = _impact_features(metal, current.date, event_impacts, news_clusters)
    vector = [
        1.0,
        current.return_1d,
        current.return_5d,
        current.return_20d,
        current.volatility_20d,
        current.zscore_20d,
        news["news_volume"] / 10.0,
        news["positive_news_ratio"],
        news["negative_news_ratio"],
        news["high_uncertainty_ratio"],
        news["supply_signal"],
        news["macro_signal"],
        impacts["analog_avg_reaction"],
        impacts["analog_confidence"],
    ]
    score = sum(weight * value for weight, value in zip(model["weights"], vector))
    return {"up_probability": round(_sigmoid(score), 3)}


def score_directional_bias_from_context(
    model: Dict[str, object],
    metal: str,
    current: PriceFeatureRecord,
    relevant_news_clusters: List[NewsCluster],
    relevant_event_impacts: List[EventImpactRecord],
) -> Dict[str, float]:
    if not model or not model.get("weights"):
        return {"up_probability": 0.5}
    news = _recent_news_features(metal, current.date, relevant_news_clusters)
    impacts = _impact_features(metal, current.date, relevant_event_impacts, relevant_news_clusters)
    vector = [
        1.0,
        current.return_1d,
        current.return_5d,
        current.return_20d,
        current.volatility_20d,
        current.zscore_20d,
        news["news_volume"] / 10.0,
        news["positive_news_ratio"],
        news["negative_news_ratio"],
        news["high_uncertainty_ratio"],
        news["supply_signal"],
        news["macro_signal"],
        impacts["analog_avg_reaction"],
        impacts["analog_confidence"],
    ]
    score = sum(weight * value for weight, value in zip(model["weights"], vector))
    return {"up_probability": round(_sigmoid(score), 3)}
