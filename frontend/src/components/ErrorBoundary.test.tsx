import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

function Bomb({ armed }: { armed: boolean }): never | null {
  if (armed) throw new Error('kaboom');
  return null;
}

describe('ErrorBoundary', () => {
  let consoleError: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // React logs the caught error to console.error itself; suppress the
    // noise in test output without hiding a genuinely unexpected failure.
    consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleError.mockRestore();
  });

  it('renders children normally when nothing throws', () => {
    render(
      <ErrorBoundary>
        <div>content renders fine</div>
      </ErrorBoundary>,
    );
    expect(screen.getByText('content renders fine')).toBeInTheDocument();
  });

  it('renders a fallback instead of crashing when a child throws', () => {
    render(
      <ErrorBoundary>
        <Bomb armed />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();
  });

  it('includes the section name in the fallback when provided', () => {
    render(
      <ErrorBoundary section="Topology panel">
        <Bomb armed />
      </ErrorBoundary>,
    );
    expect(screen.getByText(/Topology panel failed to render/)).toBeInTheDocument();
  });

  it('shows the error message for diagnosis', () => {
    render(
      <ErrorBoundary>
        <Bomb armed />
      </ErrorBoundary>,
    );
    expect(screen.getByText('kaboom')).toBeInTheDocument();
  });

  it('renders a custom fallback when one is given', () => {
    render(
      <ErrorBoundary fallback={<div>custom fallback</div>}>
        <Bomb armed />
      </ErrorBoundary>,
    );
    expect(screen.getByText('custom fallback')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('one boundary catching an error does not affect a sibling boundary', () => {
    render(
      <>
        <ErrorBoundary section="A">
          <Bomb armed />
        </ErrorBoundary>
        <ErrorBoundary section="B">
          <div>sibling still renders</div>
        </ErrorBoundary>
      </>,
    );
    expect(screen.getByText(/A failed to render/)).toBeInTheDocument();
    expect(screen.getByText('sibling still renders')).toBeInTheDocument();
  });

  it('"Try again" resets the boundary so it can render children again on retry', async () => {
    const user = userEvent.setup();
    let armed = true;

    function Toggle() {
      return <Bomb armed={armed} />;
    }

    const { rerender } = render(
      <ErrorBoundary>
        <Toggle />
      </ErrorBoundary>,
    );
    expect(screen.getByRole('alert')).toBeInTheDocument();

    armed = false;
    await user.click(screen.getByRole('button', { name: /try again/i }));
    rerender(
      <ErrorBoundary>
        <Toggle />
      </ErrorBoundary>,
    );

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
