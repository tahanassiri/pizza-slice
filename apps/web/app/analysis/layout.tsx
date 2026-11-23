export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="cockpit fixed inset-0 z-40 w-full max-w-[100vw] overflow-x-clip overflow-y-auto overscroll-contain">
      {children}
    </div>
  );
}
