import { cx, el, omit } from './util.js';

/**
 * Layout — page shell (antd Layout).
 * Compose Layout.Header / Sider / Content / Footer via helpers below.
 */
export function Layout(props = {}, ...children) {
  const { className, hasSider = false } = props;
  return el(
    'div',
    {
      ...omit(props, ['className', 'hasSider']),
      className: cx('gd-layout', hasSider && 'gd-layout--has-sider', className),
    },
    ...children
  );
}

export function LayoutHeader(props = {}, ...children) {
  const { className } = props;
  return el(
    'header',
    {
      ...omit(props, ['className']),
      className: cx('gd-layout__header', className),
    },
    ...children
  );
}

export function LayoutSider(props = {}, ...children) {
  const { className, width = 200, collapsed = false, collapsedWidth = 64 } = props;
  const w = collapsed ? collapsedWidth : width;
  return el(
    'aside',
    {
      ...omit(props, ['className', 'width', 'collapsed', 'collapsedWidth']),
      className: cx('gd-layout__sider', collapsed && 'gd-layout__sider--collapsed', className),
      style: { width: typeof w === 'number' ? `${w}px` : w, flex: `0 0 ${typeof w === 'number' ? w + 'px' : w}` },
    },
    ...children
  );
}

export function LayoutContent(props = {}, ...children) {
  const { className } = props;
  return el(
    'main',
    {
      ...omit(props, ['className']),
      className: cx('gd-layout__content', className),
    },
    ...children
  );
}

export function LayoutFooter(props = {}, ...children) {
  const { className } = props;
  return el(
    'footer',
    {
      ...omit(props, ['className']),
      className: cx('gd-layout__footer', className),
    },
    ...children
  );
}

Layout.Header = LayoutHeader;
Layout.Sider = LayoutSider;
Layout.Content = LayoutContent;
Layout.Footer = LayoutFooter;
