import { cx, el, omit } from './util.js';

/**
 * @param {object} [props]
 * @param {'default'|'primary'|'danger'} [props.color]
 * @param {string} [props.text]
 */
export function Tag(props = {}, ...children) {
  const { color = 'default', className, text } = props;
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    'span',
    {
      ...omit(props, ['color', 'className', 'text']),
      className: cx('gd-tag', color !== 'default' && `gd-tag--${color}`, className),
    },
    ...kids
  );
}

/**
 * @param {object} [props]
 * @param {'info'|'success'|'warning'|'error'} [props.type]
 * @param {string} [props.message]
 */
export function Alert(props = {}, ...children) {
  const { type = 'info', className, message } = props;
  const kids = children.length ? children : message != null ? [message] : [];
  return el(
    'div',
    {
      ...omit(props, ['type', 'className', 'message']),
      className: cx('gd-alert', `gd-alert--${type}`, className),
      role: 'alert',
    },
    ...kids
  );
}

export function Spin(props = {}) {
  const { size = 'md', className } = props;
  return el('div', {
    ...omit(props, ['size', 'className']),
    className: cx('gd-spin', size === 'lg' && 'gd-spin--lg', className),
    attrs: { 'aria-label': 'loading' },
  });
}

/**
 * @param {object} [props]
 * @param {string} [props.description]
 * @param {any} [props.extra]
 */
export function Empty(props = {}, ...children) {
  const { description = 'No data', className, extra, title = 'Empty' } = props;
  return el(
    'div',
    {
      ...omit(props, ['description', 'className', 'extra', 'title']),
      className: cx('gd-empty', className),
    },
    el('p', { className: 'gd-empty__title', text: title }),
    el('p', { className: 'gd-empty__desc', text: description }),
    extra || null,
    ...children
  );
}
