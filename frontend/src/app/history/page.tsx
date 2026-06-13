import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Phase 3 will populate this page with real prediction history from MongoDB.
// For now we render an informative empty state.

export default function HistoryPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <h1 className="mb-2 text-2xl font-bold">Prediction History</h1>
      <p className="mb-8 text-sm text-muted-foreground">
        Accuracy of past AI predictions vs actual race results.
      </p>

      {/* Empty state */}
      <Card className="border-dashed border-border/50">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <span>🏁</span> No predictions yet
          </CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <p className="text-sm text-muted-foreground">
            Predictions are stored after you click{" "}
            <span className="font-medium text-foreground">
              &ldquo;Predict the Winner&rdquo;
            </span>{" "}
            on any upcoming race. Once the race has been run you can compare the
            prediction against the actual result here.
          </p>
          <div className="flex items-center gap-2">
            <Badge variant="secondary">Phase 3 — AI Agents</Badge>
            <span className="text-xs text-muted-foreground">
              required for live predictions
            </span>
          </div>

          {/* Future table placeholder */}
          <div className="mt-2 rounded-lg border border-border/50 bg-muted/10 p-4">
            <p className="text-xs font-mono text-muted-foreground text-center">
              Race · Predicted Winner · Actual Winner · Correct? · Confidence · Date
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
