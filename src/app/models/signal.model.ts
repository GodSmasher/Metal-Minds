export interface SignalResponse {
  decision: 'BUY NOW' | 'HOLD' | 'HEDGE';
  confidence: 'HIGH' | 'MEDIUM' | 'LOW';
  rationale: string;
  brief: string;
  model: string;
  npi: number;
  top_articles: Article[];
  timestamp: string;
}

export interface Article {
  title: string;
  source: string;
  url: string;
  sentiment: number;
  published: string;
}

export interface OHLCVBar {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export type Commodity = 'Cocoa' | 'Copper' | 'Coffee';
