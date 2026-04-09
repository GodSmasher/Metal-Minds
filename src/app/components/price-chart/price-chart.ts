import { Component, inject, OnInit, ElementRef, viewChild, effect } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { SignalApi } from '../../services/signal-api';

declare const Plotly: any;

@Component({
  selector: 'app-price-chart',
  imports: [DecimalPipe],
  templateUrl: './price-chart.html',
  styleUrl: './price-chart.scss',
})
export class PriceChart implements OnInit {
  api = inject(SignalApi);
  chartEl = viewChild<ElementRef>('chart');

  constructor() {
    effect(() => {
      const data = this.api.priceData();
      if (this.chartEl() && data.length) this.render(data);
    });
  }

  ngOnInit() {
    this.loadPlotly();
  }

  private loadPlotly() {
    if (typeof Plotly !== 'undefined') return;
    const script = document.createElement('script');
    script.src = 'https://cdn.plot.ly/plotly-2.35.0.min.js';
    script.onload = () => this.render(this.api.priceData());
    document.head.appendChild(script);
  }

  private render(bars: any[]) {
    if (typeof Plotly === 'undefined' || !this.chartEl()) return;
    const trace = {
      x: bars.map(b => b.date),
      open: bars.map(b => b.open),
      high: bars.map(b => b.high),
      low: bars.map(b => b.low),
      close: bars.map(b => b.close),
      type: 'candlestick',
      increasing: { line: { color: '#00c896' } },
      decreasing: { line: { color: '#e24b4a' } },
    };
    const layout = {
      paper_bgcolor: '#161b22',
      plot_bgcolor: '#161b22',
      font: { color: '#8b949e', size: 11 },
      xaxis: { gridcolor: '#30363d', rangeslider: { visible: false } },
      yaxis: { gridcolor: '#30363d', side: 'right' },
      margin: { t: 10, r: 50, b: 40, l: 10 },
      height: 350,
    };
    Plotly.newPlot(this.chartEl()!.nativeElement, [trace], layout, { responsive: true, displayModeBar: false });
  }
}
