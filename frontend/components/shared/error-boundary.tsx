"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";

import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
  fallbackTitle?: string;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

/**
 * React error boundary that catches rendering errors and shows a friendly
 * fallback instead of a blank screen. Mount it in the dashboard layout
 * so a single broken component doesn't take down the whole app.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In production this would go to Sentry
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center px-4 py-24 text-center">
          <AlertTriangle className="mb-4 h-10 w-10 text-amber-500" />
          <h2 className="text-lg font-semibold">
            {this.props.fallbackTitle || "Something went wrong"}
          </h2>
          <p className="mt-2 max-w-md text-sm text-muted-foreground">
            An unexpected error occurred. Try refreshing the page. If the
            problem persists, contact support.
          </p>
          <Button
            className="mt-6"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
          >
            Reload page
          </Button>
        </div>
      );
    }
    return this.props.children;
  }
}
