import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { SignalResponse, OHLCVBar, Commodity, ChatMessage } from '../models/signal.model';
import { MOCK_SIGNAL, generateMockOHLCV } from './mock-data';

const API_BASE = 'http://localhost:8000';
const USE_MOCK = true; // ← auf false wenn Backend steht

@Injectable({ providedIn: 'root' })
export class SignalApi {
  // ── State ──
  commodity = signal<Commodity>('Cocoa');
  signalData = signal<SignalResponse>(MOCK_SIGNAL);
  priceData = signal<OHLCVBar[]>(generateMockOHLCV());
  chatMessages = signal<ChatMessage[]>([]);
  loading = signal(false);

  // ── Derived ──
  currentPrice = computed(() => {
    const bars = this.priceData();
    return bars.length ? bars[bars.length - 1].close : 0;
  });

  priceChange = computed(() => {
    const bars = this.priceData();
    if (bars.length < 2) return 0;
    const prev = bars[bars.length - 2].close;
    const curr = bars[bars.length - 1].close;
    return ((curr - prev) / prev) * 100;
  });

  constructor(private http: HttpClient) {}

  // ── Fetch Signal Decision ──
  async fetchSignal(overrides?: Record<string, number>): Promise<void> {
    this.loading.set(true);
    try {
      if (USE_MOCK) {
        await this.fakeLag();
        if (overrides) {
          const modified = { ...MOCK_SIGNAL, npi: overrides['npi'] ?? MOCK_SIGNAL.npi };
          if (modified.npi < -0.3) {
            modified.decision = 'HEDGE';
            modified.confidence = 'HIGH';
          } else if (modified.npi < 0.3) {
            modified.decision = 'HOLD';
            modified.confidence = 'MEDIUM';
          } else {
            modified.decision = 'BUY NOW';
            modified.confidence = modified.npi > 0.6 ? 'HIGH' : 'MEDIUM';
          }
          this.signalData.set(modified);
        }
        return;
      }
      const body = { commodity: this.commodity(), ...overrides };
      const res = await this.http.post<SignalResponse>(`${API_BASE}/signal`, body).toPromise();
      if (res) this.signalData.set(res);
    } finally {
      this.loading.set(false);
    }
  }

  // ── Chat ──
  async sendChat(message: string): Promise<void> {
    const msgs = [...this.chatMessages(), { role: 'user' as const, content: message }];
    this.chatMessages.set(msgs);

    if (USE_MOCK) {
      await this.fakeLag(800);
      const reply: ChatMessage = {
        role: 'assistant',
        content: `Based on the current ${this.commodity()} analysis: The NPI is at ${this.signalData().npi.toFixed(2)}, which supports our ${this.signalData().decision} recommendation. ${message.toLowerCase().includes('risk') ? 'Key risk: EU deforestation regulation could suppress demand by 5-8% in Q3.' : 'The supply picture from West Africa remains tight, supporting prices near-term.'}`,
      };
      this.chatMessages.set([...this.chatMessages(), reply]);
      return;
    }

    // Real API: POST /chat { commodity, message, history }
    // TODO: wire when backend ready
  }

  // ── Switch Commodity ──
  switchCommodity(c: Commodity): void {
    this.commodity.set(c);
    this.priceData.set(generateMockOHLCV());
    this.chatMessages.set([]);
    this.fetchSignal();
  }

  private fakeLag(ms = 400): Promise<void> {
    return new Promise(r => setTimeout(r, ms));
  }
}
