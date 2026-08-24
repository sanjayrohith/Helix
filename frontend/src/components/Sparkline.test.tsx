// Tests the edge cases Sparkline exists to handle correctly: an empty
// series, a flat series, a single point, and threshold recoloring - the
// cases a naive min/max-scaled line chart gets wrong.

import { render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Sparkline } from './Sparkline';

describe('Sparkline', () => {
  it('renders a dashed baseline for an empty series without throwing', () => {
    const { container } = render(<Sparkline values={[]} />);
    const line = container.querySelector('line');
    expect(line).toBeInTheDocument();
    expect(line).toHaveAttribute('stroke-dasharray', '3 3');
  });

  it('renders a path for a normal series', () => {
    const { container } = render(<Sparkline values={[1, 5, 3, 8, 2]} />);
    const path = container.querySelector('path[fill="none"]');
    expect(path).toBeInTheDocument();
    expect(path?.getAttribute('d')).toMatch(/^M/);
  });

  it('does not divide by zero for a perfectly flat series', () => {
    const { container } = render(<Sparkline values={[5, 5, 5, 5]} width={100} height={40} />);
    const path = container.querySelector('path[fill="none"]');
    const d = path?.getAttribute('d') ?? '';
    // A flat series must not collapse every point to the same y (which a
    // naive (v - min) / (max - min) with max === min would produce as NaN).
    expect(d).not.toContain('NaN');
  });

  it('renders a single point centred rather than crashing', () => {
    const { container } = render(<Sparkline values={[42]} />);
    const circle = container.querySelector('circle');
    expect(circle).toBeInTheDocument();
  });

  it('uses the warning color when the latest value breaches the threshold', () => {
    const { container } = render(
      <Sparkline values={[1, 2, 10]} threshold={5} color="#00d4ff" warningColor="#ff4444" />,
    );
    const path = container.querySelector('path[fill="none"]');
    expect(path).toHaveAttribute('stroke', '#ff4444');
  });

  it('uses the normal color when the latest value is under the threshold', () => {
    const { container } = render(
      <Sparkline values={[1, 2, 3]} threshold={10} color="#00d4ff" warningColor="#ff4444" />,
    );
    const path = container.querySelector('path[fill="none"]');
    expect(path).toHaveAttribute('stroke', '#00d4ff');
  });

  it('draws a threshold line only when the threshold falls within the data range', () => {
    const { container: withinRange } = render(
      <Sparkline values={[1, 5, 10]} threshold={5} />,
    );
    expect(withinRange.querySelectorAll('line').length).toBeGreaterThan(0);

    const { container: outOfRange } = render(
      <Sparkline values={[1, 5, 10]} threshold={1000} />,
    );
    expect(outOfRange.querySelectorAll('line').length).toBe(0);
  });

  it('respects custom width and height', () => {
    const { container } = render(<Sparkline values={[1, 2, 3]} width={200} height={60} />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('width', '200');
    expect(svg).toHaveAttribute('height', '60');
  });

  it('sets an accessible label including the latest value when a label is given', () => {
    const { container } = render(<Sparkline values={[1, 2, 3.456]} label="Latency" />);
    const svg = container.querySelector('svg');
    expect(svg).toHaveAttribute('aria-label', 'Latency: 3.46');
  });
});
