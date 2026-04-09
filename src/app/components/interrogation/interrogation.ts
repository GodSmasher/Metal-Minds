import { Component, inject, signal, ElementRef, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { SignalApi } from '../../services/signal-api';

@Component({
  selector: 'app-interrogation',
  imports: [FormsModule],
  templateUrl: './interrogation.html',
  styleUrl: './interrogation.scss',
})
export class Interrogation {
  api = inject(SignalApi);
  input = signal('');
  sending = signal(false);
  messagesEl = viewChild<ElementRef>('messagesContainer');

  async send() {
    const msg = this.input().trim();
    if (!msg || this.sending()) return;
    this.input.set('');
    this.sending.set(true);
    await this.api.sendChat(msg);
    this.sending.set(false);
    setTimeout(() => this.scrollToBottom(), 50);
  }

  onKeydown(event: KeyboardEvent) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }

  private scrollToBottom() {
    const el = this.messagesEl()?.nativeElement;
    if (el) el.scrollTop = el.scrollHeight;
  }
}
