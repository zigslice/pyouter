import { cx, el, omit } from './util.js';

/**
 * Rate — star rating (antd Rate).
 * @param {object} [props]
 * @param {number} [props.value]
 * @param {number} [props.count]
 * @param {boolean} [props.allowClear]
 * @param {boolean} [props.disabled]
 * @param {function} [props.onChange]
 */
export function Rate(props = {}) {
  const {
    value = 0,
    count = 5,
    allowClear = true,
    disabled = false,
    onChange,
    className,
    character = '★',
  } = props;

  return el(
    'div',
    {
      ...omit(props, ['value', 'count', 'allowClear', 'disabled', 'onChange', 'className', 'character']),
      className: cx('gd-rate', disabled && 'gd-rate--disabled', className),
      role: 'radiogroup',
      attrs: { 'aria-label': 'Rating' },
    },
    ...Array.from({ length: count }, (_, i) => {
      const n = i + 1;
      const active = n <= value;
      return el('button', {
        type: 'button',
        className: cx('gd-rate__star', active && 'gd-rate__star--active'),
        text: character,
        disabled: !!disabled,
        attrs: { 'aria-label': `${n} star${n > 1 ? 's' : ''}` },
        onClick: () => {
          if (disabled) return;
          if (allowClear && value === n) onChange?.(0);
          else onChange?.(n);
        },
      });
    })
  );
}
