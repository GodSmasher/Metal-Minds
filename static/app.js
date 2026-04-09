async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

function setList(elementId, items) {
  const container = document.getElementById(elementId);
  container.innerHTML = "";
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    container.appendChild(li);
  });
}

function renderPriceContext(context) {
  const container = document.getElementById("price-context");
  container.innerHTML = "";
  const metrics = [
    ["Latest price", context.latestPrice],
    ["1d return", `${context.return1d}%`],
    ["5d return", `${context.return5d}%`],
    ["20d return", `${context.return20d}%`],
    ["20d vol", `${context.volatility}%`],
    ["Up prob", `${context.upProbability}%`],
    ["Z-score", context.zscore],
  ];
  metrics.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "kpi-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    container.appendChild(card);
  });
}

function renderThemes(themeCounts) {
  const container = document.getElementById("theme-tags");
  container.innerHTML = "";
  Object.entries(themeCounts).forEach(([theme, count]) => {
    const tag = document.createElement("span");
    tag.className = "tag";
    tag.textContent = `${theme} (${count})`;
    container.appendChild(tag);
  });
}

function renderScenarios(scenarios) {
  const container = document.getElementById("scenario-grid");
  container.innerHTML = "";
  Object.entries(scenarios).forEach(([label, value]) => {
    const card = document.createElement("article");
    card.className = "scenario-card";
    card.innerHTML = `
      <h4>${label}</h4>
      <p><strong>${value.probability_pct}% likely</strong> • ${value.direction} ${value.price_change_pct}%</p>
      <p>${value.narrative}</p>
    `;
    container.appendChild(card);
  });
}

