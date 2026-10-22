import { cx, el, omit } from './util.js';

/**
 * @param {object} [props]
 * @param {'sm'|'md'|'lg'} [props.size]
 */
export function Input(props = {}) {
  const { size = 'md', className, ...rest } = props;
  return el('input', {
    ...rest,
    className: cx('gd-input', size !== 'md' && `gd-input--${size}`, className),
  });
}

export function TextArea(props = {}, ...children) {
  const { className, value, text, ...rest } = props;
  const content = children.length ? children : value ?? text;
  return el(
    'textarea',
    {
      ...omit(rest, []),
      className: cx('gd-textarea', className),
      ...(content != null && !children.length ? { text: String(content) } : {}),
    },
    ...children
  );
}

/**
 * @param {object} [props]
 * @param {Array<{value:string,label:string}>} [props.options]
 */
export function Select(props = {}) {
  const { size = 'md', className, options = [], ...rest } = props;
  return el(
    'select',
    {
      ...omit(rest, ['options']),
      className: cx('gd-select', size !== 'md' && `gd-select--${size}`, className),
    },
    ...options.map((opt) =>
      el('option', {
        value: opt.value,
        text: opt.label,
        selected: opt.value === props.value ? true : undefined,
      })
    )
  );
}

/**
 * Labeled field wrapper.
 * @param {object} [props]
 * @param {string} [props.label]
 * @param {string} [props.hint]
 * @param {import('../engine/element.js').Element|any} [props.control]
 */
export function Field(props = {}, ...children) {
  const { label, hint, error, control, className, id } = props;
  const body = children.length ? children : control ? [control] : [];
  return el(
    'div',
    { className: cx('gd-field', error && 'gd-field--error', className), id },
    label != null ? el('label', { className: 'gd-field__label', text: label }) : null,
    ...body,
    error != null
      ? el('div', { className: 'gd-field__error', text: error })
      : hint != null
        ? el('div', { className: 'gd-field__hint', text: hint })
        : null
  );
}
