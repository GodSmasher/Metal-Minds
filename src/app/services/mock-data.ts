import { SignalResponse, OHLCVBar } from '../models/signal.model';

// ── Mock Signal Response (bis das Backend steht) ──────────
export const MOCK_SIGNAL: SignalResponse = {
  decision: 'BUY NOW',
  confidence: 'HIGH',
  rationale: 'NPI surged to +0.72 on Ghana supply disruption. XGBoost forecasts 8.2% upside in 5 days. Volatility regime is low — favorable entry.',
  brief: `## Market Assessment\nCocoa futures are trading at $8,420/ton, up 3.1% this week. Ghana's COCOBOD reported a 15% shortfall in forward contracts.\n\n## Key Drivers\n- Supply constraint from West Africa (Ghana + Ivory Coast)\n- Fund positioning is net long but not crowded\n- USD weakness supports commodity prices\n\n## Risk Factors\n- EU deforestation regulation could cap demand\n- El Niño forecast remains uncertain\n\n## Recommendation\nEnter long position at current levels. Set stop at $8,100.`,
  model: 'xgboost-v2-cocoa',
  npi: 0.72,
  top_articles: [
    { title: "Ghana cocoa output falls short of target", source: "Reuters", url: "#", sentiment: 0.85, published: "2026-04-09T08:00:00Z" },
    { title: "Cocoa prices surge on West African supply fears", source: "Bloomberg", url: "#", sentiment: 0.71, published: "2026-04-09T06:30:00Z" },
    { title: "EU deforestation law may reshape cocoa trade", source: "FT", url: "#", sentiment: -0.45, published: "2026-04-08T14:00:00Z" },
    { title: "Hedge funds increase cocoa long positions", source: "CFTC", url: "#", sentiment: 0.62, published: "2026-04-08T12:00:00Z" },
    { title: "Ivory Coast midcrop forecast revised lower", source: "Reuters", url: "#", sentiment: 0.78, published: "2026-04-07T09:15:00Z" },
  ],
  timestamp: new Date().toISOString(),
};

// ── Mock OHLCV Daten (30 Tage Cocoa) ─────────────────────
export function generateMockOHLCV(days = 60): OHLCVBar[] {
  const bars: OHLCVBar[] = [];
  let price = 8200;
  const now = new Date();

  for (let i = days; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const change = (Math.random() - 0.45) * 120;
    const open = price;
    const close = price + change;
    const high = Math.max(open, close) + Math.random() * 60;
    const low = Math.min(open, close) - Math.random() * 60;
    price = close;

    bars.push({
      date: date.toISOString().split('T')[0],
      open: Math.round(open),
      high: Math.round(high),
      low: Math.round(low),
      close: Math.round(close),
      volume: Math.round(50000 + Math.random() * 30000),
    });
  }
  return bars;
}
