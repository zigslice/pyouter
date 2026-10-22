import { cx, el, omit } from './util.js';

/**
 * Breadcrumbs — hierarchy trail.
 * @param {object} [props]
 * @param {Array<{label:string,href?:string,onClick?:function}>} [props.items]
 * @param {string} [props.separator]
 */
export function Breadcrumbs(props = {}) {
  const { items = [], separator = '/', className } = props;
  const nodes = [];
  items.forEach((item, i) => {
    const last = i === items.length - 1;
    if (i > 0) {
      nodes.push(
        el('span', {
          className: 'gd-breadcrumb__sep',
          text: separator,
          attrs: { 'aria-hidden': 'true' },
        })
      );
    }
    if (last || (!item.href && !item.onClick)) {
      nodes.push(
        el('span', {
          className: cx('gd-breadcrumb__item', last && 'gd-breadcrumb__item--current'),
          text: item.label,
          attrs: last ? { 'aria-current': 'page' } : undefined,
        })
      );
    } else {
      nodes.push(
        el('a', {
          className: 'gd-breadcrumb__item gd-breadcrumb__link',
          text: item.label,
          href: item.href || '#',
          onClick: (e) => {
            if (item.onClick) {
              e.preventDefault();
              item.onClick(e);
            }
          },
        })
      );
    }
  });

  return el(
    'nav',
    {
      ...omit(props, ['items', 'separator', 'className']),
      className: cx('gd-breadcrumb', className),
      attrs: { 'aria-label': 'Breadcrumb' },
    },
    ...nodes
  );
}
