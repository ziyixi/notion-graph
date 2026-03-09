"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { DetailsPanel } from "../components/DetailsPanel";
import { SearchPanel } from "../components/SearchPanel";
import { fetchGraph, fetchNodeDetail, searchNodes } from "../lib/api";
import { GraphEdge, GraphResponse, NodeDetailResponse, NodeType, SearchItem } from "../lib/types";

const ALL_TYPES: NodeType[] = ["person", "topic", "project", "artifact", "unknown"];

const GraphCanvas = dynamic(
  () => import("../components/GraphCanvas").then((mod) => mod.GraphCanvas),
  { ssr: false }
);

export default function HomePage() {
  const [graph, setGraph] = useState<GraphResponse | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchItem[]>([]);
  const [searchTotal, setSearchTotal] = useState(0);
  const [isSearching, setIsSearching] = useState(false);
  const [isSearchCollapsed, setIsSearchCollapsed] = useState(false);
  const [detail, setDetail] = useState<NodeDetailResponse | null>(null);
  const [visibleTypes, setVisibleTypes] = useState<Set<NodeType>>(new Set(ALL_TYPES));
  const [hideIsolated, setHideIsolated] = useState(false);
  const [minDegree, setMinDegree] = useState(0);
  const [focusDepth, setFocusDepth] = useState(0);
  const [relationLabelFilter, setRelationLabelFilter] = useState("all");

  useEffect(() => {
    fetchGraph()
      .then((payload) => {
        setGraph(payload);
      })
      .catch((error) => {
        console.error(error);
      });
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      setSearchTotal(0);
      return;
    }

    setIsSearching(true);
    const handle = window.setTimeout(() => {
      searchNodes(query, Array.from(visibleTypes))
        .then((payload) => {
          setResults(payload.items);
          setSearchTotal(payload.total);
        })
        .catch((error) => {
          console.error(error);
        })
        .finally(() => {
          setIsSearching(false);
        });
    }, 200);

    return () => {
      window.clearTimeout(handle);
    };
  }, [query, visibleTypes]);

  useEffect(() => {
    if (!selectedNodeId) {
      setDetail(null);
      return;
    }

    fetchNodeDetail(selectedNodeId)
      .then((payload) => {
        setDetail(payload);
      })
      .catch((error) => {
        console.error(error);
      });
  }, [selectedNodeId]);

  const activeGraph = useMemo<GraphResponse>(() => {
    return (
      graph ?? {
        nodes: [],
        edges: [],
        meta: {
          rootPageId: "",
          generatedAt: new Date().toISOString(),
          mode: "full"
        }
      }
    );
  }, [graph]);

  const structuredRelationLabels = useMemo(() => {
    return Array.from(
      new Set(
        activeGraph.edges
          .filter((edge) => edge.relationType === "structured_relation" && edge.label)
          .map((edge) => edge.label as string)
      )
    ).sort((a, b) => a.localeCompare(b));
  }, [activeGraph.edges]);

  const filteredGraph = useMemo<GraphResponse>(() => {
    const typeFilteredNodes = activeGraph.nodes.filter((node) => visibleTypes.has(node.type));
    let allowedNodeIds = new Set(typeFilteredNodes.map((node) => node.id));

    let filteredEdges = activeGraph.edges.filter(
      (edge) => allowedNodeIds.has(edge.sourceId) && allowedNodeIds.has(edge.targetId)
    );

    if (relationLabelFilter !== "all") {
      filteredEdges = filteredEdges.filter(
        (edge) => edge.relationType !== "structured_relation" || edge.label === relationLabelFilter
      );
    }

    let filteredNodes = typeFilteredNodes;

    if (focusDepth > 0 && selectedNodeId) {
      const neighborhoodNodeIds = collectNeighborhoodNodeIds(filteredEdges, selectedNodeId, focusDepth);
      filteredNodes = filteredNodes.filter((node) => neighborhoodNodeIds.has(node.id));
      allowedNodeIds = new Set(filteredNodes.map((node) => node.id));
      filteredEdges = filteredEdges.filter(
        (edge) => allowedNodeIds.has(edge.sourceId) && allowedNodeIds.has(edge.targetId)
      );
    }

    const degreeMap = computeDegreeMap(filteredEdges);
    const requiredDegree = hideIsolated ? Math.max(1, minDegree) : minDegree;

    if (requiredDegree > 0) {
      filteredNodes = filteredNodes.filter(
        (node) => (degreeMap.get(node.id) ?? 0) >= requiredDegree
      );
      allowedNodeIds = new Set(filteredNodes.map((node) => node.id));
      filteredEdges = filteredEdges.filter(
        (edge) => allowedNodeIds.has(edge.sourceId) && allowedNodeIds.has(edge.targetId)
      );
    }

    return {
      nodes: filteredNodes,
      edges: filteredEdges,
      meta: {
        ...activeGraph.meta,
        mode: focusDepth > 0 && selectedNodeId ? "neighborhood" : "full"
      }
    };
  }, [
    activeGraph,
    focusDepth,
    hideIsolated,
    minDegree,
    relationLabelFilter,
    selectedNodeId,
    visibleTypes
  ]);

  useEffect(() => {
    if (!selectedNodeId) {
      return;
    }
    const exists = filteredGraph.nodes.some((node) => node.id === selectedNodeId);
    if (!exists) {
      setSelectedNodeId(null);
    }
  }, [filteredGraph.nodes, selectedNodeId]);

  const toggleType = (type: NodeType) => {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  };

  const clearSelection = () => {
    setSelectedNodeId(null);
    setHoveredNodeId(null);
  };

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div className="brand-block">
          <p className="eyebrow">Knowledge Graph Explorer</p>
          <h1>Notion Atlas</h1>
          <p className="top-subline">
            Explore relationships, evidence, and project context in one connected map.
          </p>
          <div className="top-links">
            <Link href="/admin">Open Admin Control Plane</Link>
          </div>
        </div>
        <div className="top-stats">
          <div className="stat-card">
            <span>Nodes</span>
            <strong>
              {filteredGraph.nodes.length}
              <small> / {activeGraph.nodes.length}</small>
            </strong>
          </div>
          <div className="stat-card">
            <span>Edges</span>
            <strong>
              {filteredGraph.edges.length}
              <small> / {activeGraph.edges.length}</small>
            </strong>
          </div>
          <div className="stat-card root-card">
            <span>Root</span>
            <strong>{activeGraph.meta.rootPageId || "loading..."}</strong>
          </div>
        </div>
      </header>

      <section className="type-filters">
        <div className="filter-label">Types</div>
        <div className="filter-actions">
          {ALL_TYPES.map((type) => (
            <button
              key={type}
              type="button"
              className={visibleTypes.has(type) ? "active" : "inactive"}
              onClick={() => toggleType(type)}
            >
              {type}
            </button>
          ))}
        </div>
        <div className="advanced-filters">
          <label className="inline-check">
            <input
              type="checkbox"
              checked={hideIsolated}
              onChange={(event) => setHideIsolated(event.target.checked)}
            />
            Hide isolated
          </label>

          <label className="inline-field">
            Min degree
            <input
              type="number"
              min={0}
              max={20}
              value={minDegree}
              onChange={(event) => setMinDegree(Number(event.target.value || 0))}
            />
          </label>

          <label className="inline-field">
            Focus depth
            <select
              value={focusDepth}
              onChange={(event) => setFocusDepth(Number(event.target.value))}
            >
              <option value={0}>Full graph</option>
              <option value={1}>1 hop</option>
              <option value={2}>2 hops</option>
              <option value={3}>3 hops</option>
            </select>
          </label>

          <label className="inline-field">
            Structured relation
            <select
              value={relationLabelFilter}
              onChange={(event) => setRelationLabelFilter(event.target.value)}
            >
              <option value="all">All labels</option>
              {structuredRelationLabels.map((label) => (
                <option key={label} value={label}>
                  {label.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <div className="content-grid">
        <SearchPanel
          query={query}
          results={results}
          total={searchTotal}
          isLoading={isSearching}
          isCollapsed={isSearchCollapsed}
          onChangeQuery={setQuery}
          onHover={setHoveredNodeId}
          onSelect={setSelectedNodeId}
          onToggleCollapsed={() => setIsSearchCollapsed((prev) => !prev)}
        />

        <section className="graph-panel">
          <div className="graph-frame-head">
            <h2>Graph View</h2>
            <p>
              {selectedNodeId
                ? "Node selected. Use focus controls and filters to inspect local context."
                : "Select nodes from graph or search results to inspect connections."}
            </p>
          </div>
          <GraphCanvas
            data={filteredGraph}
            selectedNodeId={selectedNodeId}
            hoveredNodeId={hoveredNodeId}
            onSelectNode={setSelectedNodeId}
            onClearSelection={clearSelection}
          />
        </section>

        <DetailsPanel detail={detail} />
      </div>
    </main>
  );
}

function computeDegreeMap(edges: GraphEdge[]): Map<string, number> {
  const degreeByNode = new Map<string, number>();
  edges.forEach((edge) => {
    degreeByNode.set(edge.sourceId, (degreeByNode.get(edge.sourceId) ?? 0) + 1);
    degreeByNode.set(edge.targetId, (degreeByNode.get(edge.targetId) ?? 0) + 1);
  });
  return degreeByNode;
}

function collectNeighborhoodNodeIds(
  edges: GraphEdge[],
  centerNodeId: string,
  maxDepth: number
): Set<string> {
  const adjacency = new Map<string, Set<string>>();
  edges.forEach((edge) => {
    if (!adjacency.has(edge.sourceId)) {
      adjacency.set(edge.sourceId, new Set());
    }
    if (!adjacency.has(edge.targetId)) {
      adjacency.set(edge.targetId, new Set());
    }
    adjacency.get(edge.sourceId)?.add(edge.targetId);
    adjacency.get(edge.targetId)?.add(edge.sourceId);
  });

  const visited = new Set<string>([centerNodeId]);
  const queue: Array<{ id: string; depth: number }> = [{ id: centerNodeId, depth: 0 }];

  while (queue.length > 0) {
    const current = queue.shift();
    if (!current) {
      continue;
    }
    if (current.depth >= maxDepth) {
      continue;
    }

    const neighbors = adjacency.get(current.id) ?? new Set();
    neighbors.forEach((neighborId) => {
      if (visited.has(neighborId)) {
        return;
      }
      visited.add(neighborId);
      queue.push({ id: neighborId, depth: current.depth + 1 });
    });
  }

  return visited;
}
