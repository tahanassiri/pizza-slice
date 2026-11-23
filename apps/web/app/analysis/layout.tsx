export default function AnalysisLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="cockpit fixed inset-0 z-40 overflow-x-hidden overflow-y-auto overscroll-contain">
      {children}
    </div>
  );
}
