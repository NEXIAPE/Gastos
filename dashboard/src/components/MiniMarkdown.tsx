import { Fragment } from "react";

// Renderizador mínimo de markdown (viñetas, **negrita**, encabezados, párrafos).
// Suficiente para las recomendaciones; evita una dependencia extra.
function inline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith("**") && p.endsWith("**")
      ? <strong key={i}>{p.slice(2, -2)}</strong>
      : <Fragment key={i}>{p}</Fragment>);
}

export default function MiniMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const out: JSX.Element[] = [];
  let bullets: string[] = [];
  const flush = (k: number) => {
    if (bullets.length) {
      out.push(<ul key={`ul${k}`}>{bullets.map((b, i) => <li key={i}>{inline(b)}</li>)}</ul>);
      bullets = [];
    }
  };
  lines.forEach((raw, i) => {
    const line = raw.trim();
    if (/^[-*]\s+/.test(line)) { bullets.push(line.replace(/^[-*]\s+/, "")); return; }
    flush(i);
    if (!line) return;
    if (line.startsWith("### ")) out.push(<h3 key={i}>{inline(line.slice(4))}</h3>);
    else if (line.startsWith("## ")) out.push(<h2 key={i}>{inline(line.slice(3))}</h2>);
    else if (line.startsWith("# ")) out.push(<h2 key={i}>{inline(line.slice(2))}</h2>);
    else out.push(<p key={i}>{inline(line)}</p>);
  });
  flush(lines.length);
  return <div className="markdown">{out}</div>;
}
