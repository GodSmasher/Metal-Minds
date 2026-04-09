import { Component, computed, inject } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { SignalApi } from '../../services/signal-api';

@Component({
  selector: 'app-decision-card',
  imports: [DecimalPipe],
  templateUrl: './decision-card.html',
  styleUrl: './decision-card.scss',
})
export class DecisionCard {
  api = inject(SignalApi);

  color = computed(() => {
    switch (this.api.signalData().decision) {
      case 'BUY NOW': return '#00c896';
      case 'HOLD': return '#f0a500';
      case 'HEDGE': return '#e24b4a';
    }
  });
}
