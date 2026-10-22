import { cx, el, omit } from './util.js';

/**
 * Walk treeData and return keys from root to `key` (inclusive), or [].
 * @param {Array<{key:string,children?:array}>} treeData
 * @param {string} key
 * @returns {string[]}
 */
export function treePathKeys(treeData, key) {
  const walk = (nodes, trail) => {
    for (const n of nodes || []) {
      const next = [...trail, n.key];
      if (n.key === key) return next;
      if (n.children?.length) {
        const found = walk(n.children, next);
        if (found) return found;
      }
    }
    return null;
  };
  return walk(treeData, []) || [];
}

/**
 * Compute next expandedKeys after toggling `key`.
 * Accordion: keep only root→key when opening; keep ancestors when closing.
 * @param {object} opts
 * @param {Array} opts.treeData
 * @param {Set|string[]} opts.expandedKeys
 * @param {string} opts.key
 * @param {boolean} [opts.accordion]
 * @returns {string[]}
 */
export function nextTreeExpandedKeys({
  treeData,
  expandedKeys,
  key,
  accordion = false,
}) {
  const expanded =
    expandedKeys instanceof Set
      ? expandedKeys
      : new Set(expandedKeys || []);
  const open = expanded.has(key);

  if (accordion) {
    const path = treePathKeys(treeData, key);
    if (!path.length) return [...expanded];
    return open ? path.slice(0, -1) : path;
  }

  const next = new Set(expanded);
  if (open) next.delete(key);
  else next.add(key);
  return [...next];
}

function toKeySet(expandedKeys) {
  return expandedKeys instanceof Set
    ? new Set(expandedKeys)
    : new Set(expandedKeys || []);
}

/**
 * Tree / OutlineView — expandable rows with guide lines.
 * Self-repaints on expand/select so it works under ensureShell.
 *
 * @param {object} [props]
 * @param {Array<{key:string,title:string,children?:array}>} [props.treeData]
 * @param {Set|string[]} [props.expandedKeys]
 * @param {function} [props.onExpand]
 * @param {string} [props.selectedKey]
 * @param {function} [props.onSelect]
 * @param {boolean} [props.accordion] 手风琴：只保留根→当前节点路径
 */
export function Tree(props = {}) {
  const {
    treeData = [],
    expandedKeys,
    onExpand,
    selectedKey: selectedKeyProp,
    onSelect,
    accordion = false,
    className,
  } = props;

  let expanded = toKeySet(expandedKeys);
  let selectedKey = selectedKeyProp;

  const root = el('div', {
    ...omit(props, [
      'treeData',
      'expandedKeys',
      'onExpand',
      'selectedKey',
      'onSelect',
      'accordion',
      'className',
    ]),
    className: cx('gd-tree', accordion && 'gd-tree--accordion', className),
    role: 'tree',
  });

  const paint = () => {
    const host = root.dom();
    while (host.firstChild) host.removeChild(host.firstChild);
    for (const n of treeData) {
      host.appendChild(renderNode(n).dom());
    }
  };

  const applyExpand = (key) => {
    const next = nextTreeExpandedKeys({
      treeData,
      expandedKeys: expanded,
      key,
      accordion,
    });
    expanded = new Set(next);
    onExpand?.(next);
    paint();
  };

  const renderNode = (node) => {
    const hasKids = Array.isArray(node.children) && node.children.length > 0;
    const open = expanded.has(node.key);

    const twist = hasKids
      ? el('button', {
          type: 'button',
          className: cx('gd-tree__twist', open && 'gd-tree__twist--open'),
          attrs: { 'aria-label': open ? 'Collapse' : 'Expand' },
          onClick: (e) => {
            e.stopPropagation();
            applyExpand(node.key);
          },
        })
      : el('span', { className: 'gd-tree__twist gd-tree__twist--leaf' });

    const selectNode = () => {
      selectedKey = node.key;
      onSelect?.(node.key, node);
      if (!accordion) {
        paint();
        return;
      }
      if (hasKids) {
        applyExpand(node.key);
      } else {
        expanded = new Set(treePathKeys(treeData, node.key).slice(0, -1));
        onExpand?.([...expanded]);
        paint();
      }
    };

    const label = el('span', {
      className: 'gd-tree__label',
      text: node.title,
    });

    const row = el(
      'div',
      {
        className: cx(
          'gd-tree__row',
          selectedKey === node.key && 'gd-tree__row--selected'
        ),
        onClick: selectNode,
      },
      twist,
      label
    );

    if (hasKids && open) {
      return el(
        'div',
        {
          className: 'gd-tree__node',
          attrs: {
            role: 'treeitem',
            'aria-expanded': 'true',
          },
        },
        row,
        el(
          'div',
          { className: 'gd-tree__children', role: 'group' },
          ...node.children.map((c) => renderNode(c))
        )
      );
    }

    return el(
      'div',
      {
        className: cx('gd-tree__node', !hasKids && 'gd-tree__node--leaf'),
        attrs: {
          role: 'treeitem',
          'aria-expanded': hasKids ? 'false' : undefined,
        },
      },
      row
    );
  };

  paint();
  return root;
}

export const OutlineView = Tree;

/** DisclosureTriangle — standalone twisty control (arrow). */
export function DisclosureTriangle(props = {}) {
  const { open = false, onClick, className } = props;
  return el('button', {
    ...omit(props, ['open', 'className']),
    type: 'button',
    className: cx('gd-tree__twist', open && 'gd-tree__twist--open', className),
    onClick,
    attrs: { 'aria-expanded': open ? 'true' : 'false' },
  });
}
