import { cx, el, omit } from './util.js';

/**
 * Avatar — image / initials circle with optional StatusDot.
 * @param {object} [props]
 * @param {string} [props.src]
 * @param {string} [props.alt]
 * @param {string} [props.name] used for initials fallback
 * @param {'sm'|'md'|'lg'|'xl'} [props.size]
 * @param {'online'|'away'|'busy'|'offline'|'processing'} [props.status]
 */
export function Avatar(props = {}) {
  const { src, alt, name, size = 'md', status, className, text } = props;
  const initials =
    text ||
    (name
      ? name
          .split(/\s+/)
          .slice(0, 2)
          .map((p) => p[0])
          .join('')
          .toUpperCase()
      : '?');

  return el(
    'span',
    {
      ...omit(props, ['src', 'alt', 'name', 'size', 'status', 'className', 'text']),
      className: cx('gd-avatar', `gd-avatar--${size}`, className),
    },
    src
      ? el('img', { className: 'gd-avatar__img', src, alt: alt || name || '' })
      : el('span', { className: 'gd-avatar__fallback', text: initials }),
    status ? StatusDot({ status, className: 'gd-avatar__status' }) : null
  );
}

/**
 * StatusDot — presence indicator.
 * @param {object} [props]
 * @param {'online'|'away'|'busy'|'offline'|'processing'|'success'|'error'|'warning'} [props.status]
 */
export function StatusDot(props = {}) {
  const { status = 'offline', className, title } = props;
  return el('span', {
    ...omit(props, ['status', 'className']),
    className: cx('gd-status-dot', `gd-status-dot--${status}`, className),
    title: title || status,
    attrs: { 'aria-label': title || status },
  });
}

/**
 * AvatarGroup — overlapping faces with +N overflow.
 * @param {object} [props]
 * @param {Array<object>} [props.items] Avatar props
 * @param {number} [props.max]
 */
export function AvatarGroup(props = {}, ...children) {
  const { items = [], max = 5, className, size = 'md' } = props;
  const list = children.length
    ? children
    : items.map((item) => Avatar({ size, ...item }));
  const shown = list.slice(0, max);
  const overflow = list.length - shown.length;

  return el(
    'div',
    {
      ...omit(props, ['items', 'max', 'className', 'size']),
      className: cx('gd-avatar-group', className),
    },
    ...shown,
    overflow > 0
      ? el('span', {
          className: cx('gd-avatar', `gd-avatar--${size}`, 'gd-avatar--overflow'),
          text: `+${overflow}`,
        })
      : null
  );
}
