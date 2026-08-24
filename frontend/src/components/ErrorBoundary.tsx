import { Component, type ErrorInfo, type ReactNode } from 'react';

interface ErrorBoundaryProps {
  children: ReactNode;
  /** A short name for what this boundary wraps, shown in the fallback and logs. */
  section?: string;
  /** Custom fallback; otherwise a generic inline panel is rendered. */
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  error: Error | null;
}

/**
 * Catches a render error in its subtree and shows a fallback instead of
 * blanking the whole page. React error boundaries are still class
 * components only - there is no hook equivalent - hence the older style
 * here, deliberately isolated to this one component.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error(`[ErrorBoundary${this.props.section ? `:${this.props.section}` : ''}]`, error, info.componentStack);
  }

  private reset = (): void => {
    this.setState({ error: null });
  };

  render(): ReactNode {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback) return this.props.fallback;

    return (
      <div
        role="alert"
        className="rounded-2xl border border-rose-300/30 bg-rose-400/[0.06] p-5 text-sm"
      >
        <p className="font-syne font-semibold text-rose-200">
          {this.props.section ? `${this.props.section} failed to render` : 'Something went wrong'}
        </p>
        <p className="mt-1 text-xs text-slate-300">
          The rest of the dashboard is unaffected. Reloading usually clears this.
        </p>
        <p className="mt-2 font-mono text-[11px] text-rose-300/80">
          {this.state.error.message}
        </p>
        <button
          type="button"
          onClick={this.reset}
          className="mt-3 rounded-lg border border-white/15 px-3 py-1.5 font-syne text-xs text-slate-200 transition-colors hover:border-cyan/40 hover:text-white"
        >
          Try again
        </button>
      </div>
    );
  }
}
