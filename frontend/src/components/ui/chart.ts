// ทางรอด — lightweight SVG path math shared by the data-viz components.
export function points(data: number[], w: number, h: number, pad: number): [number, number][] {
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const ix = w / (data.length - 1 || 1);
  return data.map((v, i) => [
    +(i * ix).toFixed(2),
    +(pad + (h - pad * 2) * (1 - (v - min) / span)).toFixed(2),
  ]);
}

export function smoothPath(pts: [number, number][]): string {
  if (pts.length < 2) return "";
  let d = `M ${pts[0][0]} ${pts[0][1]}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const [x0, y0] = pts[i];
    const [x1, y1] = pts[i + 1];
    const cx = (x0 + x1) / 2;
    d += ` C ${cx} ${y0}, ${cx} ${y1}, ${x1} ${y1}`;
  }
  return d;
}

export function linePath(pts: [number, number][]): string {
  return "M " + pts.map((p) => p.join(" ")).join(" L ");
}

let _id = 0;
export function uid(prefix = "g"): string {
  _id += 1;
  return `${prefix}${_id}`;
}
