import { LoadingState } from "@/components/LoadingState";
import { fa } from "@/lib/i18n/fa";

/** Visible wait state during Next.js route transitions (e.g. home → analysis). */
export default function RootLoading() {
  return (
    <div className="mx-auto max-w-lg py-10">
      <LoadingState
        label={fa.loading.openingPage}
        stages={[
          fa.loading.stages.prepare,
          fa.loading.stages.fetch,
          fa.loading.stages.analyze,
          fa.loading.stages.almost,
        ]}
      />
    </div>
  );
}
