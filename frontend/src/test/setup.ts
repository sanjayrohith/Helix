// Global test setup: extends Vitest's `expect` with jest-dom matchers
// (toBeInTheDocument, toHaveTextContent, ...) and unmounts every rendered
// component between tests. React Testing Library normally wires this
// cleanup automatically when it detects a global `afterEach`, but this
// project deliberately runs with `test.globals: false` (explicit imports
// over ambient globals), so it has to be registered by hand here instead -
// otherwise components rendered in one test stay mounted into the next,
// which shows up as "found multiple elements" failures with no obvious
// connection to the actual change under test.
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

afterEach(() => {
  cleanup();
});
