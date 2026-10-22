import { Component } from '../engine/index.js';
import { cx, el, loadUi } from './util.js';

/**
 * Escape HTML for safe preview injection.
 * @param {string} s
 */
export function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Wrap / prefix the current textarea selection.
 * @param {HTMLTextAreaElement} ta
 * @param {string} before
 * @param {string} [after]
 * @param {string} [placeholder]
 * @returns {string} next full value
 */
export function wrapSelection(ta, before, after = '', placeholder = '') {
  if (!ta) return '';
  const start = ta.selectionStart ?? 0;
  const end = ta.selectionEnd ?? 0;
  const value = ta.value ?? '';
  const selected = value.slice(start, end);
  const body = selected.length ? selected : placeholder;
  const next = value.slice(0, start) + before + body + after + value.slice(end);
  const selStart = start + before.length;
  const selEnd = selStart + body.length;
  ta.value = next;
  ta.focus();
  ta.setSelectionRange(selStart, selEnd);
  return next;
}

/**
 * Insert text at the cursor (or replace selection).
 * @param {HTMLTextAreaElement} ta
 * @param {string} text
 * @returns {string}
 */
export function insertAtCursor(ta, text) {
  if (!ta) return '';
  const start = ta.selectionStart ?? 0;
  const end = ta.selectionEnd ?? 0;
  const value = ta.value ?? '';
  const next = value.slice(0, start) + text + value.slice(end);
  const pos = start + text.length;
  ta.value = next;
  ta.focus();
  ta.setSelectionRange(pos, pos);
  return next;
}

/**
 * Prefix each selected line (or current line) with `prefix`.
 * @param {HTMLTextAreaElement} ta
 * @param {string} prefix
 * @returns {string}
 */
export function prefixLines(ta, prefix) {
  if (!ta) return '';
  const start = ta.selectionStart ?? 0;
  const end = ta.selectionEnd ?? 0;
  const value = ta.value ?? '';
  let lineStart = value.lastIndexOf('\n', start - 1) + 1;
  let lineEnd = value.indexOf('\n', end);
  if (lineEnd < 0) lineEnd = value.length;
  const block = value.slice(lineStart, lineEnd);
  const nextBlock = block
    .split('\n')
    .map((line) => (line.startsWith(prefix) ? line : prefix + line))
    .join('\n');
  const next = value.slice(0, lineStart) + nextBlock + value.slice(lineEnd);
  ta.value = next;
  ta.focus();
  ta.setSelectionRange(lineStart, lineStart + nextBlock.length);
  return next;
}

function inlineMarkdown(text) {
  let s = escapeHtml(text);
  // code first
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>');
  // images then links
  s = s.replace(
    /!\[([^\]]*)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g,
    (_m, alt, src, title) =>
      `<img src="${escapeHtml(src)}" alt="${alt}"${title ? ` title="${escapeHtml(title)}"` : ''} />`
  );
  s = s.replace(
    /\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]*)")?\)/g,
    (_m, label, href, title) =>
      `<a href="${escapeHtml(href)}"${title ? ` title="${escapeHtml(title)}"` : ''} rel="noopener noreferrer">${label}</a>`
  );
  // bold / italic (order: bold then italic)
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>');
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  s = s.replace(/_([^_]+)_/g, '<em>$1</em>');
  s = s.replace(/~~([^~]+)~~/g, '<del>$1</del>');
  return s;
}

/**
 * Lightweight Markdown → HTML (no dependency).
 * Covers headings, emphasis, links, images, lists, quotes, fences, hr, paragraphs.
 * @param {string} source
 * @returns {string}
 */
