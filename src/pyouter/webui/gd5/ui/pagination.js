import { cx, el, omit } from './util.js';

/**
 * Pagination — numbered page buttons.
 * @param {object} [props]
 * @param {number} [props.current]
 * @param {number} [props.total] total pages
 * @param {function} [props.onChange]
 */
export function Pagination(props = {}) {
  const { current = 1, total = 1, onChange, className } = props;
  const pages = Array.from({ length: Math.max(1, total) }, (_, i) => i + 1);
  return el(
    'nav',
    {
      ...omit(props, ['current', 'total', 'onChange', 'className']),
      className: cx('gd-pagination', className),
      attrs: { 'aria-label': 'Pagination' },
    },
    el('button', {
      type: 'button',
      className: 'gd-pagination__btn',
      text: '‹',
      disabled: current <= 1,
      onClick: () => onChange?.(current - 1),
    }),
    ...pages.map((p) =>
      el('button', {
        type: 'button',
        className: cx('gd-pagination__btn', p === current && 'gd-pagination__btn--active'),
        text: String(p),
        onClick: () => onChange?.(p),
      })
    ),
    el('button', {
      type: 'button',
      className: 'gd-pagination__btn',
      text: '›',
      disabled: current >= total,
      onClick: () => onChange?.(current + 1),
    })
  );
}

/**
 * PageControl — dot pagination (carousel-style).
 * @param {object} [props]
 * @param {number} [props.count]
 * @param {number} [props.current] 0-based
 * @param {function} [props.onChange]
 */
export function PageControl(props = {}) {
  const { count = 3, current = 0, onChange, className } = props;
  return el(
    'div',
    {
      ...omit(props, ['count', 'current', 'onChange', 'className']),
      className: cx('gd-page-control', className),
      role: 'tablist',
    },
    ...Array.from({ length: count }, (_, i) =>
      el('button', {
        type: 'button',
        className: cx('gd-page-control__dot', i === current && 'gd-page-control__dot--active'),
        attrs: { 'aria-label': `Page ${i + 1}` },
        onClick: () => onChange?.(i),
      })
    )
  );
}
