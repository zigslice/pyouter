import { cx, el, omit } from './util.js';

/**
 * Skeleton — placeholder shimmer for loading layouts.
 * @param {object} [props]
 * @param {'text'|'title'|'avatar'|'button'|'image'|'block'} [props.variant]
 * @param {number|string} [props.width]
 * @param {number|string} [props.height]
 * @param {boolean} [props.active]
 */
export function Skeleton(props = {}) {
  const { variant = 'text', width, height, active = true, className, style } = props;
  const dim = { ...(typeof style === 'object' ? style : {}) };
  if (width != null) dim.width = typeof width === 'number' ? `${width}px` : width;
  if (height != null) dim.height = typeof height === 'number' ? `${height}px` : height;

  return el('div', {
    ...omit(props, ['variant', 'width', 'height', 'active', 'className', 'style']),
    className: cx(
      'gd-skeleton',
      `gd-skeleton--${variant}`,
      active && 'gd-skeleton--active',
      className
    ),
    style: dim,
    attrs: { 'aria-hidden': 'true' },
  });
}

/** Skeleton.Paragraph — a few text lines. */
export function SkeletonParagraph(props = {}) {
  const { rows = 3, className } = props;
  const widths = ['100%', '92%', '78%', '88%', '64%'];
  return el(
    'div',
    { className: cx('gd-skeleton-paragraph', className) },
    ...Array.from({ length: rows }, (_, i) =>
      Skeleton({ variant: 'text', width: widths[i % widths.length] })
    )
  );
}
