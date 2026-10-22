import { cx, el, omit } from './util.js';

/**
 * Timeline — vertical dated events.
 * @param {object} [props]
 * @param {Array<{key?:string,time?:string,title:string,description?:string,color?:string}>} [props.items]
 */
export function Timeline(props = {}) {
  const { items = [], className } = props;
  return el(
    'div',
    {
      ...omit(props, ['items', 'className']),
      className: cx('gd-timeline', className),
    },
    ...items.map((item, i) =>
      el(
        'div',
        {
          className: cx('gd-timeline__item', item.color && `gd-timeline__item--${item.color}`),
          key: item.key || `tl-${i}`,
        },
        el('div', { className: 'gd-timeline__rail' }, el('span', { className: 'gd-timeline__dot' })),
        el(
          'div',
          { className: 'gd-timeline__body' },
          item.time
            ? el('div', { className: 'gd-timeline__time', text: item.time })
            : null,
          el('div', { className: 'gd-timeline__title', text: item.title }),
          item.description
            ? el('div', { className: 'gd-timeline__desc', text: item.description })
            : null
        )
      )
    )
  );
}
