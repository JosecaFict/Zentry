import { TestBed } from '@angular/core/testing';
import { afterEach, expect, it, vi } from 'vitest';

import { ConnectivityService } from './connectivity.service';

afterEach(() => vi.unstubAllGlobals());

it.each([
  ['server responds', () => Promise.resolve(new Response('{}', { status: 200 })), true],
  ['server answers 4xx', () => Promise.resolve(new Response('{}', { status: 404 })), true],
  ['server is down', () => Promise.resolve(new Response('', { status: 503 })), false],
  ['there is no internet', () => Promise.reject(new TypeError('Failed to fetch')), false],
])('is online only when the backend answers: %s', async (_name, fetch, expected) => {
  vi.stubGlobal('fetch', vi.fn(fetch));
  const service = TestBed.inject(ConnectivityService);

  await expect(service.check()).resolves.toBe(expected);

  expect(service.online()).toBe(expected);
  expect(service.checkedAt()).not.toBeNull();
  expect(service.offlineSince() === null).toBe(expected);
});

it('shares one ping between simultaneous checks', async () => {
  const fetch = vi.fn((_url: string) => Promise.resolve(new Response('{}', { status: 200 })));
  vi.stubGlobal('fetch', fetch);
  const service = TestBed.inject(ConnectivityService);

  await Promise.all([service.check(), service.check()]);

  expect(fetch).toHaveBeenCalledOnce();
  expect(String(fetch.mock.calls[0]?.[0] ?? '')).toContain('/health');
});
