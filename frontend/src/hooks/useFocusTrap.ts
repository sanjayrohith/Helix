import { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(', ');

/**
 * Keeps keyboard focus inside a modal-style container while it is open.
 *
 * A dialog that only closes on click (or ignores focus entirely) strands a
 * keyboard or screen-reader user: Tab still cycles through whatever is
 * behind it, and closing it never returns focus to wherever they were
 * before it opened. This handles the three things a modal needs: focus
 * moves in when it opens, Tab/Shift+Tab cannot escape the container while
 * it is open, and focus returns to the element that had it beforehand once
 * it closes.
 */
export function useFocusTrap(active: boolean) {
  const containerRef = useRef<HTMLElement | null>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!active) return;

    previouslyFocused.current = document.activeElement as HTMLElement | null;

    const container = containerRef.current;
    const focusFirst = () => {
      const focusable = container?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR);
      (focusable?.[0] ?? container)?.focus();
    };
    // Deferred a tick: the container may not be in the DOM yet on the same
    // render that flips `active` to true.
    const raf = requestAnimationFrame(focusFirst);

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Tab' || !container) return;

      // Not filtering by visibility (e.g. offsetParent): that check relies
      // on layout, which jsdom - and therefore this hook's own test suite -
      // does not implement, so it would silently behave differently under
      // test than in a real browser. None of the panels this hook wraps
      // render a hidden-but-focusable element in practice.
      const focusable = Array.from(
        container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
      );
      if (focusable.length === 0) return;

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const current = document.activeElement;

      if (event.shiftKey && current === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && current === last) {
        event.preventDefault();
        first.focus();
      } else if (!container.contains(current)) {
        // Focus escaped the container by some other means; pull it back in.
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused.current?.focus();
    };
  }, [active]);

  return containerRef;
}
