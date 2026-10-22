import { cx, el, omit } from './util.js';

/**
 * Checkbox — antd-like labeled control.
 *
 * @param {object} [props]
 * @param {string} [props.label]
 * @param {boolean} [props.checked]
 * @param {boolean} [props.disabled]
 * @param {function} [props.onChange]
 */
export function Checkbox(props = {}) {
  const { label, className, checked, disabled, onChange, id } = props;
  const input = el('input', {
    ...omit(props, ['label', 'className', 'text']),
    type: 'checkbox',
    className: 'gd-checkbox__input',
    checked: !!checked,
    disabled: !!disabled,
    onChange,
    id,
  });

  return el(
    'label',
    {
      className: cx('gd-checkbox', disabled && 'gd-checkbox--disabled', className),
    },
    input,
    el('span', { className: 'gd-checkbox__box', attrs: { 'aria-hidden': 'true' } }),
    label != null ? el('span', { className: 'gd-checkbox__label', text: label }) : null
  );
}

/**
 * Switch — antd-like toggle.
 *
 * @param {object} [props]
 * @param {boolean} [props.checked]
 * @param {boolean} [props.disabled]
 * @param {string} [props.checkedChildren]
 * @param {string} [props.unCheckedChildren]
 * @param {function} [props.onChange]
 */
export function Switch(props = {}) {
  const {
    checked = false,
    disabled = false,
    className,
    checkedChildren,
    unCheckedChildren,
    onChange,
    id,
  } = props;

  return el(
    'button',
    {
      ...omit(props, [
        'checked',
        'className',
        'checkedChildren',
        'unCheckedChildren',
        'onChange',
      ]),
      type: 'button',
      id,
      role: 'switch',
      disabled: !!disabled,
      className: cx(
        'gd-switch',
        checked && 'gd-switch--checked',
        disabled && 'gd-switch--disabled',
        className
      ),
      attrs: { ...(props.attrs || {}), 'aria-checked': checked ? 'true' : 'false' },
      onClick: (event) => {
        if (disabled) return;
        onChange?.(!checked, event);
      },
    },
    el('span', { className: 'gd-switch__knob' }),
    checked && checkedChildren != null
      ? el('span', { className: 'gd-switch__text gd-switch__text--on', text: checkedChildren })
      : null,
    !checked && unCheckedChildren != null
      ? el('span', { className: 'gd-switch__text gd-switch__text--off', text: unCheckedChildren })
      : null
  );
}

/**
 * Badge — count / status / dot overlay.
 *
 * @param {object} [props]
 * @param {number|string} [props.count]
 * @param {boolean} [props.dot]
 * @param {'success'|'processing'|'default'|'error'|'warning'} [props.status]
 * @param {string} [props.text]
 * @param {number} [props.overflowCount]
 */
export function Badge(props = {}, ...children) {
  const {
    count,
    dot = false,
    status,
    text,
    overflowCount = 99,
    className,
  } = props;

  const showCount = count != null && !dot && !status;
  const display =
    typeof count === 'number' && count > overflowCount ? `${overflowCount}+` : count;

  const indicator = status
    ? el('span', {
        className: cx('gd-badge__status', `gd-badge__status--${status}`),
      })
    : dot
      ? el('span', { className: 'gd-badge__dot' })
      : showCount
        ? el('span', { className: 'gd-badge__count', text: String(display) })
        : null;

  if (!children.length && (status || text != null)) {
    return el(
      'span',
      {
        ...omit(props, ['count', 'dot', 'status', 'text', 'overflowCount', 'className']),
        className: cx('gd-badge', 'gd-badge--standalone', className),
      },
      indicator,
      text != null ? el('span', { className: 'gd-badge__text', text }) : null
    );
  }

  return el(
    'span',
    {
      ...omit(props, ['count', 'dot', 'status', 'text', 'overflowCount', 'className']),
      className: cx('gd-badge', className),
    },
    ...children,
    indicator
  );
}