export function renderMarkdown(source) {
  const text = String(source ?? '').replace(/\r\n?/g, '\n');
  if (!text.trim()) return '';

  const lines = text.split('\n');
  const html = [];
  let i = 0;
  let inUl = false;
  let inOl = false;
  let inBlockquote = false;

  const closeLists = () => {
    if (inUl) {
      html.push('</ul>');
      inUl = false;
    }
    if (inOl) {
      html.push('</ol>');
      inOl = false;
    }
  };
  const closeQuote = () => {
    if (inBlockquote) {
      html.push('</blockquote>');
      inBlockquote = false;
    }
  };
  const closeBlocks = () => {
    closeLists();
    closeQuote();
  };

  while (i < lines.length) {
    const line = lines[i];

    // fenced code
    const fence = line.match(/^```([\w-]*)\s*$/);
    if (fence) {
      closeBlocks();
      const lang = fence[1] || '';
      const buf = [];
      i += 1;
      while (i < lines.length && !/^```\s*$/.test(lines[i])) {
        buf.push(lines[i]);
        i += 1;
      }
      i += 1; // closing ```
      html.push(
        `<pre class="gd-md-pre"${lang ? ` data-lang="${escapeHtml(lang)}"` : ''}><code>${escapeHtml(buf.join('\n'))}</code></pre>`
      );
      continue;
    }

    // hr
    if (/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(line)) {
      closeBlocks();
      html.push('<hr />');
      i += 1;
      continue;
    }

    // heading
    const heading = line.match(/^(#{1,6})\s+(.*)$/);
    if (heading) {
      closeBlocks();
      const level = heading[1].length;
      html.push(`<h${level}>${inlineMarkdown(heading[2].trim())}</h${level}>`);
      i += 1;
      continue;
    }

    // blockquote
    if (/^>\s?/.test(line)) {
      closeLists();
      if (!inBlockquote) {
        html.push('<blockquote>');
        inBlockquote = true;
      }
      html.push(`<p>${inlineMarkdown(line.replace(/^>\s?/, ''))}</p>`);
      i += 1;
      continue;
    }
    if (inBlockquote) closeQuote();

    // unordered list
    const ul = line.match(/^\s*[-*+]\s+(.*)$/);
    if (ul) {
      closeQuote();
      if (inOl) {
        html.push('</ol>');
        inOl = false;
      }
      if (!inUl) {
        html.push('<ul>');
        inUl = true;
      }
      html.push(`<li>${inlineMarkdown(ul[1])}</li>`);
      i += 1;
      continue;
    }

    // ordered list
    const ol = line.match(/^\s*\d+\.\s+(.*)$/);
    if (ol) {
      closeQuote();
      if (inUl) {
        html.push('</ul>');
        inUl = false;
      }
      if (!inOl) {
        html.push('<ol>');
        inOl = true;
      }
      html.push(`<li>${inlineMarkdown(ol[1])}</li>`);
      i += 1;
      continue;
    }

    closeLists();

    // blank → paragraph break
    if (!line.trim()) {
      i += 1;
      continue;
    }

    // paragraph (merge consecutive non-blank non-special lines)
    const para = [line];
    i += 1;
    while (i < lines.length) {
      const n = lines[i];
      if (
        !n.trim() ||
        /^#{1,6}\s/.test(n) ||
        /^```/.test(n) ||
        /^\s*[-*+]\s+/.test(n) ||
        /^\s*\d+\.\s+/.test(n) ||
        /^>\s?/.test(n) ||
        /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/.test(n)
      ) {
        break;
      }
      para.push(n);
      i += 1;
    }
    html.push(`<p>${inlineMarkdown(para.join(' '))}</p>`);
  }

  closeBlocks();
  return html.join('\n');
}

const TOOLS = [
  { id: 'bold', label: 'B', title: 'Bold', kind: 'wrap', before: '**', after: '**', placeholder: 'bold' },
  { id: 'italic', label: 'I', title: 'Italic', kind: 'wrap', before: '*', after: '*', placeholder: 'italic' },
  { id: 'heading', label: 'H', title: 'Heading', kind: 'prefix', prefix: '## ' },
  { id: 'quote', label: '>', title: 'Quote', kind: 'prefix', prefix: '> ' },
  { id: 'code', label: '`', title: 'Inline code', kind: 'wrap', before: '`', after: '`', placeholder: 'code' },
  { id: 'link', label: 'Link', title: 'Link', kind: 'link' },
  { id: 'ul', label: 'List', title: 'Bullet list', kind: 'prefix', prefix: '- ' },
  { id: 'ol', label: '1.', title: 'Numbered list', kind: 'prefix', prefix: '1. ' },
];

const MODES = [
  { id: 'edit', label: '编辑' },
  { id: 'split', label: '分栏' },
  { id: 'preview', label: '预览' },
];

/**
 * MarkdownEditor — markdown-first editor with toolbar + live preview.
 *
 * @param {object} [deps]
 * @param {string} [deps.value]
 * @param {'edit'|'split'|'preview'} [deps.mode] default `split`
 * @param {number|string} [deps.height] editor body height (default 280)
 * @param {string} [deps.placeholder]
 * @param {boolean} [deps.toolbar]
 * @param {(value:string)=>void} [deps.onChange]
 * @param {(mode:string)=>void} [deps.onModeChange]
 */
export class MarkdownEditor extends Component {
  constructor(deps = {}) {
    super(deps);
    this.state.data.value = deps.value ?? '';
    this.state.data.mode = deps.mode === 'edit' || deps.mode === 'preview' ? deps.mode : 'split';
    this.state.data.height = deps.height ?? 280;
    this.state.data.placeholder = deps.placeholder ?? 'Write Markdown…';
    this.state.data.toolbar = deps.toolbar !== false;
    this._onChange = deps.onChange || null;
    this._onModeChange = deps.onModeChange || null;
  }

  async mount(host, params = {}) {
    await loadUi();
    return super.mount(host, params);
  }

  getValue() {
    return String(this.state.data.value ?? '');
  }

  setValue(value, { refresh = true } = {}) {
    const next = String(value ?? '');
    this.state.data.value = next;
    if (refresh && this._mounted) this.refresh();
    else if (this._mounted) this._syncPreview();
    return this;
  }

  setMode(mode) {
    if (mode !== 'edit' && mode !== 'split' && mode !== 'preview') return this;
    this.state.data.mode = mode;
    this._onModeChange?.(mode);
    if (this._mounted) this.refresh();
    return this;
  }

  focus() {
    this.ids().gdMdInput?.focus();
    return this;
  }

  _emit(value) {
    this.state.data.value = value;
    this._onChange?.(value);
    this._syncPreview();
  }

  _applyTool(tool) {
    const ta = this.ids().gdMdInput;
    if (!ta) return;
    let next = ta.value;
    if (tool.kind === 'wrap') {
      next = wrapSelection(ta, tool.before, tool.after, tool.placeholder);
    } else if (tool.kind === 'prefix') {
      next = prefixLines(ta, tool.prefix);
    } else if (tool.kind === 'link') {
      const selected = ta.value.slice(ta.selectionStart, ta.selectionEnd);
      const label = selected || 'link';
      next = wrapSelection(ta, '[', '](https://)', label);
    }
    this._emit(next);
  }

  _syncMode() {
    const root = this.ids().gdMdRoot;
    if (!root) return;
    root.dataset.mode = this.state.data.mode;
    root.classList.toggle('gd-md-editor--edit', this.state.data.mode === 'edit');
    root.classList.toggle('gd-md-editor--split', this.state.data.mode === 'split');
    root.classList.toggle('gd-md-editor--preview', this.state.data.mode === 'preview');

    for (const m of MODES) {
      const btn = this.ids()[`gdMdMode_${m.id}`];
      if (!btn) continue;
      btn.classList.toggle('gd-md-editor__mode--active', m.id === this.state.data.mode);
      btn.setAttribute('aria-pressed', m.id === this.state.data.mode ? 'true' : 'false');
    }

    const edit = this.ids().gdMdEdit;
    const preview = this.ids().gdMdPreviewPane;
    if (edit) {
      edit.hidden = this.state.data.mode === 'preview';
    }
    if (preview) {
      preview.hidden = this.state.data.mode === 'edit';
    }
  }

  _syncPreview() {
    const pane = this.ids().gdMdPreview;
    if (!pane) return;
    const html = renderMarkdown(this.state.data.value);
    pane.innerHTML = html || '<p class="gd-md-editor__empty">Nothing to preview</p>';
  }

  _syncInput() {
    const ta = this.ids().gdMdInput;
    if (!ta) return;
    if (typeof document !== 'undefined' && document.activeElement === ta) return;
    if (ta.value !== this.state.data.value) ta.value = this.state.data.value;
  }

  _syncHeight() {
    const body = this.ids().gdMdBody;
    if (!body) return;
    const h = this.state.data.height;
    body.style.height = typeof h === 'number' ? `${h}px` : String(h);
  }

  render() {
    const { value, placeholder, toolbar, height } = this.state.data;

    this.ensureShell(
      (ids) => ids.gdMdRoot,
      ({ div, textarea, button }) => {
        div(
          {
            id: 'gdMdRoot',
            className: 'gd-md-editor gd-md-editor--split',
            attrs: { 'data-mode': 'split' },
          },
          div({ id: 'gdMdToolbar', className: 'gd-md-editor__toolbar' }),
          div(
            {
              id: 'gdMdBody',
              className: 'gd-md-editor__body',
              style: { height: typeof height === 'number' ? `${height}px` : String(height) },
            },
            div(
              { id: 'gdMdEdit', className: 'gd-md-editor__edit' },
              textarea({
                id: 'gdMdInput',
                className: 'gd-md-editor__input gd-textarea',
                attrs: {
                  spellcheck: 'true',
                  autocomplete: 'off',
                  'aria-label': 'Markdown source',
                },
                placeholder,
                value: value,
                onInput: (e) => {
                  this._emit(e.currentTarget.value);
                },
              })
            ),
            div(
              {
                id: 'gdMdPreviewPane',
                className: 'gd-md-editor__preview-pane',
              },
              div({
                id: 'gdMdPreview',
                className: 'gd-md-editor__preview',
                attrs: { role: 'document', 'aria-label': 'Markdown preview' },
              })
            )
          )
        );

        // silence unused — toolbar filled after shell
        void button;
      }
    );

    const bar = this.ids().gdMdToolbar;
    if (bar && !bar.dataset.ready) {
      bar.dataset.ready = '1';
      if (toolbar) {
        const formatDom = el('div', { className: 'gd-md-editor__tools' }).dom();
        for (const tool of TOOLS) {
          formatDom.appendChild(
            el('button', {
              type: 'button',
              className: cx(
                'gd-btn',
                'gd-btn--text',
                'gd-btn--sm',
                'gd-md-editor__tool',
                tool.id === 'bold' && 'gd-md-editor__tool--bold',
                tool.id === 'italic' && 'gd-md-editor__tool--italic'
              ),
              text: tool.label,
              title: tool.title,
              attrs: { 'aria-label': tool.title, 'data-tool': tool.id },
              onClick: (e) => {
                e.preventDefault();
                this._applyTool(tool);
              },
            }).dom()
          );
        }
        bar.appendChild(formatDom);
      }

      const modesEl = el('div', {
        className: 'gd-md-editor__modes',
        attrs: { role: 'group', 'aria-label': 'View mode' },
      });
      const modesDom = modesEl.dom();
      for (const m of MODES) {
        const btnEl = el('button', {
          type: 'button',
          className: cx('gd-btn', 'gd-btn--default', 'gd-btn--sm', 'gd-md-editor__mode'),
          text: m.label,
          attrs: { 'aria-pressed': 'false', 'data-mode': m.id },
          onClick: (e) => {
            e.preventDefault();
            this.setMode(m.id);
          },
        });
        const node = btnEl.dom();
        modesDom.appendChild(node);
      }
      bar.appendChild(modesDom);
    }

    // Mode buttons live outside ensureShell ids — resolve from toolbar each render.
    this.state.ref.id = this.state.ref.id || {};
    for (const m of MODES) {
      const found = bar?.querySelector?.(`[data-mode="${m.id}"]`);
      if (found) this.state.ref.id[`gdMdMode_${m.id}`] = found;
    }

    this._syncHeight();
    this._syncInput();
    this._syncMode();
    this._syncPreview();
  }
}

/**
 * @param {string} value
 * @param {HTMLElement|string} host
 * @param {object} [options]
 */
export function createMarkdownEditor(value, host, options = {}) {
  const ed = new MarkdownEditor({ ...options, value });
  const elHost =
    typeof host === 'string'
      ? typeof document !== 'undefined'
        ? document.getElementById(host)
        : null
      : host;
  if (elHost) {
    void ed.mount(elHost);
  }
  return ed;
}
