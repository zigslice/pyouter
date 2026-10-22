import { JELLY_HOST_ATTR } from './jelly.js';
import { cx, el, omit } from './util.js';

/**
 * Fab — Floating Action Button.
 * @param {object} [props]
 * @param {string} [props.text]
 * @param {'primary'|'default'} [props.type]
 * @param {function} [props.onClick]
 */
export function Fab(props = {}, ...children) {
  const { text = '+', type = 'primary', className } = props;
  const kids = children.length ? children : [text];
  return el(
    'button',
    {
      ...omit(props, ['text', 'type', 'className']),
      type: 'button',
      attrs: { ...(props.attrs || {}), [JELLY_HOST_ATTR]: 'solid' },
      className: cx('gd-fab', `gd-fab--${type}`, className),
    },
    ...kids
  );
}

/** ChatLauncher — FAB variant for chat. */
export function ChatLauncher(props = {}) {
  return Fab({
    ...props,
    text: props.text ?? '💬',
    className: cx('gd-fab--chat', props.className),
    attrs: { 'aria-label': props.label || 'Open chat' },
  });
}

/** BackToTop — FAB that scrolls window to top. */
export function BackToTop(props = {}) {
  return Fab({
    ...props,
    text: props.text ?? '↑',
    type: props.type || 'default',
    className: cx('gd-fab--top', props.className),
    onClick: props.onClick || (() => window.scrollTo({ top: 0, behavior: 'smooth' })),
    attrs: { 'aria-label': 'Back to top' },
  });
}
