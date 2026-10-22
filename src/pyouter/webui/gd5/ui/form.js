import { cx, el, omit } from './util.js';
import { Field } from './input.js';

/**
 * Form — vertical form shell (antd Form, simplified).
 * @param {object} [props]
 * @param {function} [props.onSubmit] (values, event)
 * @param {'vertical'|'horizontal'} [props.layout]
 */
export function Form(props = {}, ...children) {
  const { onSubmit, layout = 'vertical', className } = props;
  return el(
    'form',
    {
      ...omit(props, ['onSubmit', 'layout', 'className']),
      className: cx('gd-form', `gd-form--${layout}`, className),
      onSubmit: (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const values = Object.fromEntries(fd.entries());
        onSubmit?.(values, e);
      },
    },
    ...children
  );
}

/**
 * FormItem — labeled control with optional required / error (antd Form.Item).
 * Prefer over raw Field when inside Form.
 */
export function FormItem(props = {}, ...children) {
  const { label, name, required, error, hint, control, className } = props;
  const body = children.length ? children : control ? [control] : [];
  return el(
    'div',
    {
      ...omit(props, ['label', 'name', 'required', 'error', 'hint', 'control', 'className']),
      className: cx('gd-form-item', error && 'gd-form-item--error', className),
    },
    label != null
      ? el('label', {
          className: cx('gd-form-item__label', required && 'gd-form-item__label--required'),
          text: label,
          attrs: name ? { for: name } : undefined,
        })
      : null,
    el('div', { className: 'gd-form-item__control' }, ...body),
    error != null
      ? el('div', { className: 'gd-form-item__error', text: error })
      : hint != null
        ? el('div', { className: 'gd-form-item__hint', text: hint })
        : null
  );
}

/** Re-export Field for Form composition convenience */
export { Field };
