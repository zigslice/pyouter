import { cx, el, omit } from './util.js';

/**
 * Banner — full-bleed in-page notice (typically top of view).
 * @param {object} [props]
 * @param {'info'|'success'|'warning'|'error'} [props.type]
 * @param {string} [props.message]
 * @param {boolean} [props.closable]
 * @param {function} [props.onClose]
 */
export function Banner(props = {}, ...children) {
  const { type = 'info', message, closable, onClose, className } = props;
  const kids = children.length ? children : message != null ? [message] : [];
  return el(
    'div',
    {
      ...omit(props, ['type', 'message', 'closable', 'onClose', 'className']),
      className: cx('gd-banner', `gd-banner--${type}`, className),
      role: 'status',
    },
    el('div', { className: 'gd-banner__body' }, ...kids),
    closable
      ? el('button', {
          type: 'button',
          className: 'gd-banner__close',
          text: '×',
          onClick: onClose,
        })
      : null
  );
}

/**
 * Callout — bordered aside notice in the content flow.
 */
export function Callout(props = {}, ...children) {
  const { type = 'info', title, message, className } = props;
  const kids = children.length ? children : message != null ? [message] : [];
  return el(
    'aside',
    {
      ...omit(props, ['type', 'title', 'message', 'className']),
      className: cx('gd-callout', `gd-callout--${type}`, className),
    },
    title != null ? el('div', { className: 'gd-callout__title', text: title }) : null,
    el('div', { className: 'gd-callout__body' }, ...kids)
  );
}
