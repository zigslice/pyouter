import { Component } from '../engine/index.js';
import { cx, el, loadUi } from './util.js';

/**
 * @typedef {'pending'|'active'|'done'} TodoStatus
 * @typedef {{
 *   key?: string|number,
 *   text?: string,
 *   title?: string,
 *   status?: TodoStatus|'in_progress'|'completed'|'todo',
 *   disabled?: boolean,
 * }} TodoItemInput
 */

/**
 * Normalize status aliases.
 * @param {string} [status]
 * @returns {TodoStatus}
 */
export function normalizeTodoStatus(status) {
  const s = String(status || 'pending').toLowerCase();
  if (s === 'active' || s === 'in_progress' || s === 'current' || s === 'running') return 'active';
  if (s === 'done' || s === 'completed' || s === 'complete' || s === 'finished') return 'done';
  return 'pending';
}

/**
 * @param {TodoItemInput[]|string[]} items
 * @returns {Array<{key:string,text:string,status:TodoStatus,disabled:boolean,raw:any}>}
 */
export function normalizeTodoItems(items = []) {
  return (items || []).map((item, i) => {
    if (item == null || typeof item === 'string' || typeof item === 'number') {
      return {
        key: `todo-${i}`,
        text: String(item ?? ''),
        status: 'pending',
        disabled: false,
        raw: item,
      };
    }
    return {
      key: String(item.key ?? item.id ?? `todo-${i}`),
      text: String(item.text ?? item.title ?? item.label ?? ''),
      status: normalizeTodoStatus(item.status),
      disabled: !!item.disabled,
      raw: item,
    };
  });
}

/**
 * Count done / total for header badge.
 * @param {Array<{status:TodoStatus}>} items
 */
export function countTodoProgress(items = []) {
  const total = items.length;
  const done = items.filter((it) => it.status === 'done').length;
  return { done, total };
}

/**
 * Cycle pending → active → done → pending (handy for demos).
 * @param {TodoStatus} status
 * @returns {TodoStatus}
 */
export function nextTodoStatus(status) {
  const s = normalizeTodoStatus(status);
  if (s === 'pending') return 'active';
  if (s === 'active') return 'done';
  return 'pending';
}

function statusIcon(status) {
  if (status === 'active') {
    return el(
      'span',
      {
        className: 'gd-todo__icon gd-todo__icon--active',
        attrs: { 'aria-hidden': 'true' },
      },
      el('span', { className: 'gd-todo__arrow' })
    );
  }
  if (status === 'done') {
    return el(
      'span',
      {
        className: 'gd-todo__icon gd-todo__icon--done',
        attrs: { 'aria-hidden': 'true' },
      },
      el('span', { className: 'gd-todo__check' })
    );
  }
  return el('span', {
    className: 'gd-todo__icon gd-todo__icon--pending',
    attrs: { 'aria-hidden': 'true' },
  });
}

/**
 * TodoList view — mountable Component (prefer calling `TodoList(props)` in trees).
 */
export class TodoListView extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.title = deps.title ?? 'To-dos';
    this.state.data.items = normalizeTodoItems(deps.items);
    this.state.data.showProgress = deps.showProgress !== false;
    this.state.data.className = deps.className || '';
    // Bind so inline handlers can use this.setItems / this.getItems
    this._onItemClick =
      typeof deps.onItemClick === 'function' ? deps.onItemClick.bind(this) : null;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  /**
   * @param {TodoItemInput[]|string[]} items
   */
  setItems(items) {
    this.setData({ items: normalizeTodoItems(items) }, { refresh: !!this._mounted });
    return this;
  }

  getItems() {
    return this.state.data.items;
  }

  getProgress() {
    return countTodoProgress(this.state.data.items);
  }

  setTitle(title) {
    this.setData({ title: String(title ?? '') }, { refresh: !!this._mounted });
    return this;
  }

  _renderItem(item, index) {
    const interactive = typeof this._onItemClick === 'function' && !item.disabled;
    const body = [statusIcon(item.status), el('span', { className: 'gd-todo__text', text: item.text })];
    return el(
      'li',
      {
        key: item.key,
        className: cx(
          'gd-todo__item',
          `gd-todo__item--${item.status}`,
          item.disabled && 'gd-todo__item--disabled'
        ),
        attrs: {
          role: 'listitem',
          'data-status': item.status,
          'aria-current': item.status === 'active' ? 'step' : undefined,
        },
      },
      interactive
        ? el(
            'button',
            {
              type: 'button',
              className: 'gd-todo__row gd-todo__row--interactive',
              onClick: (e) => {
                e.preventDefault();
                this._onItemClick?.(item, index);
              },
            },
            ...body
          )
        : el('div', { className: 'gd-todo__row' }, ...body)
    );
  }

  render() {
    const { title, items, showProgress, className } = this.state.data;
    const { done, total } = countTodoProgress(items);

    this.ensureShell(
      (ids) => ids.gdTodoRoot,
      ({ div, ul, span }) => {
        div(
          {
            id: 'gdTodoRoot',
            className: cx('gd-todo', className),
            attrs: { role: 'list', 'aria-label': title },
          },
          div(
            { className: 'gd-todo__header' },
            span({ id: 'gdTodoTitle', className: 'gd-todo__title', text: title }),
            showProgress
              ? span({
                  id: 'gdTodoProgress',
                  className: 'gd-todo__progress',
                  text: `${done}/${total}`,
                  attrs: { 'aria-label': `${done} of ${total} completed` },
                })
              : null
          ),
          ul({ id: 'gdTodoList', className: 'gd-todo__list' })
        );
      }
    );

    const root = this.ids().gdTodoRoot;
    const titleEl = this.ids().gdTodoTitle;
    const progressEl = this.ids().gdTodoProgress;
    const list = this.ids().gdTodoList;
    if (!root || !list) return;

    if (titleEl) titleEl.innerText = title;
    if (typeof root.setAttribute === 'function') {
      root.setAttribute('aria-label', title);
    }

    if (progressEl) {
      progressEl.innerText = `${done}/${total}`;
      if (typeof progressEl.setAttribute === 'function') {
        progressEl.setAttribute('aria-label', `${done} of ${total} completed`);
      }
    }

    list.textContent = '';
    for (let i = 0; i < items.length; i++) {
      list.appendChild(this._renderItem(items[i], i).dom());
    }
  }
}

/**
 * TodoList — Cursor-style to-dos (like Button: call in the tree, no pre-`new` on `this`).
 *
 * ```js
 * div(
 *   { id: 'root' },
 *   TodoList({
 *     items: [...],
 *     onItemClick(item, index) {
 *       this.setItems(this.getItems().map(...)); // `this` is the list
 *     },
 *   })
 * )
 * ```
 *
 * Statuses: `pending` · `active` · `done`
 *
 * @param {object} [props]
 * @returns {TodoListView}
 */
export function TodoList(props = {}) {
  return new TodoListView(props);
}

/**
 * @param {object} [options]
 * @param {HTMLElement|string} [host]
 */
export function createTodoList(options = {}, host) {
  const list = TodoList(options);
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) void list.mount(elHost);
  return list;
}

/** Alias */
export const Todos = TodoList;
export const Todo = TodoList;
