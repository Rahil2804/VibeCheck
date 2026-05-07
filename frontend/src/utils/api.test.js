import assert from 'node:assert/strict';
import { afterEach, describe, it } from 'node:test';
import { analyzeNeighborhood, refreshSavedProfile } from './api.js';

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

describe('analyzeNeighborhood', () => {
  it('posts analyze payloads to the backend and returns JSON', async () => {
    const requests = [];
    globalThis.fetch = async (url, options) => {
      requests.push({ url, options });
      return {
        ok: true,
        async json() {
          return { place: { label: 'East Austin' } };
        },
      };
    };

    const result = await analyzeNeighborhood({ query: 'East Austin', generic_mode: true });

    assert.deepEqual(result, { place: { label: 'East Austin' } });
    assert.equal(requests[0].url, 'http://127.0.0.1:8000/analyze');
    assert.equal(requests[0].options.method, 'POST');
    assert.equal(requests[0].options.headers['Content-Type'], 'application/json');
    assert.equal(requests[0].options.body, JSON.stringify({ query: 'East Austin', generic_mode: true }));
  });

  it('uses server detail messages for failed responses', async () => {
    globalThis.fetch = async () => ({
      ok: false,
      status: 422,
      async json() {
        return { detail: 'Provide either query or coordinates.' };
      },
    });

    await assert.rejects(
      () => analyzeNeighborhood({ preferences: {} }),
      /Provide either query or coordinates\./,
    );
  });
});

describe('refreshSavedProfile', () => {
  it('posts to the saved profile refresh endpoint', async () => {
    const requests = [];
    globalThis.fetch = async (url, options) => {
      requests.push({ url, options });
      return {
        ok: true,
        async json() {
          return { id: 'saved-1', response: { place: { label: 'East Austin' } } };
        },
      };
    };

    const result = await refreshSavedProfile('saved-1');

    assert.equal(result.id, 'saved-1');
    assert.equal(requests[0].url, 'http://127.0.0.1:8000/profiles/saved-1/refresh');
    assert.equal(requests[0].options.method, 'POST');
  });
});
