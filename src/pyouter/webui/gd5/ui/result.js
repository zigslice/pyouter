import { cx, el, omit } from './util.js';
import { Button } from './button.js';

/**
 * Result — success / error / info page block (antd Result).
 * @param {object} [props]
 * @param {'success'|'error'|'info'|'warning'|'404'|'403'|'500'} [props.status]
 * @param {string} [props.title]
 * @param {string} [props.subTitle]
 * @param {any} [props.extra]
 */
export function Result(props = {}, ...children) {
  const {
    status = 'info',
    title,
    subTitle,
    extra,
    className,
    icon,
  } = props;

  const defaultIcon = {
    success: '✓',
    error: '✕',
    info: 'ℹ',
    warning: '!',
    '404': '404',
    '403': '403',
    '500': '500',
  }[status] || 'ℹ';

  return el(
    'div',
    {
      ...omit(props, ['status', 'title', 'subTitle', 'extra', 'className', 'icon']),
      className: cx('gd-result', `gd-result--${status}`, className),
    },
    el('div', {
      className: 'gd-result__icon',
      text: icon != null ? String(icon) : defaultIcon,
    }),
    title != null ? el('div', { className: 'gd-result__title', text: title }) : null,
    subTitle != null ? el('div', { className: 'gd-result__subtitle', text: subTitle }) : null,
    children.length ? el('div', { className: 'gd-result__body' }, ...children) : null,
    extra != null ? el('div', { className: 'gd-result__extra' }, extra) : null
  );
}

/**
 * Popconfirm — confirm popover on an action (antd Popconfirm).
 * Controlled via `open`.
 */
export function Popconfirm(props = {}, ...children) {
  const {
    open = false,
    title = 'Are you sure?',
    okText = 'OK',
    cancelText = 'Cancel',
    onConfirm,
    onCancel,
    onOpenChange,
    className,
  } = props;

  return el(
    'span',
    {
      ...omit(props, [
        'open',
        'title',
        'okText',
        'cancelText',
        'onConfirm',
        'onCancel',
        'onOpenChange',
        'className',
      ]),
      className: cx('gd-popconfirm', open && 'gd-popconfirm--open', className),
    },
    ...children,
    open
      ? el(
          'div',
          { className: 'gd-popconfirm__panel', role: 'dialog' },
          el('div', { className: 'gd-popconfirm__title', text: title }),
          el(
            'div',
            { className: 'gd-popconfirm__actions' },
            Button({
              type: 'default',
              size: 'sm',
              text: cancelText,
              onClick: () => {
                onCancel?.();
                onOpenChange?.(false);
              },
            }),
            Button({
              type: 'primary',
              size: 'sm',
              text: okText,
              onClick: () => {
                onConfirm?.();
                onOpenChange?.(false);
              },
            })
          )
        )
      : null
  );
}
