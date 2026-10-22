import { cx, el, omit } from './util.js';

/** DragHandle — grip affordance for drag & drop. */
export function DragHandle(props = {}) {
  const { className } = props;
  return el('button', {
    ...omit(props, ['className']),
    type: 'button',
    className: cx('gd-drag-handle', className),
    attrs: { 'aria-label': 'Drag', draggable: 'true' },
    text: '⠿',
  });
}

/** DropZone — landing target with active state. */
export function DropZone(props = {}, ...children) {
  const { active = false, className, label = 'Drop here' } = props;
  return el(
    'div',
    {
      ...omit(props, ['active', 'className', 'label']),
      className: cx('gd-drop-zone', active && 'gd-drop-zone--active', className),
    },
    children.length ? children : el('span', { className: 'gd-drop-zone__label', text: label })
  );
}
