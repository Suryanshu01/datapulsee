export default function DataPreview({ schema, sample, stats, rowCount }) {
  return (
    <div className="preview-page">
      <h2 className="preview-page-title">Data Preview</h2>

      {/* Data Profile Card */}
      <div className="data-profile">
        <div className="data-profile-title">Dataset Profile</div>
        <div className="data-profile-grid">
          <div className="data-profile-stat">
            <div className="data-profile-stat-label">Rows</div>
            <div className="data-profile-stat-value">{rowCount?.toLocaleString() || "—"}</div>
          </div>
          <div className="data-profile-stat">
            <div className="data-profile-stat-label">Columns</div>
            <div className="data-profile-stat-value">{schema?.length || "—"}</div>
          </div>
          <div className="data-profile-stat">
            <div className="data-profile-stat-label">Numeric</div>
            <div className="data-profile-stat-value">
              {schema?.filter((c) => stats?.[c.column]?.avg !== undefined).length || 0}
            </div>
          </div>
          <div className="data-profile-stat">
            <div className="data-profile-stat-label">Categorical</div>
            <div className="data-profile-stat-value">
              {schema?.filter((c) => stats?.[c.column]?.avg === undefined).length || 0}
            </div>
          </div>
        </div>
      </div>

      <div className="preview-section-hd">Columns & Types ({schema?.length})</div>
      <div className="schema-grid">
        {schema?.map((col) => (
          <div key={col.column} className="schema-card">
            <div className="schema-col">{col.column}</div>
            <div className="schema-type">{col.type}</div>
            {stats?.[col.column] && (
              <div className="schema-stats">
                {stats[col.column].min !== undefined && <span className="schema-stat">Min {stats[col.column].min}</span>}
                {stats[col.column].max !== undefined && <span className="schema-stat">Max {stats[col.column].max}</span>}
                {stats[col.column].avg !== undefined && <span className="schema-stat">Avg {stats[col.column].avg}</span>}
                <span className="schema-stat">{stats[col.column].unique} unique</span>
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="preview-section-hd">Sample Rows</div>
      <div className="preview-tbl-wrap">
        <table className="preview-tbl">
          <thead>
            <tr>{schema?.map((c) => <th key={c.column}>{c.column}</th>)}</tr>
          </thead>
          <tbody>
            {sample?.map((row, i) => (
              <tr key={i}>
                {schema?.map((c) => <td key={c.column}>{String(row[c.column] ?? "")}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
