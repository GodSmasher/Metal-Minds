from collections import defaultdict
from typing import Dict, List, Optional

from pacemaker.models import DecisionRecommendation, EventImpactRecord, NewsCluster, PriceFeatureRecord
from pacemaker.training import score_directional_bias_from_context


def _confidence_band(confidence: float) -> str:
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _theme_pressure(theme: str, sentiment: str) -> float:
    bullish_themes = {"supply disruption", "labor strike", "sanctions", "energy shock", "inventory/logistics"}
    bearish_themes = {"macro slowdown"}
    if theme in bullish_themes:
        return 0.18 if sentiment != "positive" else 0.12
    if theme in bearish_themes:
        return -0.18
    if theme == "china demand":
        return 0.15 if sentiment == "positive" else -0.08
    return 0.04


def _scenario_probabilities(up_probability: float, conviction_score: float) -> Dict[str, int]:
    best = 0.18 + up_probability * 0.28 + conviction_score * 0.14
    worst = 0.18 + (1 - up_probability) * 0.24 + (1 - conviction_score) * 0.14
    base = max(0.15, 1.0 - best - worst)
    total = best + base + worst
    normalized = {
        "best": round(best / total * 100),
        "base": round(base / total * 100),
        "worst": round(worst / total * 100),
    }
    diff = 100 - sum(normalized.values())
    normalized["base"] += diff
    return normalized


def _build_projection_points(
    series: List[PriceFeatureRecord],
    feature_index: int,
    horizon_days: int,
    latest_price: float,
    best_delta: float,
    base_delta: float,
    worst_delta: float,
) -> Dict[str, List[Dict[str, object]]]:
    history_start = max(0, feature_index - 9)
    history = [
        {"label": feature.date, "price": round(feature.price, 2)}
        for feature in series[history_start : feature_index + 1]
    ]

    future_end = min(len(series) - 1, feature_index + horizon_days)
    future_actual_slice = series[feature_index + 1 : future_end + 1]
    projection_labels = [feature.date for feature in future_actual_slice]
    if not projection_labels:
        projection_labels = [f"T+{step}" for step in range(1, horizon_days + 1)]

    points = []
    step_count = len(projection_labels)
    for step, label in enumerate(projection_labels, start=1):
        scale = step / step_count
        points.append(
            {
                "label": label,
                "best": round(latest_price * (1 + best_delta * scale), 2),
                "base": round(latest_price * (1 + base_delta * scale), 2),
                "worst": round(latest_price * (1 + worst_delta * scale), 2),
            }
        )

    actual_future = [{"label": feature.date, "price": round(feature.price, 2)} for feature in future_actual_slice]
    return {"history": history, "forecast": points, "actual_future": actual_future}


