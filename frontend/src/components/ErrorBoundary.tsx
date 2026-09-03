import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Ishlab chiqarishda bu yerdan xato-monitoring xizmatiga yuborilishi mumkin
    console.error("UI xatosi:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <div
        role="alert"
        className="grid min-h-screen place-items-center bg-canvas px-4"
      >
        <div className="w-full max-w-md rounded-lg border border-line-strong bg-surface p-6 text-center shadow-overlay">
          <div className="mx-auto mb-4 grid h-11 w-11 place-items-center rounded-xl bg-danger/15 text-danger">
            <AlertTriangle className="h-5 w-5" />
          </div>
          <h1 className="text-base font-semibold text-content">
            Kutilmagan xatolik yuz berdi
          </h1>
          <p className="mt-1 text-sm text-content-muted">
            Sahifani qayta yuklab ko'ring. Muammo takrorlansa administrator bilan
            bog'laning.
          </p>
          <pre className="mt-4 max-h-32 overflow-auto rounded-md bg-surface-raised p-3 text-left text-2xs text-content-faint">
            {this.state.error.message}
          </pre>
          <Button
            className="mt-4 w-full"
            onClick={() => window.location.reload()}
          >
            <RotateCcw className="h-4 w-4" />
            Qayta yuklash
          </Button>
        </div>
      </div>
    );
  }
}
