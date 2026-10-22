import { cx, el, omit } from './util.js';

/**
 * Menu — vertical or horizontal nav menu with optional submenus (antd Menu).
 * @param {object} [props]
 * @param {Array<{key:string,label:string,children?:array,disabled?:boolean,danger?:boolean,type?:'divider'|'group'}>} [props.items]
 * @param {'vertical'|'horizontal'|'inline'} [props.mode]
 * @param {string} [props.selectedKey]
 * @param {string[]} [props.openKeys]
 * @param {function} [props.onClick]
 * @param {function} [props.onOpenChange]
 */
export function Menu(props = {}) {
  const {
    items = [],
    mode = 'vertical',
    selectedKey,
    openKeys = [],
    onClick,
    onOpenChange,
    className,
  } = props;

  const openSet = new Set(openKeys);

  const renderItems = (list, depth = 0) =>
    list.flatMap((it) => {
      if (it.type === 'divider') {
        return [el('div', { className: 'gd-menu__divider', key: it.key || `d-${depth}` })];
      }
      if (it.type === 'group') {
        return [
          el('div', {
            className: 'gd-menu__group-title',
            text: it.label,
            key: it.key || it.label,
          }),
          ...renderItems(it.children || [], depth),
        ];
      }
      const hasKids = Array.isArray(it.children) && it.children.length > 0;
      const opened = openSet.has(it.key);
      if (hasKids) {
        return [
          el(
            'div',
            { className: 'gd-menu__submenu', key: it.key },
            el('button', {
              type: 'button',
              className: cx('gd-menu__item', 'gd-menu__submenu-title'),
              text: `${it.label}${mode === 'horizontal' ? '' : opened ? ' ▾' : ' ▸'}`,
              disabled: !!it.disabled,
              onClick: () => {
                const next = new Set(openSet);
                if (opened) next.delete(it.key);
                else next.add(it.key);
                onOpenChange?.([...next]);
              },
            }),
            (opened || mode === 'horizontal')
              ? el(
                  'div',
                  { className: cx('gd-menu__sub', mode === 'horizontal' && 'gd-menu__sub--popup') },
                  ...renderItems(it.children, depth + 1)
                )
              : null
          ),
        ];
      }
      return [
        el('button', {
          type: 'button',
          key: it.key,
          className: cx(
            'gd-menu__item',
            selectedKey === it.key && 'gd-menu__item--selected',
            it.danger && 'gd-menu__item--danger'
          ),
          text: it.label,
          disabled: !!it.disabled,
          onClick: () => onClick?.({ key: it.key, item: it }),
        }),
      ];
    });

  return el(
    'nav',
    {
      ...omit(props, [
        'items',
        'mode',
        'selectedKey',
        'openKeys',
        'onClick',
        'onOpenChange',
        'className',
      ]),
      className: cx('gd-menu', `gd-menu--${mode}`, className),
      role: 'menu',
    },
    ...renderItems(items)
  );
}
