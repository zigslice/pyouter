import { cx, el, omit } from './util.js';

/**
 * Table / DataTable — rows & columns with optional sort headers.
 * @param {object} [props]
 * @param {Array<{key:string,title:string,sortable?:boolean}>} [props.columns]
 * @param {Array<object>} [props.dataSource]
 * @param {string} [props.sortKey]
 * @param {'asc'|'desc'} [props.sortOrder]
 * @param {function} [props.onSort]
 * @param {function} [props.rowKey]
 */
export function Table(props = {}) {
  const {
    columns = [],
    dataSource = [],
    sortKey,
    sortOrder,
    onSort,
    rowKey = (row, i) => row.key ?? i,
    className,
  } = props;

  return el(
    'div',
    {
      ...omit(props, [
        'columns',
        'dataSource',
        'sortKey',
        'sortOrder',
        'onSort',
        'rowKey',
        'className',
      ]),
      className: cx('gd-table-wrap', className),
    },
    el(
      'table',
      { className: 'gd-table' },
      el(
        'thead',
        {},
        el(
          'tr',
          {},
          ...columns.map((col) =>
            el('th', {
              className: cx(
                'gd-table__th',
                col.sortable && 'gd-table__th--sortable',
                sortKey === col.key && 'gd-table__th--sorted'
              ),
              text:
                col.title +
                (col.sortable && sortKey === col.key
                  ? sortOrder === 'asc'
                    ? ' ↑'
                    : ' ↓'
                  : ''),
              onClick: col.sortable
                ? () => {
                    const next =
                      sortKey === col.key && sortOrder === 'asc' ? 'desc' : 'asc';
                    onSort?.(col.key, next);
                  }
                : undefined,
            })
          )
        )
      ),
      el(
        'tbody',
        {},
        ...dataSource.map((row, i) =>
          el(
            'tr',
            { key: String(rowKey(row, i)), className: 'gd-table__tr' },
            ...columns.map((col) =>
              el('td', {
                className: 'gd-table__td',
                text:
                  row[col.key] != null
                    ? String(typeof row[col.key] === 'object' ? '' : row[col.key])
                    : '',
              }, typeof row[col.key] === 'object' && row[col.key]?.dom ? row[col.key] : null)
            )
          )
        )
      )
    )
  );
}

export const DataTable = Table;
