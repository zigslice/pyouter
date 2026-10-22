import { cx, el, omit } from './util.js';

/**
 * Flex — flexbox container (antd Flex).
 * @param {object} [props]
 * @param {'horizontal'|'vertical'} [props.vertical] use vertical=true for column
 * @param {boolean} [props.wrap]
 * @param {string|number} [props.gap]
 * @param {string} [props.justify]
 * @param {string} [props.align]
 */
export function Flex(props = {}, ...children) {
  const {
    vertical = false,
    wrap = false,
    gap,
    justify,
    align,
    className,
    style,
  } = props;

  const s = { ...(typeof style === 'object' ? style : {}) };
  if (gap != null) s.gap = typeof gap === 'number' ? `${gap}px` : gap;
  if (justify) s.justifyContent = justify;
  if (align) s.alignItems = align;

  return el(
    'div',
    {
      ...omit(props, ['vertical', 'wrap', 'gap', 'justify', 'align', 'className', 'style']),
      className: cx(
        'gd-flex',
        vertical && 'gd-flex--vertical',
        wrap && 'gd-flex--wrap',
        className
      ),
      style: s,
    },
    ...children
  );
}

/**
 * Row / Col — 24-grid (antd Grid).
 * @param {object} [props]
 * @param {number|string} [props.gutter]
 */
export function Row(props = {}, ...children) {
  const { gutter = 0, className, style, align, justify } = props;
  const g = typeof gutter === 'number' ? gutter : 0;
  return el(
    'div',
    {
      ...omit(props, ['gutter', 'className', 'style', 'align', 'justify']),
      className: cx('gd-row', className),
      style: {
        ...(typeof style === 'object' ? style : {}),
        marginLeft: g ? `-${g / 2}px` : undefined,
        marginRight: g ? `-${g / 2}px` : undefined,
        alignItems: align,
        justifyContent: justify,
        '--gd-row-gutter': g ? `${g / 2}px` : '0px',
      },
    },
    ...children
  );
}

/**
 * @param {object} [props]
 * @param {number} [props.span] 1–24
 * @param {number} [props.offset]
 */
export function Col(props = {}, ...children) {
  const { span = 24, offset = 0, className, style } = props;
  const pct = (span / 24) * 100;
  const off = (offset / 24) * 100;
  return el(
    'div',
    {
      ...omit(props, ['span', 'offset', 'className', 'style']),
      className: cx('gd-col', className),
      style: {
        ...(typeof style === 'object' ? style : {}),
        flex: `0 0 ${pct}%`,
        maxWidth: `${pct}%`,
        marginLeft: offset ? `${off}%` : undefined,
        paddingLeft: 'var(--gd-row-gutter, 0px)',
        paddingRight: 'var(--gd-row-gutter, 0px)',
      },
    },
    ...children
  );
}
