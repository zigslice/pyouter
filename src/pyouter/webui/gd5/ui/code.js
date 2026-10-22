import { cx, el, omit } from './util.js';

const BREAK = /\r\n|\r|\n/;

/**
 * Split source into display lines.
 *
 * Fixes highlightjs-line-numbers.js behavior that always `pop()`s a trailing
 * empty segment — that disagrees with editors when the file ends with `\n`.
 * We keep the trailing empty line so line count matches the source.
 *
 * @param {string} code
 * @returns {string[]}
 */
export function splitCodeLines(code) {
  const text = String(code ?? '');
  if (text.length === 0) return [''];
  return text.split(BREAK);
}

/**
 * @param {string} code
 * @returns {number}
 */
export function countCodeLines(code) {
  return splitCodeLines(code).length;
}

/**
 * Lightweight tokenizer (no highlight.js dependency).
 * Emits tokens that may contain `\n`; use {@link tokensToLineNodes}.
 * @param {string} code
 * @param {string} [language]
 * @returns {Array<{type:string,text:string}>}
 */
export function tokenizeCode(code, language = 'plaintext') {
  const text = String(code ?? '');
  const lang = String(language || 'plaintext').toLowerCase();
  if (lang === 'plaintext' || lang === 'text' || lang === 'plain') {
    return text ? [{ type: 'text', text }] : [];
  }
  if (lang === 'json') return tokenizeJsonLike(text);
  if (lang === 'css') return tokenizeCss(text);
  if (lang === 'html' || lang === 'xml' || lang === 'svg') return tokenizeMarkup(text);
  // javascript / typescript / jsx / default programming
  return tokenizeJsFamily(text);
}

function pushText(out, text, type = 'text') {
  if (!text) return;
  out.push({ type, text });
}

function tokenizeJsFamily(text) {
  const out = [];
  const re =
    /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(\b(?:abstract|async|await|break|case|catch|class|const|continue|debugger|default|delete|do|else|enum|export|extends|false|finally|for|from|function|if|import|in|instanceof|let|new|null|of|return|static|super|switch|this|throw|true|try|typeof|undefined|var|void|while|with|yield)\b)|(\b(?:NaN|Infinity)\b|\b0[xX][\da-fA-F]+\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|([{}()[\];,.?:]|=>|[+\-*/%&|^~!=<>]=?=?)|(\/\/|\/\*|\*\/)|(\s+)|([^\s]+)/g;
  let m;
  while ((m = re.exec(text))) {
    if (m[1]) pushText(out, m[1], 'comment');
    else if (m[2]) pushText(out, m[2], 'string');
    else if (m[3]) pushText(out, m[3], 'keyword');
    else if (m[4]) pushText(out, m[4], 'number');
    else if (m[5]) pushText(out, m[5], 'punct');
    else if (m[7]) pushText(out, m[7], 'text');
    else if (m[8]) pushText(out, m[8], 'text');
  }
  return out;
}

function tokenizeJsonLike(text) {
  const out = [];
  const re =
    /("(?:\\.|[^"\\])*")|(\btrue\b|\bfalse\b|\bnull\b)|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|([{}[\]:,])|(\s+)|([^\s]+)/g;
  let m;
  while ((m = re.exec(text))) {
    if (m[1]) pushText(out, m[1], 'string');
    else if (m[2]) pushText(out, m[2], 'keyword');
    else if (m[3]) pushText(out, m[3], 'number');
    else if (m[4]) pushText(out, m[4], 'punct');
    else if (m[5]) pushText(out, m[5], 'text');
    else if (m[6]) pushText(out, m[6], 'text');
  }
  return out;
}

