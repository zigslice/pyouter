import { cx, el, omit } from './util.js';

/**
 * PieChart / DonutChart — simple SVG sector chart.
 * @param {object} [props]
 * @param {Array<{value:number,color?:string,label?:string}>} [props.data]
 * @param {number} [props.size]
 * @param {boolean} [props.donut]
 * @param {number} [props.innerRatio] 0–1 hole size when donut
 */
export function PieChart(props = {}) {
  const {
    data = [],
    size = 160,
    donut = false,
    innerRatio = 0.55,
    className,
  } = props;
  const total = data.reduce((s, d) => s + (Number(d.value) || 0), 0) || 1;
  const cx0 = size / 2;
  const cy0 = size / 2;
  const r = size / 2 - 2;
  const ir = donut ? r * innerRatio : 0;
  const colors = [
    'var(--gd-primary)',
    '#f0a35a',
    '#2f8f5b',
    '#2f6fed',
    '#d14343',
    '#8a8178',
  ];

  let angle = -Math.PI / 2;
  const paths = [];
  data.forEach((d, i) => {
    const slice = ((Number(d.value) || 0) / total) * Math.PI * 2;
    const a0 = angle;
    const a1 = angle + slice;
    angle = a1;
    const x0 = cx0 + r * Math.cos(a0);
    const y0 = cy0 + r * Math.sin(a0);
    const x1 = cx0 + r * Math.cos(a1);
    const y1 = cy0 + r * Math.sin(a1);
    const large = slice > Math.PI ? 1 : 0;
    let dPath;
    if (donut) {
      const ix0 = cx0 + ir * Math.cos(a1);
      const iy0 = cy0 + ir * Math.sin(a1);
      const ix1 = cx0 + ir * Math.cos(a0);
      const iy1 = cy0 + ir * Math.sin(a0);
      dPath = `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} L ${ix0} ${iy0} A ${ir} ${ir} 0 ${large} 0 ${ix1} ${iy1} Z`;
    } else {
      dPath = `M ${cx0} ${cy0} L ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1} Z`;
    }
    paths.push({ d: dPath, color: d.color || colors[i % colors.length], label: d.label });
  });

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
  svg.setAttribute('width', String(size));
  svg.setAttribute('height', String(size));
  svg.setAttribute('class', 'gd-chart__svg');
  for (const p of paths) {
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', p.d);
    path.setAttribute('fill', p.color);
    if (p.label) path.setAttribute('aria-label', p.label);
    svg.appendChild(path);
  }

  return el(
    'div',
    {
      ...omit(props, ['data', 'size', 'donut', 'innerRatio', 'className']),
      className: cx('gd-chart', donut && 'gd-chart--donut', className),
      role: 'img',
    },
    { e: svg, dom: () => svg }
  );
}

export function DonutChart(props = {}) {
  return PieChart({ ...props, donut: true });
}
