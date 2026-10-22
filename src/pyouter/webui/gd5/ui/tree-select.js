import { cx, el, omit } from './util.js';

/**
 * TreeSelect — select a node from a tree (antd TreeSelect, simplified).
 * @param {object} [props]
 * @param {Array<{value:string,title:string,children?:array}>} [props.treeData]
 * @param {string} [props.value]
 * @param {boolean} [props.open]
 * @param {function} [props.onChange]
 * @param {function} [props.onOpenChange]
 */
export function TreeSelect(props = {}) {
  const {
    treeData = [],
    value,
    open = false,
    onChange,
    onOpenChange,
    placeholder = 'Please select',
    className,
  } = props;

  const findTitle = (nodes, v) => {
    for (const n of nodes) {
      if (n.value === v) return n.title;
      if (n.children) {
        const t = findTitle(n.children, v);
        if (t) return t;
      }
    }
    return null;
  };

  const label = value != null ? findTitle(treeData, value) || value : placeholder;

  const renderNodes = (nodes, depth = 0) =>
    nodes.flatMap((n) => [
      el('button', {
        type: 'button',
        className: cx(
          'gd-tree-select__option',
          n.value === value && 'gd-tree-select__option--active'
        ),
        style: { paddingLeft: `${12 + depth * 14}px` },
        text: n.title,
        onClick: () => {
          onChange?.(n.value, n);
          onOpenChange?.(false);
        },
      }),
      ...(n.children ? renderNodes(n.children, depth + 1) : []),
    ]);

  return el(
    'div',
    {
      ...omit(props, [
        'treeData',
        'value',
        'open',
        'onChange',
        'onOpenChange',
        'placeholder',
        'className',
      ]),
      className: cx('gd-tree-select', open && 'gd-tree-select--open', className),
    },
    el('button', {
      type: 'button',
      className: 'gd-tree-select__trigger',
      text: String(label),
      onClick: () => onOpenChange?.(!open),
    }),
    open
      ? el('div', { className: 'gd-tree-select__dropdown' }, ...renderNodes(treeData))
      : null
  );
}
