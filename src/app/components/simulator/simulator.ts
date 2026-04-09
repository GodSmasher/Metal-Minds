import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { DecimalPipe } from '@angular/common';
import { SignalApi } from '../../services/signal-api';

@Component({
  selector: 'app-simulator',
  imports: [FormsModule, DecimalPipe],
  templateUrl: './simulator.html',
  styleUrl: './simulator.scss',
})
export class Simulator {
  api = inject(SignalApi);

  npi = signal(0.72);
  confidence = signal(0.85);
  volatility = signal(0.3);

  async recalculate() {
    await this.api.fetchSignal({
      npi: this.npi(),
      confidence: this.confidence(),
      volatility: this.volatility(),
    });
  }
}
