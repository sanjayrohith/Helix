// Tests for the API client's error handling and URL construction, mocking
// global fetch rather than hitting a real backend.

import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  exportUrl,
  fetchExport,
  getAllSlices,
  provisionSlice,
} from './api';

function jsonResponse(body: unknown, init: Partial<Response> & { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('ApiError', () => {
  it('marks 429 as transient', () => {
    expect(new ApiError(429, 'rate limited').isTransient).toBe(true);
  });

  it('marks 5xx as transient', () => {
    expect(new ApiError(500, 'boom').isTransient).toBe(true);
    expect(new ApiError(503, 'boom').isTransient).toBe(true);
  });

  it('marks 4xx other than 429 as not transient', () => {
    expect(new ApiError(404, 'missing').isTransient).toBe(false);
    expect(new ApiError(403, 'forbidden').isTransient).toBe(false);
  });

  it('marks a network failure (status 0) as not transient', () => {
    // Status 0 means "never got an HTTP response at all" - retrying blindly
    // is a caller decision, not something isTransient should encourage here.
    expect(new ApiError(0, 'network error').isTransient).toBe(false);
  });
});

describe('request error handling', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('throws an ApiError with the backend detail on a non-2xx response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ detail: 'Slice not found' }, { status: 404 })));

    await expect(getAllSlices()).rejects.toMatchObject({
      status: 404,
      message: 'Slice not found',
    });
  });

  it('falls back to statusText when the error body is not JSON', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response('not json', { status: 500, statusText: 'Internal Server Error' }),
      ),
    );

    await expect(getAllSlices()).rejects.toMatchObject({ status: 500 });
  });

  it('wraps a network-level failure as a status-0 ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    await expect(getAllSlices()).rejects.toMatchObject({
      status: 0,
      message: 'Failed to fetch',
    });
  });

  it('resolves with the parsed body on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse([{ slice_id: 'a' }])));

    const result = await getAllSlices();
    expect(result).toEqual([{ slice_id: 'a' }]);
  });
});

describe('request construction', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('sends the intent as a JSON body on provision', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ success: true }));
    vi.stubGlobal('fetch', fetchMock);

    await provisionSlice('an intent');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ intent: 'an intent' });
  });

  it('omits undefined and empty-string filters from the query string', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse([]));
    vi.stubGlobal('fetch', fetchMock);

    await getAllSlices({ use_case: 'iot', location: '', status: undefined });

    const [url] = fetchMock.mock.calls[0];
    expect(url).toContain('use_case=iot');
    expect(url).not.toContain('location=');
    expect(url).not.toContain('status=');
  });
});

describe('export helpers', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('exportUrl builds a download URL with the format and slice id', () => {
    const url = exportUrl('kubernetes', 'slice-123');
    expect(url).toContain('/api/export/slices/slice-123');
    expect(url).toContain('format=kubernetes');
    expect(url).toContain('download=true');
  });

  it('exportUrl omits the slice id for a network-wide export', () => {
    const url = exportUrl('json');
    expect(url).toContain('/api/export/slices');
    expect(url).not.toContain('/api/export/slices/');
  });

  it('fetchExport returns the response body as text', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('apiVersion: v1', { status: 200 })),
    );

    const text = await fetchExport('kubernetes', 'slice-1');
    expect(text).toBe('apiVersion: v1');
  });

  it('fetchExport throws an ApiError on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(new Response('nope', { status: 404, statusText: 'Not Found' })),
    );

    await expect(fetchExport('kubernetes', 'missing')).rejects.toBeInstanceOf(ApiError);
  });
});
