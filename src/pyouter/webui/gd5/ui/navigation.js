import { cx, el, omit } from './util.js';
import { Button } from './button.js';

/**
 * Navbar — row of page links (inside a SiteHeader).
 * @param {object} [props]
 * @param {Array<{key?:string,label:string,href?:string,active?:boolean,onClick?:function}>} [props.items]
 */
export function Navbar(props = {}, ...children) {
  const { items = [], className } = props;
  return el(
    'nav',
    {
      ...omit(props, ['items', 'className']),
      className: cx('gd-navbar', className),
    },
    ...(children.length
      ? children
      : items.map((it) =>
          el('a', {
            className: cx('gd-navbar__link', it.active && 'gd-navbar__link--active'),
            text: it.label,
            href: it.href || '#',
            onClick: it.onClick
              ? (e) => {
                  e.preventDefault();
                  it.onClick(e);
                }
              : undefined,
          })
        ))
  );
}

/**
 * SiteHeader — top strip containing brand + Navbar + extra.
 */
export function SiteHeader(props = {}, ...children) {
  const { brand, extra, className, sticky = false } = props;
  return el(
    'header',
    {
      ...omit(props, ['brand', 'extra', 'className', 'sticky']),
      className: cx('gd-site-header', sticky && 'gd-sticky', className),
    },
    brand != null ? el('div', { className: 'gd-site-header__brand', text: String(brand) }) : null,
    ...children,
    extra || null
  );
}

/**
 * BottomNav — mobile tab bar.
 * @param {object} [props]
 * @param {Array<{key:string,label:string,icon?:string,active?:boolean,onClick?:function}>} [props.items]
 */
export function BottomNav(props = {}) {
  const { items = [], className } = props;
  return el(
    'nav',
    {
      ...omit(props, ['items', 'className']),
      className: cx('gd-bottom-nav', className),
      attrs: { 'aria-label': 'Bottom navigation' },
    },
    ...items.map((it) =>
      el('button', {
        type: 'button',
        className: cx('gd-bottom-nav__item', it.active && 'gd-bottom-nav__item--active'),
        onClick: it.onClick,
      },
        it.icon ? el('span', { className: 'gd-bottom-nav__icon', text: it.icon }) : null,
        el('span', { className: 'gd-bottom-nav__label', text: it.label })
      )
    )
  );
}

/**
 * Sidebar — left navigation column.
 */
export function Sidebar(props = {}, ...children) {
  const { items = [], title, className, width = 220 } = props;
  return el(
    'aside',
    {
      ...omit(props, ['items', 'title', 'className', 'width']),
      className: cx('gd-sidebar', className),
      style: { width: typeof width === 'number' ? `${width}px` : width },
    },
    title != null ? el('div', { className: 'gd-sidebar__title', text: title }) : null,
    el(
      'div',
      { className: 'gd-sidebar__nav' },
      ...(children.length
        ? children
        : items.map((it) =>
            el('a', {
              className: cx('gd-sidebar__link', it.active && 'gd-sidebar__link--active'),
              text: it.label,
              href: it.href || '#',
              onClick: it.onClick
                ? (e) => {
                    e.preventDefault();
                    it.onClick(e);
                  }
                : undefined,
            })
          ))
    )
  );
}

/**
 * Toolbar — action row.
 */
export function Toolbar(props = {}, ...children) {
  const { className, extra } = props;
  return el(
    'div',
    {
      ...omit(props, ['className', 'extra']),
      className: cx('gd-toolbar', className),
      role: 'toolbar',
    },
    el('div', { className: 'gd-toolbar__actions' }, ...children),
    extra || null
  );
}

/**
 * HamburgerButton — three-line trigger for a nav drawer.
 */
export function HamburgerButton(props = {}) {
  const { className, label = 'Menu', onClick } = props;
  return el('button', {
    ...omit(props, ['className', 'label']),
    type: 'button',
    className: cx('gd-hamburger', className),
    attrs: { 'aria-label': label },
    onClick,
  },
    el('span'),
    el('span'),
    el('span')
  );
}

/**
 * Scrollspy — “On this page” list; mark active via `activeKey`.
 */
export function Scrollspy(props = {}) {
  const { items = [], activeKey, onChange, className, title = 'On this page' } = props;
  return el(
    'nav',
    {
      ...omit(props, ['items', 'activeKey', 'onChange', 'className', 'title']),
      className: cx('gd-scrollspy', className),
      attrs: { 'aria-label': title },
    },
    el('div', { className: 'gd-scrollspy__title', text: title }),
    ...items.map((it) =>
      el('a', {
        className: cx('gd-scrollspy__link', it.key === activeKey && 'gd-scrollspy__link--active'),
        text: it.label,
        href: it.href || `#${it.key}`,
        onClick: (e) => {
          if (onChange) {
            e.preventDefault();
            onChange(it.key);
          }
        },
      })
    )
  );
}

/**
 * SplitButton — primary action + overflow menu trigger.
 */
export function SplitButton(props = {}) {
  const { text = 'Action', onClick, onMenuClick, className, type = 'primary' } = props;
  return el(
    'div',
    { className: cx('gd-split-btn', className) },
    Button({ type, text, onClick, className: 'gd-split-btn__main' }),
    Button({
      type,
      text: '▾',
      className: 'gd-split-btn__caret',
      onClick: onMenuClick,
      attrs: { 'aria-label': 'More actions' },
    })
  );
}
