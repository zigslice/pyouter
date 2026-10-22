import { cx, el, omit } from './util.js';

/**
 * Steps — checkout / wizard stage indicators.
 * @param {object} [props]
 * @param {Array<{title:string,description?:string}>} [props.items]
 * @param {number} [props.current] 0-based
 * @param {'horizontal'|'vertical'} [props.direction]
 */
export function Steps(props = {}) {
  const { items = [], current = 0, direction = 'horizontal', className } = props;
  return el(
    'div',
    {
      ...omit(props, ['items', 'current', 'direction', 'className']),
      className: cx(
        'gd-steps',
        direction === 'vertical' && 'gd-steps--vertical',
        className
      ),
    },
    ...items.map((item, i) => {
      const status = i < current ? 'finish' : i === current ? 'process' : 'wait';
      return el(
        'div',
        { className: cx('gd-steps__item', `gd-steps__item--${status}`) },
        el('div', { className: 'gd-steps__indicator', text: String(i + 1) }),
        el(
          'div',
          { className: 'gd-steps__content' },
          el('div', { className: 'gd-steps__title', text: item.title }),
          item.description
            ? el('div', { className: 'gd-steps__desc', text: item.description })
            : null
        )
      );
    })
  );
}

/**
 * QuantityStepper — increment / decrement numeric value.
 * @param {object} [props]
 * @param {number} [props.value]
 * @param {number} [props.min]
 * @param {number} [props.max]
 * @param {number} [props.step]
 * @param {function} [props.onChange]
 */
export function QuantityStepper(props = {}) {
  const { value = 0, min = 0, max = Infinity, step = 1, onChange, className, disabled } =
    props;
  const dec = () => {
    const next = Math.max(min, value - step);
    if (next !== value) onChange?.(next);
  };
  const inc = () => {
    const next = Math.min(max, value + step);
    if (next !== value) onChange?.(next);
  };
  return el(
    'div',
    {
      ...omit(props, ['value', 'min', 'max', 'step', 'onChange', 'className']),
      className: cx('gd-qty-stepper', className),
    },
    el('button', {
      type: 'button',
      className: 'gd-qty-stepper__btn',
      text: '−',
      disabled: disabled || value <= min,
      onClick: dec,
    }),
    el('span', { className: 'gd-qty-stepper__value', text: String(value) }),
    el('button', {
      type: 'button',
      className: 'gd-qty-stepper__btn',
      text: '+',
      disabled: disabled || value >= max,
      onClick: inc,
    })
  );
}
