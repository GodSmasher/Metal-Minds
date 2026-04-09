import { Component, inject } from '@angular/core';
import { DecimalPipe, DatePipe } from '@angular/common';
import { SignalApi } from '../../services/signal-api';

@Component({
  selector: 'app-news-feed',
  imports: [DecimalPipe, DatePipe],
  templateUrl: './news-feed.html',
  styleUrl: './news-feed.scss',
})
export class NewsFeed {
  api = inject(SignalApi);

  sentimentColor(val: number): string {
    if (val > 0.3) return '#00c896';
    if (val < -0.3) return '#e24b4a';
    return '#f0a500';
  }
}
