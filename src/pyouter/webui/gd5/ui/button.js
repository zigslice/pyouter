import { JELLY_HOST_ATTR } from './jelly.js';
import { cx, el, omit } from './util.js';

/**
 * Inline loading indicator for buttons.
 * @param {'dots'|'spin'} [kind]
 */
export function ButtonIndicator(kind = 'dots') {
  if (kind === 'spin') {
    return el('span', {
      className: 'gd-btn__indicator gd-btn__indicator--spin',
      attrs: { 'aria-hidden': 'true' },
    });
  }
  return el(
    'span',
    {
      className: 'gd-btn__indicator gd-btn__indicator--dots',
      attrs: { 'aria-hidden': 'true' },
    },
    el('i'),
    el('i'),
    el('i')
  );
}

/**
 * Button — antd-like primitive.
 *
 * @param {object} [props]
 * @param {'primary'|'default'|'ghost'|'danger'|'text'} [props.type]
 * @param {'sm'|'md'|'lg'} [props.size]
 * @param {boolean} [props.block]
 * @param {boolean} [props.disabled]
 * @param {boolean} [props.loading]  shows indicator + locks click
 * @param {'dots'|'spin'} [props.indicator]
 * @param {string} [props.text]
 * @param {string} [props.loadingText]  label while loading (default: keep text)
 * @param {string} [props.className]
 * @param {function} [props.onClick]
 * @param {...any} children
 */
export function Button(props = {}, ...children) {
  const {
    type = 'default',
    size = 'md',
    block = false,
    className,
    text,
    loadingText,
    disabled,
    loading = false,
    indicator = 'dots',
  } = props;

  const busy = !!loading;
  const locked = busy || !!disabled;
  const kids = children.length ? children : [];
  const label =
    kids.length === 0
      ? busy && loadingText != null
        ? String(loadingText)
        : text != null
          ? String(text)
          : null
      : null;

  return el(
    'button',
    {
      ...omit(props, [
        'type',
        'size',
        'block',
        'className',
        'text',
        'loadingText',
        'htmlType',
        'loading',
        'indicator',
      ]),
      type: props.htmlType || 'button',
      disabled: locked,
      attrs: buttonAttrs(type, busy, props.attrs),
      className: cx(
        'gd-btn',
        `gd-btn--${type}`,
        `gd-btn--${size}`,
        block && 'gd-btn--block',
        busy && 'gd-btn--loading',
        className
      ),
      onClick: (e) => {
        if (busy) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
        props.onClick?.(e);
      },
    },
    busy ? ButtonIndicator(indicator === 'spin' ? 'spin' : 'dots') : null,
    label != null ? el('span', { className: 'gd-btn__label', text: label }) : null,
    ...kids
  );
}

/** Solid primary and default buttons can carry the global jelly membrane. */
function buttonAttrs(type, busy, extra) {
  const attrs = {
    ...(extra || {}),
    'aria-busy': busy ? 'true' : 'false',
  };
  if (type === 'primary' || type === 'default' || type === 'ghost' || type === 'danger') {
    attrs[JELLY_HOST_ATTR] = 'solid';
  } else delete attrs[JELLY_HOST_ATTR];
  return attrs;
}

/**
 * Run an async click handler once; ignore re-entry while pending.
 * @param {() => (void|Promise<void>)} fn
 * @returns {() => Promise<void>}
 */
export function onceAsync(fn) {
  let pending = false;
  return async () => {
    if (pending) return;
    pending = true;
    try {
      await fn?.();
    } finally {
      pending = false;
    }
  };
}
