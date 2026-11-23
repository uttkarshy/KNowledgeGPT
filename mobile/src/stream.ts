import type { Citation } from './types.ts';

export interface StreamEvent {type: 'delta' | 'done' | 'no_answer' | 'error'; delta?: string; message_id?: string; citations?: Citation[]; error?: string}

// SSE line endings can span transport chunks. Decode UTF-8 incrementally in the caller.
export class AnswerStream {
  private pending = '';
  private terminal = false;

  push(text: string): StreamEvent[] {
    this.pending += text;
    const events: StreamEvent[] = [];
    let boundary: RegExpExecArray | null;
    while ((boundary = /\r?\n\r?\n/.exec(this.pending))) {
      const frame = this.pending.slice(0, boundary.index);
      this.pending = this.pending.slice(boundary.index + boundary[0].length);
      const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:'))
        .map(line => line.slice(5).trimStart()).join('\n');
      if (!data) continue;
      const item = JSON.parse(data) as StreamEvent;
      if (!item || !['delta', 'done', 'no_answer', 'error'].includes(item.type) || this.terminal) {
        throw new Error('The service returned an invalid answer stream.');
      }
      if (item.type === 'delta' && typeof item.delta !== 'string') throw new Error('Invalid answer text.');
      if (item.type !== 'delta') this.terminal = true;
      events.push(item);
    }
    if (this.pending.length > 2_000_000) throw new Error('The answer exceeded the stream limit.');
    return events;
  }

  finish() {
    if (!this.terminal || this.pending.trim()) throw new Error('The connection closed before the answer finished. Check history before retrying.');
  }
}
