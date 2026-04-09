import { CommonModule } from '@angular/common';
import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { firstValueFrom } from 'rxjs';

type RiskAppetite = 'low' | 'medium' | 'high';

interface DecisionResponse {
  metal: string;
  horizon: string;
  decision_date: string;
  risk_appetite: RiskAppetite;
  action: string;
  confidence: number;
  confidence_band: string;
  pressure_score: number;
  risk_score: number;
  conviction_score: number;
  rationale: string[];
  counterpoints: string[];
  triggers_to_watch: string[];
  recommended_actions: string[];
  scenarios: Record<string, { direction: string; price_change_pct: number; narrative: string }>;
  historical_performance: {
    evaluation_available: boolean;
    verification_status: string;
    horizon_end_date: string;
    entry_price: number;
    future_price: number;
    realized_return_pct: number;
    recommendation_was_correct: boolean | null;
    benchmark: { expected_direction: string; actual_direction: string };
  };
  why_now: {
    latest_price: number;
    price_context: {
      return_1d_pct: number;
      return_5d_pct: number;
      return_20d_pct: number;
      volatility_20d_pct: number;
      zscore_20d: number;
      regime: string;
      up_probability: number;
    };
    theme_counts: Record<string, number>;
    news_clusters: Array<{ theme: string; summary: string; date: string; article_count: number; uncertainty: string }>;
    analog_events: Array<{ reaction_label: string; horizon: string; avg_reaction: number; confidence: number; lead_lag_signal: string }>;
  };
}

@Component({
  selector: 'app-root',
  imports: [CommonModule, FormsModule],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  private readonly http = inject(HttpClient);
  protected readonly metals = signal<string[]>([]);
  protected readonly dates = signal<string[]>([]);
  protected readonly decision = signal<DecisionResponse | null>(null);
  protected readonly loading = signal(false);
  protected readonly error = signal('');

  protected selectedMetal = 'copper';
  protected selectedDate = '';
  protected selectedHorizon = '10d';
  protected selectedRisk: RiskAppetite = 'medium';

  async ngOnInit(): Promise<void> {
    await this.loadMetals();
    await this.loadDates();
    await this.loadDecision();
  }

  protected async onMetalChange(): Promise<void> {
    await this.loadDates();
    await this.loadDecision();
  }

  protected async onFiltersChange(): Promise<void> {
    await this.loadDecision();
  }

  protected objectEntries(value: Record<string, number>) {
    return Object.entries(value);
  }

  protected scenarioEntries(value: DecisionResponse['scenarios']) {
    return Object.entries(value);
  }

  private async loadMetals(): Promise<void> {
    const response = await firstValueFrom(this.http.get<{ metals: string[] }>('/api/metals'));
    this.metals.set(response.metals);
    if (response.metals.length > 0 && !response.metals.includes(this.selectedMetal)) {
      this.selectedMetal = response.metals[0];
    }
  }

  private async loadDates(): Promise<void> {
    const response = await firstValueFrom(
      this.http.get<{ dates: string[] }>(`/api/dates?metal=${encodeURIComponent(this.selectedMetal)}`),
    );
    this.dates.set(response.dates);
    this.selectedDate = response.dates[response.dates.length - 1] || '';
  }

  private async loadDecision(): Promise<void> {
    this.loading.set(true);
    this.error.set('');
    try {
      const params = new URLSearchParams({
        metal: this.selectedMetal,
        date: this.selectedDate,
        horizon: this.selectedHorizon,
        risk_appetite: this.selectedRisk,
      });
      const response = await firstValueFrom(
        this.http.get<DecisionResponse>(`/api/decision?${params.toString()}`),
      );
      this.decision.set(response);
    } catch (error) {
      this.error.set(error instanceof Error ? error.message : 'Failed to load decision.');
    } finally {
      this.loading.set(false);
    }
  }
}
