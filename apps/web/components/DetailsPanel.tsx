"use client";

import { NodeDetailResponse } from "../lib/types";

interface DetailsPanelProps {
  detail: NodeDetailResponse | null;
}

export function DetailsPanel({ detail }: DetailsPanelProps) {
  if (!detail) {
    return (
      <aside className="details-panel">
        <h2 className="panel-title">Node Details</h2>
        <p className="panel-caption">Select a node to inspect metadata and relations.</p>
      </aside>
    );
  }

  const relationEntries = Object.entries(detail.adjacentByRelation);

  return (
    <aside className="details-panel">
      <div className="panel-head">
        <h2 className="panel-title">{detail.node.title}</h2>
        <div className="detail-chip-row">
          <span className="detail-chip">{detail.node.type}</span>
          <span className="detail-chip">Depth {detail.node.depth}</span>
        </div>
      </div>
      <p className="detail-snippet">{detail.node.snippet ?? "No snippet available."}</p>

      <div className="details-section">
        <h3>Ancestor Path</h3>
        <p className="detail-breadcrumb">{detail.ancestors.map((item) => item.title).join(" / ") || "Root"}</p>
      </div>

      <div className="details-section">
        <h3>Connected Nodes</h3>
        {relationEntries.length === 0 ? (
          <p className="panel-caption">No connected nodes available.</p>
        ) : (
          relationEntries.map(([relation, items]) => (
            <div key={relation} className="relation-block">
              <div className="relation-head">
                <strong>{relation.replaceAll("_", " ")}</strong>
                <span>{items.length}</span>
              </div>
              <ul>
                {items.map((item) => (
                  <li key={`${relation}-${item.id}`}>{item.title}</li>
                ))}
              </ul>
            </div>
          ))
        )}
      </div>

      <a className="notion-link" href={detail.notionUrl} target="_blank" rel="noreferrer">
        Open in Notion
      </a>
    </aside>
  );
}
