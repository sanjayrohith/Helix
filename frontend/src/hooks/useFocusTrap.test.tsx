import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { useFocusTrap } from './useFocusTrap';

function Modal({ active, onClose }: { active: boolean; onClose: () => void }) {
  const ref = useFocusTrap(active);
  if (!active) return null;
  return (
    <div ref={ref as React.RefObject<HTMLDivElement>} data-testid="modal">
      <button>First</button>
      <button>Second</button>
      <button onClick={onClose}>Last</button>
    </div>
  );
}

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button onClick={() => setOpen(true)}>Open trigger</button>
      <Modal active={open} onClose={() => setOpen(false)} />
    </div>
  );
}

describe('useFocusTrap', () => {
  it('moves focus into the container when activated', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open trigger' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
    });
  });

  // jsdom implements no native tab-order focus movement at all - a real
  // browser's Tab key press is what the hook's keydown listener overrides
  // via preventDefault(), but jsdom has nothing to override. userEvent.tab()
  // papers over this by re-simulating "what a browser would do" in JS,
  // entirely independently of this page's own keydown listeners - so it
  // cannot exercise this hook's logic at all. Dispatching the raw keydown
  // the hook actually listens for is the only way to test it under jsdom.
  it('Tab from the last focusable element wraps to the first', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open trigger' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'First' })).toHaveFocus());

    screen.getByRole('button', { name: 'Last' }).focus();
    fireEvent.keyDown(document, { key: 'Tab' });

    expect(screen.getByRole('button', { name: 'First' })).toHaveFocus();
  });

  it('Shift+Tab from the first focusable element wraps to the last', async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Open trigger' }));
    await waitFor(() => expect(screen.getByRole('button', { name: 'First' })).toHaveFocus());

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });

    expect(screen.getByRole('button', { name: 'Last' })).toHaveFocus();
  });

  it('restores focus to the trigger element after closing', async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const trigger = screen.getByRole('button', { name: 'Open trigger' });
    await user.click(trigger);
    await waitFor(() => expect(screen.getByRole('button', { name: 'First' })).toHaveFocus());

    await user.click(screen.getByRole('button', { name: 'Last' }));

    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('does nothing when never activated', () => {
    render(<Harness />);
    // No modal in the DOM, no focus movement, no error - inactive is a no-op.
    expect(screen.queryByTestId('modal')).not.toBeInTheDocument();
  });
});
