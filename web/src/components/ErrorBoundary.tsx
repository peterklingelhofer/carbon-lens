import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            maxWidth: 500,
            margin: "0 auto",
            padding: "4rem 2rem",
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontSize: "3rem",
              fontWeight: 700,
              color: "var(--red-400)",
            }}
          >
            Oops
          </div>
          <h1 style={{ margin: "0.5rem 0 1rem", fontSize: "1.3rem" }}>Something went wrong</h1>
          <p style={{ color: "var(--gray-500)", marginBottom: "1rem" }}>
            {this.state.error?.message || "An unexpected error occurred."}
          </p>
          <button
            type="button"
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.href = "/";
            }}
            style={{
              padding: "0.75rem 2rem",
              background: "var(--btn-green)",
              color: "white",
              border: "none",
              borderRadius: 8,
              cursor: "pointer",
              fontWeight: 600,
              fontSize: "1rem",
            }}
          >
            Back to Home
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
