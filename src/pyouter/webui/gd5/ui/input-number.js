import { cx, el, omit } from './util.js';

/**
 * InputNumber — numeric stepper field (antd InputNumber).
 * @param {object} [props]
 * @param {number} [props.value]
 * @param {number} [props.min]
 * @param {number} [props.max]
 * @param {number} [props.step]
 * @param {function} [props.onChange]
 */
export function InputNumber(props = {}) {
  const {
    value = 0,
    min = -Infinity,
    max = Infinity,
    step = 1,
    onChange,
    className,
    disabled,
    placeholder,
  } = props;

  const clamp = (n) => Math.min(max, Math.max(min, n));

  return el(
    'div',
    {
      ...omit(props, ['value', 'min', 'max', 'step', 'onChange', 'className', 'placeholder']),
      className: cx('gd-input-number', disabled && 'gd-input-number--disabled', className),
    },
    el('button', {
      type: 'button',
      className: 'gd-input-number__btn',
      text: '−',
      disabled: disabled || value <= min,
      onClick: () => onChange?.(clamp(Number(value) - step)),
    }),
    el('input', {
      type: 'number',
      className: 'gd-input-number__input',
      value,
      min: Number.isFinite(min) ? min : undefined,
      max: Number.isFinite(max) ? max : undefined,
      step,
      disabled: !!disabled,
      placeholder,
      onInput: (e) => {
        const n = Number(e.target.value);
        if (!Number.isNaN(n)) onChange?.(clamp(n));
      },
    }),
    el('button', {
      type: 'button',
      className: 'gd-input-number__btn',
      text: '+',
      disabled: disabled || value >= max,
      onClick: () => onChange?.(clamp(Number(value) + step)),
    })
  );
}
