import { TestBed } from '@angular/core/testing';
import { ActivatedRoute } from '@angular/router';
import { Subject } from 'rxjs';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AIReportResponse } from '../../core/models/reports.model';
import { CatalogService } from '../../core/services/catalog.service';
import { ReportsService } from '../../core/services/reports.service';
import { ReportsAdmin } from './reports-admin';

class TestRecorder {
  static isTypeSupported() { return true; }
  readonly mimeType = 'audio/webm';
  state: RecordingState = 'inactive';
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;

  start() { this.state = 'recording'; }

  stop() {
    this.state = 'inactive';
    this.ondataavailable?.({ data: new Blob(['audio']) });
    this.onstop?.();
  }
}

describe('ReportsAdmin voice input', () => {
  afterEach(() => vi.unstubAllGlobals());

  function setup() {
    const transcription = new Subject<{ texto: string }>();
    const response = new Subject<AIReportResponse>();
    const reports = {
      transcribeVoice: vi.fn(() => transcription),
      askAssistant: vi.fn(() => response),
    };
    vi.stubGlobal('MediaRecorder', TestRecorder);
    vi.stubGlobal('navigator', {
      mediaDevices: { getUserMedia: vi.fn(async () => ({ getTracks: () => [{ stop: vi.fn() }] })) },
    });
    TestBed.configureTestingModule({
      imports: [ReportsAdmin],
      providers: [
        { provide: ReportsService, useValue: reports },
        { provide: CatalogService, useValue: {} },
        { provide: ActivatedRoute, useValue: {} },
      ],
    }).overrideComponent(ReportsAdmin, { set: { template: '' } });
    const fixture = TestBed.createComponent(ReportsAdmin);
    return { fixture, component: fixture.componentInstance, reports, transcription };
  }

  it('submits the transcript once with the selected branch after stopping', async () => {
    const { component, reports, transcription } = setup();
    component.branchId = 4;
    await component.toggleVoiceRecording();
    await component.toggleVoiceRecording();

    expect(reports.transcribeVoice).toHaveBeenCalledOnce();
    expect(reports.askAssistant).not.toHaveBeenCalled();
    transcription.next({ texto: '  ¿Cuál fue la prenda más vendida?  ' });
    component.askAssistant();

    expect(component.aiQuestion).toBe('¿Cuál fue la prenda más vendida?');
    expect(reports.askAssistant).toHaveBeenCalledExactlyOnceWith(component.aiQuestion, 4);
  });

  it('does not submit the previous question when the transcript is empty', async () => {
    const { component, reports, transcription } = setup();
    component.aiQuestion = 'Una consulta anterior';
    await component.toggleVoiceRecording();
    await component.toggleVoiceRecording();
    transcription.next({ texto: ' ' });

    expect(reports.askAssistant).not.toHaveBeenCalled();
    expect(component.voiceMessage()).toContain('No se detectó');
  });
});
