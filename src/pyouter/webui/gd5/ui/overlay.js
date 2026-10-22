import { cx, el, omit } from './util.js';

/** Scrim — translucent backdrop layer. */
export function Scrim(props = {}) {
  const { className, visible = true, onClick } = props;
  return el('div', {
    ...omit(props, ['className', 'visible']),
    className: cx('gd-scrim', visible && 'gd-scrim--visible', className),
    onClick,
  });
}

/**
 * Tooltip — anchored hint (CSS hover / focus).
 * Wrap a trigger; show `title` text.
 */
export function Tooltip(props = {}, ...children) {
  const { title, placement = 'top', className } = props;
  return el(
    'span',
    {
      ...omit(props, ['title', 'placement', 'className']),
      className: cx('gd-tooltip', `gd-tooltip--${placement}`, className),
    },
    ...children,
    el('span', { className: 'gd-tooltip__bubble', role: 'tooltip', text: title })
  );
}

/**
 * Popover — richer anchored panel (visibility controlled).
 * @param {object} [props]
 * @param {boolean} [props.open]
 * @param {any} [props.content]
 * @param {string} [props.title]
 */
export function Popover(props = {}, ...children) {
  const { open = false, content, title, className, placement = 'bottom' } = props;
  return el(
    'span',
    {
      ...omit(props, ['open', 'content', 'title', 'className', 'placement']),
      className: cx('gd-popover', `gd-popover--${placement}`, open && 'gd-popover--open', className),
    },
    ...children,
    open
      ? el(
          'div',
          { className: 'gd-popover__panel', role: 'dialog' },
          title != null ? el('div', { className: 'gd-popover__title', text: title }) : null,
          el('div', { className: 'gd-popover__body' }, content)
        )
      : null
  );
}

/**
 * DropdownMenu — list of actions under a trigger.
 * @param {object} [props]
 * @param {boolean} [props.open]
 * @param {Array<{key?:string,label:string,danger?:boolean,disabled?:boolean,onClick?:function,divider?:boolean}>} [props.items]
 */
export function DropdownMenu(props = {}, ...children) {
  const { open = false, items = [], className, onOpenChange } = props;
  return el(
    'span',
    {
      ...omit(props, ['open', 'items', 'className', 'onOpenChange']),
      className: cx('gd-dropdown', open && 'gd-dropdown--open', className),
    },
    ...children,
    open
      ? el(
          'div',
          { className: 'gd-dropdown__menu', role: 'menu' },
          ...items.map((it, i) =>
            it.divider
              ? el('div', { className: 'gd-dropdown__divider', key: `d-${i}` })
              : el('button', {
                  type: 'button',
                  role: 'menuitem',
                  className: cx(
                    'gd-dropdown__item',
                    it.danger && 'gd-dropdown__item--danger'
                  ),
                  text: it.label,
                  disabled: !!it.disabled,
                  onClick: (e) => {
                    it.onClick?.(e);
                    onOpenChange?.(false);
                  },
                })
          )
        )
      : null
  );
}

/**
 * HoverCard — rich preview on hover (CSS :hover).
 */
export function HoverCard(props = {}, ...children) {
  const { content, className, title } = props;
  return el(
    'span',
    {
      ...omit(props, ['content', 'className', 'title']),
      className: cx('gd-hover-card', className),
    },
    ...children,
    el(
      'div',
      { className: 'gd-hover-card__panel', role: 'tooltip' },
      title != null ? el('div', { className: 'gd-hover-card__title', text: title }) : null,
      el('div', { className: 'gd-hover-card__body' }, content)
    )
  );
}

/**
 * ContextMenu — right-click menu host.
 * Pass open + position {x,y} + items.
 */
export function ContextMenu(props = {}) {
  const { open = false, x = 0, y = 0, items = [], onClose, className } = props;
  if (!open) return el('div', { className: 'gd-context-menu gd-context-menu--hidden' });
  return el(
    'div',
    {
      ...omit(props, ['open', 'x', 'y', 'items', 'onClose', 'className']),
      className: cx('gd-context-menu', className),
      style: { left: `${x}px`, top: `${y}px` },
      role: 'menu',
    },
    ...items.map((it, i) =>
      it.divider
        ? el('div', { className: 'gd-dropdown__divider', key: `cd-${i}` })
        : el('button', {
            type: 'button',
            role: 'menuitem',
            className: cx('gd-dropdown__item', it.danger && 'gd-dropdown__item--danger'),
            text: it.label,
            disabled: !!it.disabled,
            onClick: (e) => {
              it.onClick?.(e);
              onClose?.();
            },
          })
    )
  );
}

/**
 * OverflowMenu — three-dots / kebab trigger + menu.
 * @param {'horizontal'|'vertical'|'hamburger'} [props.variant]
 */
export function OverflowMenu(props = {}) {
  const {
    variant = 'horizontal',
    open = false,
    items = [],
    onOpenChange,
    className,
  } = props;
  const glyph = variant === 'vertical' ? '⋮' : variant === 'hamburger' ? '☰' : '⋯';
  return DropdownMenu(
    { open, items, onOpenChange, className: cx('gd-overflow-menu', className) },
    el('button', {
      type: 'button',
      className: 'gd-overflow-menu__trigger',
      text: glyph,
      attrs: { 'aria-label': 'More' },
      onClick: () => onOpenChange?.(!open),
    })
  );
}
