import { JELLY_HOST_ATTR } from './jelly.js';
import { cx, el, omit } from './util.js';

/**
 * Chip — interactive compact label (closable / selectable).
 * Distinct from Badge (count) and Tag (static).
 * @param {object} [props]
 * @param {string} [props.text]
 * @param {boolean} [props.closable]
 * @param {boolean} [props.selected]
 * @param {function} [props.onClose]
 * @param {function} [props.onClick]
 */
export function Chip(props = {}, ...children) {
  const { text, closable, selected, className, onClose, onClick, color } = props;
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    'span',
    {
      ...omit(props, ['text', 'closable', 'selected', 'className', 'onClose', 'color']),
      attrs: { ...(props.attrs || {}), [JELLY_HOST_ATTR]: 'solid' },
      className: cx(
        'gd-chip',
        selected && 'gd-chip--selected',
        color && `gd-chip--${color}`,
        className
      ),
      onClick,
    },
    ...kids,
    closable
      ? el('button', {
          type: 'button',
          className: 'gd-chip__close',
          text: '×',
          onClick: (e) => {
            e.stopPropagation();
            onClose?.(e);
          },
        })
      : null
  );
}

/** Pill — fully rounded static label. */
export function Pill(props = {}, ...children) {
  const { text, className, color = 'default' } = props;
  const kids = children.length ? children : text != null ? [text] : [];
  return el(
    'span',
    {
      ...omit(props, ['text', 'className', 'color']),
      className: cx('gd-pill', `gd-pill--${color}`, className),
    },
    ...kids
  );
}