function tokenizeCss(text) {
  const out = [];
  const re =
    /(\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(@[a-zA-Z-]+)|([#.]?[a-zA-Z_-][\w-]*)|([{}:;,()\[\]])|(\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|s|ms)?)|(\s+)|([^\s]+)/g;
  let m;
  while ((m = re.exec(text))) {
    if (m[1]) pushText(out, m[1], 'comment');
    else if (m[2]) pushText(out, m[2], 'string');
    else if (m[3]) pushText(out, m[3], 'keyword');
    else if (m[4]) pushText(out, m[4], 'text');
    else if (m[5]) pushText(out, m[5], 'punct');
    else if (m[6]) pushText(out, m[6], 'number');
    else if (m[7]) pushText(out, m[7], 'text');
    else if (m[8]) pushText(out, m[8], 'text');
  }
  return out;
}

function tokenizeMarkup(text) {
  const out = [];
  const re =
    /(<!--[\s\S]*?-->)|(<\/?[a-zA-Z][^>]*>)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|([^<]+)/g;
  let m;
  while ((m = re.exec(text))) {
    if (m[1]) pushText(out, m[1], 'comment');
    else if (m[2]) pushText(out, m[2], 'keyword');
    else if (m[3]) pushText(out, m[3], 'string');
    else if (m[4]) pushText(out, m[4], 'text');
  }
  return out;
}

/**
 * Map tokens (possibly multi-line) onto per-line token lists.
 * This replaces highlightjs-line-numbers' fragile `duplicateMultilineNodes`
 * HTML rewrite — we never split markup mid-tag.
 *
 * @param {Array<{type:string,text:string}>} tokens
 * @returns {Array<Array<{type:string,text:string}>>}
 */
export function tokensToLineNodes(tokens) {
  /** @type {Array<Array<{type:string,text:string}>>} */
  const lines = [[]];
  for (const tok of tokens) {
    const parts = String(tok.text).split(BREAK);
    for (let i = 0; i < parts.length; i++) {
      if (i > 0) lines.push([]);
      if (parts[i].length) lines[lines.length - 1].push({ type: tok.type, text: parts[i] });
    }
  }
  return lines;
}

/**
 * Build highlighted line contents from source.
 * Guarantees line count === splitCodeLines(code).length
 * @param {string} code
 * @param {string} [language]
 * @returns {Array<Array<{type:string,text:string}>>}
 */
export function codeToHighlightedLines(code, language) {
  const lines = splitCodeLines(code);
  const tokens = tokenizeCode(code, language);
  const mapped = tokensToLineNodes(tokens);
  // Pad / trim to exact source line count (tokenizer must not drop trailing empty).
  while (mapped.length < lines.length) mapped.push([]);
  if (mapped.length > lines.length) mapped.length = lines.length;
  // Ensure empty lines stay empty arrays (render as blank).
  return mapped.map((parts, i) => (parts.length ? parts : lines[i] ? [{ type: 'text', text: lines[i] }] : []));
}

/**
 * Reconstruct plain text from a DOM selection inside a CodeBlock.
 * Avoids table-row copy bugs (extra blank lines in Firefox/Edge).
 *
 * @param {ParentNode} root
 * @param {string[]} sourceLines
 * @returns {string|null}
 */
export function copyTextFromCodeSelection(root, sourceLines) {
  const sel = typeof window !== 'undefined' ? window.getSelection() : null;
  if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
  const anchor = sel.anchorNode;
  if (!anchor || !root.contains(anchor)) return null;

  const lineEls = [...root.querySelectorAll('.gd-code__line')];
  if (!lineEls.length) return sel.toString();

  const selected = lineEls.filter((el) => {
    try {
      return sel.containsNode(el, true);
    } catch {
      return false;
    }
  });
  if (!selected.length) return sel.toString();

  const idxs = selected
    .map((el) => Number(el.getAttribute('data-line-number')))
    .filter((n) => Number.isFinite(n))
    .sort((a, b) => a - b);
  if (!idxs.length) return sel.toString();

  const first = idxs[0];
  const last = idxs[idxs.length - 1];
  // Map data-line-number back to 0-based source index via startFrom on root.
  const startFrom = Number(root.getAttribute('data-start-from') || '1') || 1;
  const slice = sourceLines.slice(first - startFrom, last - startFrom + 1);

  if (idxs.length === 1) {
    // Single-line: prefer actual selection string (partial line copy).
    return sel.toString().replace(/\r\n|\r|\n/g, '');
  }
  return slice.join('\n');
}

function renderLineContent(parts) {
  if (!parts.length) {
    // Keep height for empty lines without using a NBSP hack that copies as space.
    return el('span', { className: 'gd-code__empty', attrs: { 'aria-hidden': 'true' } });
  }
  return parts.map((p) =>
    el('span', {
      className: cx('gd-code__tok', p.type && p.type !== 'text' && `gd-code__tok--${p.type}`),
      text: p.text,
    })
  );
}

/**
 * CodeBlock — native code display with line numbers (no highlight.js dependency).
 *
 * Design fixes vs highlightjs-line-numbers.js:
 * - No `<table>` wrapper (copy/paste no longer invents blank lines)
 * - Tokenize → map to lines (no innerHTML multiline-span duplication)
 * - Trailing newline kept as a real empty line
 * - Single-line blocks always numbered when `lineNumbers` is on
 * - Copy uses source lines / selection helper, not table textContent
 *
 * @param {object} [props]
 * @param {string} [props.code]
 * @param {string} [props.language]
 * @param {boolean} [props.lineNumbers]
 * @param {number} [props.startFrom]
 * @param {number[]|Set<number>} [props.highlightLines] 1-based including startFrom offset
 * @param {boolean} [props.showCopy]
 * @param {string} [props.className]
 */
export function CodeBlock(props = {}) {
  if (props.mode === 'diff' || props.diff != null) {
    return DiffBlock({
      ...props,
      diff: props.diff ?? props.code,
    });
  }

  const {
    code = '',
    language = 'javascript',
    lineNumbers = true,
    startFrom = 1,
    highlightLines,
    showCopy = true,
    className,
  } = props;

  const source = String(code ?? '');
  const lines = splitCodeLines(source);
  const highlighted = codeToHighlightedLines(source, language);
  const hi = highlightLines instanceof Set ? highlightLines : new Set(highlightLines || []);
  const start = Number.isFinite(startFrom) ? startFrom : 1;

  const lineNodes = lines.map((_, i) => {
    const n = start + i;
    const parts = highlighted[i] || [];
    return el(
      'div',
      {
        className: cx(
          'gd-code__line',
          hi.has(n) && 'gd-code__line--hl'
        ),
        attrs: { 'data-line-number': String(n) },
      },
      lineNumbers
        ? el('span', {
            className: 'gd-code__n',
            attrs: { 'data-line-number': String(n), 'aria-hidden': 'true' },
          })
        : null,
      el(
        'code',
        { className: 'gd-code__c' },
        ...[].concat(renderLineContent(parts))
      )
    );
  });

  const root = el(
    'div',
    {
      ...omit(props, [
        'code',
        'diff',
        'mode',
        'language',
        'lineNumbers',
        'startFrom',
        'highlightLines',
        'showCopy',
        'className',
      ]),
      className: cx(
        'gd-code',
        lineNumbers && 'gd-code--numbered',
        `gd-code--${String(language || 'plaintext').toLowerCase()}`,
        className
      ),
      attrs: {
        'data-start-from': String(start),
        'data-language': String(language || 'plaintext'),
      },
    },
    showCopy
      ? el('button', {
          type: 'button',
          className: 'gd-code__copy gd-btn gd-btn--default gd-btn--sm',
          text: 'Copy',
          onClick: async (e) => {
            e.stopPropagation();
            const btn = e.currentTarget;
            try {
              if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(source);
              } else {
                const ta = document.createElement('textarea');
                ta.value = source;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
              }
              btn.textContent = 'Copied';
              setTimeout(() => {
                btn.textContent = 'Copy';
              }, 1200);
            } catch {
              btn.textContent = 'Failed';
              setTimeout(() => {
                btn.textContent = 'Copy';
              }, 1200);
            }
          },
        })
      : null,
    el(
      'pre',
      {
        className: 'gd-code__pre',
        onCopy: (e) => {
          const rootEl = e.currentTarget?.closest?.('.gd-code');
          if (!rootEl) return;
          const text = copyTextFromCodeSelection(rootEl, lines);
          if (text == null) return;
          e.clipboardData?.setData('text/plain', text);
          e.preventDefault();
        },
      },
      ...lineNodes
    )
  );

  return root;
}

/** Alias */
export const Code = CodeBlock;

/**
 * @typedef {'hunk'|'meta'|'add'|'del'|'ctx'} DiffLineType
 * @typedef {{
 *   type: DiffLineType,
 *   text: string,
 *   oldLine: number|null,
 *   newLine: number|null,
 *   marker: string,
 *   raw: string,
 * }} DiffLine
 */

const HUNK_RE = /^@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s@@/;

/**
 * Parse unified diff (or hunk-less +/-/space lines) into typed rows.
 * Dual line counters follow GitHub-style unified hunks.
 *
 * @param {string} text
 * @returns {DiffLine[]}
 */
export function parseDiffLines(text) {
  const source = String(text ?? '');
  if (!source.length) return [];

  const rawLines = source.split(BREAK);
  // Trailing newline from split → empty segment; drop for diff rows.
  if (rawLines.length && rawLines[rawLines.length - 1] === '') rawLines.pop();

  /** @type {DiffLine[]} */
  const out = [];
  let oldLine = 0;
  let newLine = 0;

  for (const raw of rawLines) {
    const hunk = HUNK_RE.exec(raw);
    if (hunk) {
      oldLine = Number(hunk[1]) || 0;
      newLine = Number(hunk[2]) || 0;
      out.push({
        type: 'hunk',
        text: raw,
        oldLine: null,
        newLine: null,
        marker: '',
        raw,
      });
      continue;
    }

    if (
      raw.startsWith('diff ') ||
      raw.startsWith('index ') ||
      raw.startsWith('---') ||
      raw.startsWith('+++') ||
      raw.startsWith('Binary ') ||
      raw.startsWith('\\')
    ) {
      out.push({
        type: 'meta',
        text: raw,
        oldLine: null,
        newLine: null,
        marker: '',
        raw,
      });
      continue;
    }

    const ch = raw.charAt(0);
    if (ch === '+') {
      const n = newLine || 1;
      if (newLine) newLine += 1;
      else newLine = 2;
      out.push({
        type: 'add',
        text: raw.slice(1),
        oldLine: null,
        newLine: n,
        marker: '+',
        raw,
      });
      continue;
    }
    if (ch === '-') {
      const n = oldLine || 1;
      if (oldLine) oldLine += 1;
      else oldLine = 2;
      out.push({
        type: 'del',
        text: raw.slice(1),
        oldLine: n,
        newLine: null,
        marker: '-',
        raw,
      });
      continue;
    }

    // Context: leading space (unified) or bare text (simplified).
    const body = ch === ' ' ? raw.slice(1) : raw;
    const o = oldLine || 1;
    const n = newLine || 1;
    if (oldLine) oldLine += 1;
    else oldLine = 2;
    if (newLine) newLine += 1;
    else newLine = 2;
    out.push({
      type: 'ctx',
      text: body,
      oldLine: o,
      newLine: n,
      marker: ' ',
      raw,
    });
  }

  return out;
}

/** Alias */
export const parseUnifiedDiff = parseDiffLines;

function gutterSpan(kind, n) {
  const attrs = { 'aria-hidden': 'true' };
  if (n != null) attrs['data-line-number'] = String(n);
  return el('span', {
    className: cx('gd-code__n', `gd-code__n--${kind}`, n == null && 'gd-code__n--empty'),
    attrs,
  });
}

/**
 * DiffBlock — unified diff viewer (GitHub-style dual gutters).
 * Reuses CodeBlock tokens / chrome; no highlight.js.
 *
 * @param {object} [props]
 * @param {string} [props.diff] unified / simplified diff text
 * @param {string} [props.code] alias of diff
 * @param {DiffLine[]} [props.lines] pre-parsed rows (skips parse)
 * @param {string} [props.language] highlighter for content body
 * @param {boolean} [props.showCopy]
 * @param {string} [props.className]
 */
export function DiffBlock(props = {}) {
  const {
    diff,
    code,
    lines: preLines,
    language = 'javascript',
    showCopy = true,
    className,
  } = props;

  const source = String(diff ?? code ?? '');
  const rows = Array.isArray(preLines) ? preLines : parseDiffLines(source);

  const lineNodes = rows.map((row) => {
    const isCode = row.type === 'add' || row.type === 'del' || row.type === 'ctx';
    const parts = isCode
      ? codeToHighlightedLines(row.text, language)[0] || []
      : row.text
        ? [{ type: 'text', text: row.text }]
        : [];

    return el(
      'div',
      {
        className: cx('gd-code__line', `gd-code__line--${row.type}`),
        attrs: {
          'data-diff-type': row.type,
          ...(row.oldLine != null ? { 'data-old-line': String(row.oldLine) } : {}),
          ...(row.newLine != null ? { 'data-new-line': String(row.newLine) } : {}),
        },
      },
      gutterSpan('old', row.oldLine),
      gutterSpan('new', row.newLine),
      el('span', {
        className: cx('gd-code__marker', !row.marker && 'gd-code__marker--empty'),
        attrs: {
          'aria-hidden': 'true',
          ...(row.marker ? { 'data-marker': row.marker } : {}),
        },
      }),
      el(
        'code',
        { className: 'gd-code__c' },
        ...[].concat(renderLineContent(parts))
      )
    );
  });

  const root = el(
    'div',
    {
      ...omit(props, ['diff', 'code', 'lines', 'language', 'showCopy', 'className', 'mode']),
      className: cx(
        'gd-code',
        'gd-code--diff',
        'gd-code--numbered',
        `gd-code--${String(language || 'plaintext').toLowerCase()}`,
        className
      ),
      attrs: {
        'data-language': String(language || 'plaintext'),
        'data-mode': 'diff',
      },
    },
    showCopy
      ? el('button', {
          type: 'button',
          className: 'gd-code__copy gd-btn gd-btn--default gd-btn--sm',
          text: 'Copy',
          onClick: async (e) => {
            e.stopPropagation();
            const btn = e.currentTarget;
            const payload =
              source ||
              rows.map((r) => r.raw).join('\n');
            try {
              if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(payload);
              } else {
                const ta = document.createElement('textarea');
                ta.value = payload;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
              }
              btn.textContent = 'Copied';
              setTimeout(() => {
                btn.textContent = 'Copy';
              }, 1200);
            } catch {
              btn.textContent = 'Failed';
              setTimeout(() => {
                btn.textContent = 'Copy';
              }, 1200);
            }
          },
        })
      : null,
    el('pre', { className: 'gd-code__pre' }, ...lineNodes)
  );

  return root;
}

/** Alias */
export const Diff = DiffBlock;