def build_decision(
    metal: str,
    horizon: str,
    price_features: Dict[str, List[PriceFeatureRecord]],
    news_clusters: List[NewsCluster],
    event_impacts: List[EventImpactRecord],
    trained_model: Optional[Dict[str, object]] = None,
    as_of_date: Optional[str] = None,
    risk_appetite: str = "high",
) -> DecisionRecommendation:
    series = price_features[metal]
    if as_of_date:
        eligible_indices = [index for index, feature in enumerate(series) if feature.date <= as_of_date]
        feature_index = eligible_indices[-1] if eligible_indices else 0
    else:
        feature_index = len(series) - 1
    latest = series[feature_index]
    decision_date = latest.date
    relevant_clusters = [cluster for cluster in news_clusters if metal in cluster.metal_tags and cluster.date <= decision_date][-5:]
    relevant_cluster_ids = {cluster.cluster_id for cluster in relevant_clusters}
    relevant_impacts = [
        impact for impact in event_impacts if impact.metal == metal and impact.cluster_id in relevant_cluster_ids
    ][-5:]
    directional = score_directional_bias_from_context(trained_model or {}, metal, latest, relevant_clusters, relevant_impacts)
    up_probability = directional["up_probability"]

    pressure_score = 0.42
    pressure_score += max(-0.18, min(0.18, latest.return_20d * 1.7))
    pressure_score += max(-0.12, min(0.12, latest.return_5d * 1.5))
    pressure_score += (up_probability - 0.5) * 0.22
    if latest.regime == "bullish breakout":
        pressure_score += 0.1
    elif latest.regime == "bearish slide":
        pressure_score -= 0.12

    for cluster in relevant_clusters:
        pressure_score += _theme_pressure(cluster.theme, cluster.sentiment) * min(0.75, cluster.relevance_score) * 0.55
        if cluster.uncertainty == "high":
            pressure_score += 0.02

    risk_score = 0.35 + min(0.25, latest.volatility_20d * 8)
    risk_score += 0.1 if "large daily move" in latest.anomaly_flags else 0.0
    risk_score += sum(0.05 for cluster in relevant_clusters if cluster.uncertainty == "high")
    risk_score = max(0.0, min(1.0, risk_score))
    appetite = (risk_appetite or "medium").lower()
    if appetite == "low":
        pressure_score += 0.04
        conviction_score_bias = 0.06
    elif appetite == "high":
        pressure_score -= 0.03
        conviction_score_bias = -0.02
    else:
        conviction_score_bias = 0.0

    positive_impacts = [impact for impact in relevant_impacts if impact.avg_reaction > 0.01]
    negative_impacts = [impact for impact in relevant_impacts if impact.avg_reaction < -0.01]
    conviction_score = 0.4
    conviction_score += min(0.2, len(relevant_clusters) * 0.03)
    conviction_score += min(0.18, sum(impact.confidence for impact in relevant_impacts) / 12.0)
    conviction_score += abs(up_probability - 0.5) * 0.12
    conviction_score += conviction_score_bias
    if latest.regime == "range-bound":
        conviction_score -= 0.08
    if positive_impacts and negative_impacts:
        conviction_score -= 0.12
    conviction_score = max(0.0, min(1.0, conviction_score))
    pressure_score = max(0.0, min(1.0, pressure_score))

    if appetite == "low" and risk_score >= 0.55 and pressure_score >= 0.5:
        action = "Partial buy + hedge"
    elif appetite == "high" and pressure_score < 0.52 and conviction_score < 0.72:
        action = "Wait / monitor" if latest.regime != "bearish slide" else "Stay lean"
    elif pressure_score >= 0.62 and conviction_score >= 0.62:
        action = "Buy now"
    elif pressure_score >= 0.52 and risk_score >= 0.5:
        action = "Partial buy + hedge"
    elif pressure_score <= 0.38 and conviction_score < 0.55:
        action = "Wait / monitor"
    elif latest.regime == "bearish slide" and pressure_score < 0.43:
        action = "Stay lean"
    else:
        action = "Investigate / hedge selectively"

    confidence = max(0.0, min(0.95, 0.35 + conviction_score * 0.35 + abs(pressure_score - 0.5) * 0.3))
    confidence_band = _confidence_band(confidence)

    rationale = []
    if relevant_clusters:
        top_cluster = sorted(relevant_clusters, key=lambda cluster: cluster.relevance_score, reverse=True)[0]
        rationale.append(
            f"Recent {top_cluster.theme} coverage is the dominant narrative, with {top_cluster.article_count} clustered articles pointing to {metal} supply-demand pressure."
        )
        rationale.append(top_cluster.summary)
        supporting_clusters = [cluster for cluster in relevant_clusters if cluster.cluster_id != top_cluster.cluster_id]
        if supporting_clusters:
            supporting = supporting_clusters[0]
            rationale.append(
                f"A secondary theme in the news flow is {supporting.theme}, which reinforces the current market narrative around {metal}."
            )
    rationale.append(
        f"Price action is currently {latest.regime}, with {latest.return_5d * 100:.1f}% over 5 days and {latest.return_20d * 100:.1f}% over 20 days."
    )
    rationale.append(
        f"Near-term delay risk remains elevated because realized volatility is {latest.volatility_20d * 100:.1f}% over the last 20 sessions."
    )
    if positive_impacts:
        strongest = sorted(positive_impacts, key=lambda impact: impact.confidence, reverse=True)[0]
        rationale.append(
            f"Historically, similar news setups showed {strongest.reaction_label} over {strongest.horizon}, supporting a more proactive decision."
        )
    elif negative_impacts:
        strongest = sorted(negative_impacts, key=lambda impact: impact.confidence, reverse=True)[0]
        rationale.append(
            f"Historically, similar news setups led to downside follow-through over {strongest.horizon}, which argues for patience."
        )

    counterpoints = []
    if negative_impacts:
        counterpoints.append("Some historical analogs point to downside or muted follow-through after similar headlines.")
    if latest.zscore_20d > 1.5:
        counterpoints.append("Spot price is already stretched versus its trailing mean, increasing reversal risk.")
    if not counterpoints:
        counterpoints.append("Signal agreement is decent, but the prototype still relies on lightweight historical analog matching.")

    triggers_to_watch = []
    if latest.return_5d > 0:
        triggers_to_watch.append("Monitor whether 5-day momentum stays positive through the next trading week.")
    else:
        triggers_to_watch.append("Watch for stabilization in short-term returns before adding inventory.")
    triggers_to_watch.append("Track whether high-relevance news themes broaden or fade over the next 3 to 5 trading days.")
    triggers_to_watch.append("Escalate if volatility spikes above the recent 20-day range.")

    best_delta = max(0.01, pressure_score * 0.06)
    worst_delta = -max(0.01, (1 - pressure_score) * 0.05)
    base_delta = (best_delta + worst_delta) / 2
    scenario_probabilities = _scenario_probabilities(up_probability, conviction_score)
    scenarios = {
        "best": {
            "direction": "up",
            "probability_pct": scenario_probabilities["best"],
            "price_change_pct": round(best_delta * 100, 1),
            "narrative": "Supply-side pressure persists and buyers face tighter availability.",
        },
        "base": {
            "direction": "sideways" if abs(base_delta) < 0.01 else ("up" if base_delta > 0 else "down"),
            "probability_pct": scenario_probabilities["base"],
            "price_change_pct": round(base_delta * 100, 1),
            "narrative": "Mixed signals keep the market choppy, with procurement costs holding near current levels.",
        },
        "worst": {
            "direction": "down" if worst_delta < 0 else "up",
            "probability_pct": scenario_probabilities["worst"],
            "price_change_pct": round(worst_delta * 100, 1),
            "narrative": "Demand concerns dominate and recent headlines fail to create sustained follow-through.",
        },
    }

    recommended_actions = {
        "Buy now": [
            "Cover the majority of near-term demand now.",
            "Keep a smaller tranche flexible in case volatility softens.",
            "Prepare a hedge only if volatility accelerates further.",
        ],
        "Partial buy + hedge": [
            "Execute a partial purchase now to reduce timing risk.",
            "Hedge a portion of remaining exposure over the next week.",
            "Reassess after the next cluster of high-relevance news or price breakout.",
        ],
        "Wait / monitor": [
            "Hold off on incremental buying until directional evidence improves.",
            "Set alert thresholds for momentum reversal or new supply headlines.",
            "Keep inventory lean while monitoring news intensity.",
        ],
        "Stay lean": [
            "Avoid building inventory into a weakening market.",
            "Review physical coverage needs only for mandatory near-term demand.",
            "Use any rebound to reassess purchase timing.",
        ],
        "Investigate / hedge selectively": [
            "Avoid an all-in timing call while signals conflict.",
            "Hedge only the exposure that cannot tolerate an upside surprise.",
            "Revisit after another 3 to 5 trading sessions of evidence.",
        ],
    }[action]

    theme_counts = defaultdict(int)
    for cluster in relevant_clusters:
        theme_counts[cluster.theme] += cluster.article_count

    dominant_theme = max(theme_counts.items(), key=lambda item: item[1])[0] if theme_counts else "mixed signals"
    linkage_points = []
    for impact in sorted(relevant_impacts, key=lambda item: item.confidence, reverse=True)[:3]:
        related_cluster = next((cluster for cluster in relevant_clusters if cluster.cluster_id == impact.cluster_id), None)
        theme_label = related_cluster.theme if related_cluster else "market event"
        linkage_points.append(
            f"{theme_label.title()} events historically produced {impact.reaction_label} over {impact.horizon} with {impact.confidence:.0%} confidence."
        )
    if not linkage_points:
        linkage_points.append("Historical analog coverage is still thin, so the recommendation leans more on current price regime and news intensity.")

    narrative_summary = (
        f"Raw news clustered into a {dominant_theme} narrative, price features show a {latest.regime} regime, "
        f"and the model assigns a {up_probability:.0%} upside probability. "
        f"Those signals combine into a {action.lower()} recommendation."
    )
    decision_story = [
        f"Data: {len(relevant_clusters)} recent news clusters and current {metal} price features were evaluated as of {decision_date}.",
        f"Insight: the dominant narrative is {dominant_theme}, while price action is {latest.regime} with {latest.return_20d * 100:.1f}% 20-day performance.",
        f"Decision: {action} because pressure is {pressure_score:.2f}, risk is {risk_score:.2f}, and conviction is {conviction_score:.2f}.",
    ]

    horizon_days = int(horizon[:-1]) if horizon.endswith("d") and horizon[:-1].isdigit() else 10
    future_index = min(len(series) - 1, feature_index + horizon_days)
    future_feature = series[future_index]
    chart_data = _build_projection_points(series, feature_index, horizon_days, latest.price, best_delta, base_delta, worst_delta)
    realized_return = 0.0 if latest.price == 0 else (future_feature.price - latest.price) / latest.price
    if action == "Buy now":
        recommendation_correct = realized_return > 0
    elif action in {"Wait / monitor", "Stay lean"}:
        recommendation_correct = realized_return <= 0
    elif action == "Partial buy + hedge":
        recommendation_correct = abs(realized_return) <= 0.03 or realized_return > 0
    else:
        recommendation_correct = abs(realized_return) <= 0.04
    if future_index == feature_index:
        verification_status = "insufficient future data"
    else:
        verification_status = "good call" if recommendation_correct else "missed move"
    historical_performance = {
        "evaluation_available": future_index > feature_index,
        "verification_status": verification_status,
        "horizon_end_date": future_feature.date,
        "entry_price": round(latest.price, 2),
        "future_price": round(future_feature.price, 2),
        "realized_return_pct": round(realized_return * 100, 2),
        "recommendation_was_correct": recommendation_correct if future_index > feature_index else None,
        "benchmark": {
            "expected_direction": "up" if action in {"Buy now", "Partial buy + hedge"} else "down_or_flat",
            "actual_direction": "up" if realized_return > 0.002 else ("down" if realized_return < -0.002 else "flat"),
        },
    }

    why_now = {
        "latest_price": latest.price,
        "price_context": {
            "return_1d_pct": round(latest.return_1d * 100, 2),
            "return_5d_pct": round(latest.return_5d * 100, 2),
            "return_20d_pct": round(latest.return_20d * 100, 2),
            "volatility_20d_pct": round(latest.volatility_20d * 100, 2),
            "zscore_20d": round(latest.zscore_20d, 2),
            "regime": latest.regime,
            "anomaly_flags": latest.anomaly_flags,
            "up_probability": up_probability,
        },
        "score_explanations": {
            "pressure": f"{pressure_score:.2f} means how strongly the combined price trend, news themes, and model signal argue for acting now rather than waiting.",
            "risk": f"{risk_score:.2f} measures how costly it could be to delay because of volatility, uncertainty, and unstable market conditions.",
            "conviction": f"{conviction_score:.2f} reflects how much price action, historical analogs, and recent news agree with one another.",
        },
        "theme_counts": dict(theme_counts),
        "narrative_summary": narrative_summary,
        "decision_story": decision_story,
        "linkage_points": linkage_points,
        "chart_data": chart_data,
        "news_clusters": [cluster.to_dict() for cluster in sorted(relevant_clusters, key=lambda cluster: cluster.date, reverse=True)],
        "analog_events": [impact.to_dict() for impact in relevant_impacts],
        "model": trained_model or {},
    }

    return DecisionRecommendation(
        metal=metal,
        horizon=horizon,
        decision_date=decision_date,
        risk_appetite=appetite,
        action=action,
        confidence=round(confidence, 2),
        confidence_band=confidence_band,
        pressure_score=round(pressure_score, 2),
        risk_score=round(risk_score, 2),
        conviction_score=round(conviction_score, 2),
        rationale=rationale[:5],
        counterpoints=counterpoints[:3],
        triggers_to_watch=triggers_to_watch[:3],
        scenarios=scenarios,
        recommended_actions=recommended_actions,
        historical_performance=historical_performance,
        why_now=why_now,
    )
