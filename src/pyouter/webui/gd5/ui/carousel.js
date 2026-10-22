import { cx, el, omit } from './util.js';
import { PageControl } from './pagination.js';

/**
 * Carousel — horizontal slides with arrows + dots.
 * Controlled via `index` + `onChange`.
 * @param {object} [props]
 * @param {Array<any>} [props.slides] Element or string
 * @param {number} [props.index]
 * @param {function} [props.onChange]
 */
export function Carousel(props = {}) {
  const { slides = [], index = 0, onChange, className } = props;
  const count = slides.length;
  const i = ((index % count) + count) % count || 0;

  return el(
    'div',
    {
      ...omit(props, ['slides', 'index', 'onChange', 'className']),
      className: cx('gd-carousel', className),
    },
    el(
      'div',
      { className: 'gd-carousel__viewport' },
      el(
        'div',
        {
          className: 'gd-carousel__track',
          style: { transform: `translateX(-${i * 100}%)` },
        },
        ...slides.map((slide, n) =>
          el(
            'div',
            { className: 'gd-carousel__slide', key: `slide-${n}` },
            typeof slide === 'string' ? el('div', { text: slide }) : slide
          )
        )
      )
    ),
    count > 1
      ? el(
          'div',
          { className: 'gd-carousel__controls' },
          el('button', {
            type: 'button',
            className: 'gd-carousel__arrow',
            text: '‹',
            onClick: () => onChange?.((i - 1 + count) % count),
          }),
          PageControl({
            count,
            current: i,
            onChange,
          }),
          el('button', {
            type: 'button',
            className: 'gd-carousel__arrow',
            text: '›',
            onClick: () => onChange?.((i + 1) % count),
          })
        )
      : null
  );
}
