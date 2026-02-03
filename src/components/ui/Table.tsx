/**
 * Reusable Table Component
 */

import React from 'react';

interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  width?: string;
}

interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyField: keyof T;
  selectable?: boolean;
  selectedIds?: Set<string>;
  onSelect?: (id: string) => void;
  onSelectAll?: (selected: boolean) => void;
  emptyMessage?: string;
  loading?: boolean;
}

function Table<T extends Record<string, any>>({
  columns,
  data,
  keyField,
  selectable = false,
  selectedIds = new Set(),
  onSelect,
  onSelectAll,
  emptyMessage = 'No data found',
  loading = false,
}: TableProps<T>) {
  const allSelected = data.length > 0 && data.every(item => selectedIds.has(String(item[keyField])));

  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '600px' }}>
          <thead>
            <tr style={{ background: '#f9fafb' }}>
              {selectable && (
                <th style={thStyle}>
                  <input type="checkbox" checked={allSelected} onChange={e => onSelectAll?.(e.target.checked)} style={{ accentColor: '#10B981' }} />
                </th>
              )}
              {columns.map(col => (
                <th key={col.key} style={{ ...thStyle, width: col.width }}>{col.header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={columns.length + (selectable ? 1 : 0)} style={emptyStyle}>Loading...</td></tr>
            ) : data.length === 0 ? (
              <tr><td colSpan={columns.length + (selectable ? 1 : 0)} style={emptyStyle}>{emptyMessage}</td></tr>
            ) : (
              data.map(item => (
                <tr key={String(item[keyField])} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  {selectable && (
                    <td style={tdStyle}>
                      <input type="checkbox" checked={selectedIds.has(String(item[keyField]))} onChange={() => onSelect?.(String(item[keyField]))} style={{ accentColor: '#10B981' }} />
                    </td>
                  )}
                  {columns.map(col => (
                    <td key={col.key} style={tdStyle}>{col.render ? col.render(item) : item[col.key]}</td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb',
  fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase',
};

const tdStyle: React.CSSProperties = {
  padding: '12px 16px', fontSize: '14px',
};

const emptyStyle: React.CSSProperties = {
  padding: '40px', textAlign: 'center', color: '#6b7280',
};

export default Table;
