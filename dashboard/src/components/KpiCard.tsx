export default function KpiCard({
  icon, label, value, sub, accent,
}: {
  icon: string; label: string; value: string; sub?: React.ReactNode; accent?: string;
}) {
  return (
    <div className="kpi" style={accent ? { borderTopColor: accent } : undefined}>
      <div className="kpi-top">
        <span className="kpi-icon">{icon}</span>
        <span className="kpi-label">{label}</span>
      </div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
    </div>
  );
}
