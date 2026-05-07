import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { shouldSearchPlaces } from './searchState.js';

describe('shouldSearchPlaces', () => {
  it('does not search blank queries', () => {
    assert.equal(shouldSearchPlaces('   ', ''), false);
  });

  it('does not search the just-selected label again', () => {
    assert.equal(
      shouldSearchPlaces('123 Main St, Toronto, ON', '123 Main St, Toronto, ON'),
      false,
    );
  });

  it('searches when the user edits after selecting a label', () => {
    assert.equal(
      shouldSearchPlaces('123 Main', '123 Main St, Toronto, ON'),
      true,
    );
  });
});
