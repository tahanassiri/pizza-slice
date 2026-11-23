import { LoadingState } from "@/components/LoadingState";

/** Visible wait state during Next.js route transitions (e.g. home → analysis). */
export default function RootLoading() {
  return (
    <div className="mx-auto max-w-lg py-10">
      <LoadingState />
    </div>
  );
}
