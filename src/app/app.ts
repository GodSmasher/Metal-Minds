import { Component, inject } from '@angular/core';
import { SignalApi } from './services/signal-api';
import { DecisionCard } from './components/decision-card/decision-card';
import { PriceChart } from './components/price-chart/price-chart';
import { NewsFeed } from './components/news-feed/news-feed';
import { Interrogation } from './components/interrogation/interrogation';
import { Simulator } from './components/simulator/simulator';
import { Commodity } from './models/signal.model';

@Component({
  selector: 'app-root',
  imports: [DecisionCard, PriceChart, NewsFeed, Interrogation, Simulator],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App {
  api = inject(SignalApi);
  commodities: Commodity[] = ['Cocoa', 'Copper', 'Coffee'];

  onCommodityChange(event: Event) {
    const val = (event.target as HTMLSelectElement).value as Commodity;
    this.api.switchCommodity(val);
  }
}
