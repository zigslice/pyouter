import { cx, el, omit } from './util.js';

/** BentoGrid — mixed-span tile grid. */
export function BentoGrid(props = {}, ...children) {
  const { className, columns = 4 } = props;
  return el(
    'div',
    {
      ...omit(props, ['className', 'columns']),
      className: cx('gd-bento', className),
      style: { '--gd-bento-cols': String(columns) },
    },
    ...children
  );
}

/** BentoTile — one cell; `span` / `rowSpan` for size. */
export function BentoTile(props = {}, ...children) {
  const { span = 1, rowSpan = 1, className } = props;
  return el(
    'div',
    {
      ...omit(props, ['span', 'rowSpan', 'className']),
      className: cx('gd-bento__tile', className),
      style: {
        gridColumn: `span ${span}`,
        gridRow: `span ${rowSpan}`,
      },
    },
    ...children
  );
}

/** Masonry — CSS columns masonry. */
export function Masonry(props = {}, ...children) {
  const { columns = 3, className, gap = 12 } = props;
  return el(
    'div',
    {
      ...omit(props, ['columns', 'className', 'gap']),
      className: cx('gd-masonry', className),
      style: {
        columnCount: String(columns),
        columnGap: typeof gap === 'number' ? `${gap}px` : gap,
      },
    },
    ...children.map((child) => el('div', { className: 'gd-masonry__item' }, child))
  );
}

/** Marquee — endless horizontal scroll. */
export function Marquee(props = {}, ...children) {
  const { className, speed = 30, pauseOnHover = true } = props;
  return el(
    'div',
    {
      ...omit(props, ['className', 'speed', 'pauseOnHover']),
      className: cx(
        'gd-marquee',
        pauseOnHover && 'gd-marquee--pause-hover',
        className
      ),
      style: { '--gd-marquee-duration': `${speed}s` },
    },
    el('div', { className: 'gd-marquee__track' }, ...children, ...children)
  );
}

/** Sticky — position:sticky helper wrapper. */
export function Sticky(props = {}, ...children) {
  const { top = 0, className } = props;
  return el(
    'div',
    {
      ...omit(props, ['top', 'className']),
      className: cx('gd-sticky', className),
      style: { top: typeof top === 'number' ? `${top}px` : top },
    },
    ...children
  );
}

/** Fixed — position:fixed helper. */
export function Fixed(props = {}, ...children) {
  const { className, style } = props;
  return el(
    'div',
    {
      ...omit(props, ['className']),
      className: cx('gd-fixed', className),
      style,
    },
    ...children
  );
}

/** ScrollArea — scrollable region. */
export function ScrollArea(props = {}, ...children) {
  const { className, height = 200, style } = props;
  return el(
    'div',
    {
      ...omit(props, ['className', 'height']),
      className: cx('gd-scroll-area', className),
      style: {
        ...(typeof style === 'object' ? style : {}),
        maxHeight: typeof height === 'number' ? `${height}px` : height,
      },
    },
    ...children
  );
}

/** ResizeHandle — visual size grip. */
export function ResizeHandle(props = {}) {
  const { className } = props;
  return el('div', {
    ...omit(props, ['className']),
    className: cx('gd-resize-handle', className),
    attrs: { 'aria-hidden': 'true' },
  });
}

/**
 * Splitter / SplitView — two panes with a drag gutter (visual; optional onDrag).
 */
export function Splitter(props = {}, ...children) {
  const { direction = 'horizontal', className, sizes = ['50%', '50%'] } = props;
  const [a, b] = children;
  return el(
    'div',
    {
      ...omit(props, ['direction', 'className', 'sizes']),
      className: cx(
        'gd-splitter',
        direction === 'vertical' && 'gd-splitter--vertical',
        className
      ),
    },
    el('div', { className: 'gd-splitter__pane', style: { flexBasis: sizes[0] } }, a),
    el('div', {
      className: 'gd-splitter__gutter',
      attrs: { role: 'separator', 'aria-orientation': direction },
    }),
    el('div', { className: 'gd-splitter__pane', style: { flexBasis: sizes[1] } }, b)
  );
}

export const SplitView = Splitter;
