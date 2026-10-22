import { cx, el, omit } from './util.js';

/**
 * @param {object} [props]
 * @param {string} [props.title]
 * @param {any} [props.extra]
 * @param {any} [props.footer]
 */
export function Card(props = {}, ...children) {
  const { title, extra, footer, className, id } = props;
  const hasHead = title != null || extra != null;

  return el(
    'div',
    {
      ...omit(props, ['title', 'extra', 'footer', 'className']),
      id,
      className: cx('gd-card', className),
    },
    hasHead
      ? el(
          'div',
          { className: 'gd-card__head' },
          title != null ? el('h3', { className: 'gd-card__title', text: title }) : null,
          extra || null
        )
      : null,
    el('div', { className: 'gd-card__body' }, ...children),
    footer != null ? el('div', { className: 'gd-card__foot' }, footer) : null
  );
}
