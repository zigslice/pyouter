import { cx, el, omit } from './util.js';

/**
 * Radio — single choice in a named group.
 * @param {object} [props]
 * @param {string} [props.label]
 * @param {string} [props.name]
 * @param {string|number} [props.value]
 * @param {boolean} [props.checked]
 */
export function Radio(props = {}) {
  const { label, className, checked, disabled, name, value, onChange, id } = props;
  return el(
    'label',
    {
      className: cx('gd-radio', disabled && 'gd-radio--disabled', className),
    },
    el('input', {
      ...omit(props, ['label', 'className', 'text']),
      type: 'radio',
      className: 'gd-radio__input',
      name,
      value,
      checked: !!checked,
      disabled: !!disabled,
      onChange,
      id,
    }),
    el('span', { className: 'gd-radio__dot', attrs: { 'aria-hidden': 'true' } }),
    label != null ? el('span', { className: 'gd-radio__label', text: label }) : null
  );
}

/**
 * RadioGroup — convenience wrapper.
 * @param {object} [props]
 * @param {Array<{value:string,label:string,disabled?:boolean}>} [props.options]
 * @param {string} [props.value]
 * @param {string} [props.name]
 * @param {function} [props.onChange]
 */
export function RadioGroup(props = {}) {
  const { options = [], value, name = 'gd-radio', className, onChange, direction = 'vertical' } =
    props;
  return el(
    'div',
    {
      className: cx(
        'gd-radio-group',
        direction === 'horizontal' && 'gd-radio-group--horizontal',
        className
      ),
      role: 'radiogroup',
    },
    ...options.map((opt) =>
      Radio({
        name,
        value: opt.value,
        label: opt.label,
        disabled: opt.disabled,
        checked: value === opt.value,
        onChange: (e) => onChange?.(e.target.value, e),
      })
    )
  );
}
