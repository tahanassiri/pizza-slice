import { Suspense } from "react";
import { AnalysisShell } from "@/features/analysis/AnalysisShell";
import { LoadingState } from "@/components/LoadingState";

export default async function MarketsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <Suspense fallback={<LoadingState />}>
      <AnalysisShell runId={id} initialTab="markets" />
    </Suspense>
  );
}
