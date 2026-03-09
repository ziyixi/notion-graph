"use client";

import { KeyboardEvent, useEffect, useMemo, useState } from "react";

import { NodeType, SearchItem } from "../lib/types";

const TYPE_ORDER: NodeType[] = ["person", "topic", "project", "artifact", "unknown"];

interface SearchPanelProps {
  query: string;
  results: SearchItem[];
  total: number;
  isLoading: boolean;
  isCollapsed: boolean;
  onChangeQuery: (value: string) => void;
  onHover: (nodeId: string | null) => void;
  onSelect: (nodeId: string) => void;
  onToggleCollapsed: () => void;
}

function prettyType(type: NodeType): string {
  return type.replaceAll("_", " ");
}

export function SearchPanel({
  query,
  results,
  total,
  isLoading,
  isCollapsed,
  onChangeQuery,
  onHover,
  onSelect,
  onToggleCollapsed
}: SearchPanelProps) {
  const [activeIndex, setActiveIndex] = useState(-1);

  const orderedResults = useMemo(() => {
    return [...results].sort((a, b) => {
      const typeDiff = TYPE_ORDER.indexOf(a.type) - TYPE_ORDER.indexOf(b.type);
      if (typeDiff !== 0) {
        return typeDiff;
      }
      return a.title.localeCompare(b.title);
    });
  }, [results]);

  const grouped = useMemo(() => {
    const byType = new Map<NodeType, SearchItem[]>();
    TYPE_ORDER.forEach((type) => byType.set(type, []));
    orderedResults.forEach((item) => {
      byType.get(item.type)?.push(item);
    });

    let cursor = 0;
    return TYPE_ORDER.map((type) => {
      const items = byType.get(type) ?? [];
      const startIndex = cursor;
      cursor += items.length;
      return { type, items, startIndex };
    }).filter((entry) => entry.items.length > 0);
  }, [orderedResults]);

  useEffect(() => {
    if (isCollapsed || !orderedResults.length) {
      setActiveIndex(-1);
      onHover(null);
      return;
    }
    setActiveIndex((prev) => {
      if (prev < 0) {
        return 0;
      }
      return Math.min(prev, orderedResults.length - 1);
    });
  }, [isCollapsed, orderedResults, onHover]);

  useEffect(() => {
    if (isCollapsed || activeIndex < 0 || activeIndex >= orderedResults.length) {
      onHover(null);
      return;
    }
    onHover(orderedResults[activeIndex].id);
  }, [activeIndex, isCollapsed, orderedResults, onHover]);

  const onInputKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (isCollapsed || orderedResults.length === 0) {
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((prev) => (prev + 1) % orderedResults.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((prev) => {
        if (prev <= 0) {
          return orderedResults.length - 1;
        }
        return prev - 1;
      });
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();
      if (activeIndex >= 0 && activeIndex < orderedResults.length) {
        onSelect(orderedResults[activeIndex].id);
      }
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      setActiveIndex(-1);
      onHover(null);
    }
  };

  return (
    <aside className={`search-panel ${isCollapsed ? "collapsed" : ""}`}>
      <div className="panel-head panel-head-row">
        <div>
          <h2 className="panel-title">Search</h2>
          <p className="panel-caption">Find pages and jump directly in the map.</p>
        </div>
        <button
          className="panel-toggle"
          type="button"
          onClick={onToggleCollapsed}
          aria-expanded={!isCollapsed}
        >
          {isCollapsed ? "Expand" : "Collapse"}
        </button>
      </div>

      {isCollapsed ? null : (
        <>
          <input
            className="search-input"
            value={query}
            placeholder="Find a page"
            onChange={(event) => onChangeQuery(event.target.value)}
            onKeyDown={onInputKeyDown}
          />
          <div className="panel-subtitle" role="status" aria-live="polite">
            {isLoading
              ? "Searching..."
              : `${orderedResults.length} shown${query.trim() ? ` / ${total} matched` : ""}`}
          </div>
          <ul className="results-list" aria-label="Search results">
            {!isLoading && query.trim() && orderedResults.length === 0 ? (
              <li className="result-empty">No matches found.</li>
            ) : null}

            {grouped.map((entry) => (
              <li key={`group-${entry.type}`} className="result-group">
                <div className="result-group-head">
                  <span>{prettyType(entry.type)}</span>
                  <small>{entry.items.length}</small>
                </div>
                <ul className="result-group-list">
                  {entry.items.map((item, offset) => {
                    const index = entry.startIndex + offset;
                    const isActive = index === activeIndex;
                    return (
                      <li
                        className={`result-item ${isActive ? "active" : ""}`}
                        key={item.id}
                        onMouseEnter={() => setActiveIndex(index)}
                        onMouseLeave={() => {
                          setActiveIndex(-1);
                          onHover(null);
                        }}
                        onClick={() => onSelect(item.id)}
                        role="option"
                        aria-selected={isActive}
                      >
                        <span className="result-main">
                          <strong>{item.title}</strong>
                          <small>{prettyType(item.type)}</small>
                        </span>
                        <span className="result-arrow">Open</span>
                      </li>
                    );
                  })}
                </ul>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