function renderPredictionTable(chartData) {
  const container = document.getElementById("prediction-table");
  const forecast = chartData.forecast || [];
  const actualFuture = chartData.actual_future || [];
  const actualByLabel = Object.fromEntries(actualFuture.map((point) => [point.label, point.price]));

  if (!forecast.length) {
    container.innerHTML = `<p class="subtle">No forward projection is available for the selected horizon.</p>`;
    return;
  }

  const rows = forecast
    .map((point) => {
      const predicted = point.base;
      const actual = actualByLabel[point.label];
      const diffPct = actual == null || actual === 0 ? null : ((predicted - actual) / actual) * 100;
      return `
        <tr>
          <td>${point.label}</td>
          <td>${predicted.toFixed(2)}</td>
          <td>${actual == null ? "-" : actual.toFixed(2)}</td>
          <td>${diffPct == null ? "-" : `${diffPct.toFixed(2)}%`}</td>
        </tr>
      `;
    })
    .join("");

  container.innerHTML = `
    <table class="prediction-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Predicted Price</th>
          <th>Actual Price</th>
          <th>% Difference</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderNewsClusters(items) {
  const container = document.getElementById("news-clusters");
  container.innerHTML = "";
  items.forEach((cluster) => {
    const article = document.createElement("article");
    article.innerHTML = `
      <h4>${cluster.theme}</h4>
      <p>${cluster.summary}</p>
      <p><strong>${cluster.date}</strong> • ${cluster.article_count} articles • ${cluster.uncertainty} uncertainty</p>
    `;
    container.appendChild(article);
  });
}

function renderAnalogEvents(items) {
  const container = document.getElementById("analog-events");
  container.innerHTML = "";
  items.forEach((impact) => {
    const article = document.createElement("article");
    article.innerHTML = `
      <h4>${impact.reaction_label}</h4>
      <p>${impact.horizon} reaction: ${(impact.avg_reaction * 100).toFixed(1)}% • confidence ${(impact.confidence * 100).toFixed(0)}%</p>
      <p>${impact.lead_lag_signal}</p>
    `;
    container.appendChild(article);
  });
}

async function loadDashboard() {
  const metal = document.getElementById("metal-select").value;
  const date = document.getElementById("date-select").value;
  const horizon = document.getElementById("horizon-select").value;
  const params = new URLSearchParams({ metal, horizon, date, risk_appetite: "high" });
  const decision = await fetchJson(`/api/decision?${params.toString()}`);

  document.getElementById("decision-action").textContent = decision.action;
  document.getElementById("decision-summary").textContent = `Confidence ${(decision.confidence * 100).toFixed(0)}% • ${decision.horizon} • ${decision.decision_date}`;
  document.getElementById("confidence-pill").textContent = `${decision.confidence_band} confidence`;
  document.getElementById("pressure-score").textContent = decision.pressure_score;
  document.getElementById("risk-score").textContent = decision.risk_score;
  document.getElementById("conviction-score").textContent = decision.conviction_score;
  document.getElementById("pressure-help").textContent = decision.why_now.score_explanations.pressure;
  document.getElementById("risk-help").textContent = decision.why_now.score_explanations.risk;
  document.getElementById("conviction-help").textContent = decision.why_now.score_explanations.conviction;
  document.getElementById("regime-badge").textContent = decision.why_now.price_context.regime;
  document.getElementById("narrative-summary").textContent = decision.why_now.narrative_summary;

  setList("rationale-list", decision.rationale);
  setList("triggers-list", decision.triggers_to_watch);
  setList("actions-list", decision.recommended_actions);
  setList("counterpoints-list", decision.counterpoints);
  setList("decision-story-list", decision.why_now.decision_story);
  setList("linkage-list", decision.why_now.linkage_points);

  renderPriceContext({
    latestPrice: decision.why_now.latest_price.toFixed(0),
    return1d: decision.why_now.price_context.return_1d_pct.toFixed(2),
    return5d: decision.why_now.price_context.return_5d_pct.toFixed(2),
    return20d: decision.why_now.price_context.return_20d_pct.toFixed(2),
    volatility: decision.why_now.price_context.volatility_20d_pct.toFixed(2),
    zscore: decision.why_now.price_context.zscore_20d.toFixed(2),
    upProbability: (decision.why_now.price_context.up_probability * 100).toFixed(0),
  });
  renderThemes(decision.why_now.theme_counts);
  renderScenarios(decision.scenarios);
  renderPredictionTable(decision.why_now.chart_data);
  renderHistorical(decision.historical_performance);

  const [news, analogs] = await Promise.all([
    fetchJson(`/api/news-clusters?metal=${metal}&date=${date}`),
    fetchJson(`/api/analog-events?metal=${metal}`),
  ]);
  renderNewsClusters(news.items.slice(-5).reverse());
  renderAnalogEvents(analogs.items.slice(-5).reverse());
}

function renderHistorical(performance) {
  document.getElementById("verification-pill").textContent = performance.verification_status;
  const kpis = document.getElementById("historical-kpis");
  kpis.innerHTML = "";
  const metrics = [
    ["Entry", performance.entry_price],
    ["Future", performance.future_price],
    ["Realized move", `${performance.realized_return_pct}%`],
    ["Horizon end", performance.horizon_end_date],
  ];
  metrics.forEach(([label, value]) => {
    const card = document.createElement("div");
    card.className = "kpi-card";
    card.innerHTML = `<span>${label}</span><strong>${value}</strong>`;
    kpis.appendChild(card);
  });
  const interpretation = document.getElementById("historical-list");
  interpretation.innerHTML = "";
  const items = [
    `Expected direction: ${performance.benchmark.expected_direction}.`,
    `Actual direction: ${performance.benchmark.actual_direction}.`,
    performance.evaluation_available
      ? `Recommendation ${performance.recommendation_was_correct ? "matched" : "did not match"} realized price behavior.`
      : "There is not enough future data after this date to verify the call yet.",
  ];
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    interpretation.appendChild(li);
  });
}

async function loadDates() {
  const metal = document.getElementById("metal-select").value;
  const response = await fetchJson(`/api/dates?metal=${metal}`);
  const select = document.getElementById("date-select");
  const previous = select.value;
  select.innerHTML = "";
  response.dates.forEach((date) => {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = date;
    select.appendChild(option);
  });
  select.value = previous && response.dates.includes(previous) ? previous : response.dates[response.dates.length - 1];
}

async function init() {
  const metalsResponse = await fetchJson("/api/metals");
  const select = document.getElementById("metal-select");
  metalsResponse.metals.forEach((metal) => {
    const option = document.createElement("option");
    option.value = metal;
    option.textContent = metal.charAt(0).toUpperCase() + metal.slice(1);
    select.appendChild(option);
  });
  await loadDates();
  select.addEventListener("change", async () => {
    await loadDates();
    await loadDashboard();
  });
  document.getElementById("date-select").addEventListener("change", loadDashboard);
  document.getElementById("horizon-select").addEventListener("change", loadDashboard);
  document.getElementById("refresh-button").addEventListener("click", async () => {
    await fetchJson("/api/refresh");
    await loadDates();
    await loadDashboard();
  });
  await loadDashboard();
}

init().catch((error) => {
  document.body.innerHTML = `<pre>${error.message}</pre>`;
});
