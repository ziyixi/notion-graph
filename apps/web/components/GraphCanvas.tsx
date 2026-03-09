"use client";

import "@react-sigma/core/lib/react-sigma.min.css";

import {
  SigmaContainer,
  useLoadGraph,
  useRegisterEvents,
  useSigma
} from "@react-sigma/core";
import Graph from "graphology";
import { useEffect, useMemo } from "react";

import { GraphResponse, NodeType } from "../lib/types";

interface GraphCanvasProps {
  data: GraphResponse;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  onClearSelection: () => void;
}

type NodeAttrs = {
  x: number;
  y: number;
  color: string;
  size: number;
  label: string;
  baseColor: string;
  baseSize: number;
};

type EdgeAttrs = {
  color: string;
  size: number;
  baseColor: string;
  baseSize: number;
};

type SigmaInstance = ReturnType<typeof useSigma>;

const NODE_COLORS: Record<NodeType, string> = {
  person: "#0b7285",
  topic: "#c2410c",
  project: "#15803d",
  artifact: "#be185d",
  unknown: "#475569"
};

function toUnitHash(input: string): number {
  let hash = 0;
  for (let idx = 0; idx < input.length; idx += 1) {
    hash = ((hash << 5) - hash + input.charCodeAt(idx)) | 0;
  }
  return Math.abs(hash % 10000) / 10000;
}

function focusCameraOnNode(sigma: SigmaInstance, nodeId: string, ratio = 0.52): boolean {
  const displayData = sigma.getNodeDisplayData(nodeId);
  if (!displayData) {
    return false;
  }

  sigma.getCamera().animate(
    {
      x: displayData.x,
      y: displayData.y,
      ratio,
      angle: 0
    },
    { duration: 420 }
  );

  return true;
}

function applyFocusStyles(
  sigma: SigmaInstance,
  selectedNodeId: string | null,
  hoveredNodeId: string | null
): void {
  const display = sigma.getGraph();
  const focusNodeId = selectedNodeId ?? hoveredNodeId;
  const connectedNodeIds = new Set<string>();

  if (focusNodeId && display.hasNode(focusNodeId)) {
    display.forEachEdge((edgeId, _attrs, source, target) => {
      if (source === focusNodeId || target === focusNodeId) {
        connectedNodeIds.add(source);
        connectedNodeIds.add(target);
      }
    });
  }

  display.forEachNode((nodeId) => {
    const attrs = display.getNodeAttributes(nodeId) as Partial<NodeAttrs>;
    const baseColor = attrs.baseColor ?? NODE_COLORS.unknown;
    const baseSize = attrs.baseSize ?? 6;

    let nextColor = baseColor;
    let nextSize = baseSize;

    if (focusNodeId) {
      if (nodeId === focusNodeId) {
        nextColor = "#0f172a";
        nextSize = baseSize * 1.35;
      } else if (connectedNodeIds.has(nodeId)) {
        nextColor = baseColor;
        nextSize = baseSize * 1.12;
      } else {
        nextColor = "#cbd5e1";
        nextSize = Math.max(3.4, baseSize * 0.82);
      }
    }

    display.setNodeAttribute(nodeId, "color", nextColor);
    display.setNodeAttribute(nodeId, "size", nextSize);
  });

  display.forEachEdge((edgeId, _attrs, source, target) => {
    const attrs = display.getEdgeAttributes(edgeId) as Partial<EdgeAttrs>;
    const baseColor = attrs.baseColor ?? "#64748b";
    const baseSize = attrs.baseSize ?? 1.5;

    let nextColor = baseColor;
    let nextSize = baseSize;

    if (focusNodeId) {
      if (source === focusNodeId || target === focusNodeId) {
        nextColor = "#0f766e";
        nextSize = 2.35;
      } else {
        nextColor = "#d7dee8";
        nextSize = 1.05;
      }
    }

    display.setEdgeAttribute(edgeId, "color", nextColor);
    display.setEdgeAttribute(edgeId, "size", nextSize);
  });

  sigma.refresh();
}

function GraphLoader({
  graph,
  selectedNodeId,
  hoveredNodeId,
  onSelectNode
}: {
  graph: Graph;
  selectedNodeId: string | null;
  hoveredNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
}) {
  const sigma = useSigma();
  const loadGraph = useLoadGraph();
  const registerEvents = useRegisterEvents();

  useEffect(() => {
    loadGraph(graph);
    sigma.refresh();
    sigma.getCamera().animatedReset();
  }, [graph, loadGraph, sigma]);

  useEffect(() => {
    registerEvents({
      clickNode: (event) => {
        onSelectNode(event.node);
        focusCameraOnNode(sigma, event.node, 0.34);
      }
    });
  }, [registerEvents, onSelectNode, sigma]);

  useEffect(() => {
    applyFocusStyles(sigma, selectedNodeId, hoveredNodeId);
  }, [selectedNodeId, hoveredNodeId, sigma]);

  useEffect(() => {
    if (!selectedNodeId) {
      return;
    }
    const focused = focusCameraOnNode(sigma, selectedNodeId, 0.34);
    if (focused) {
      return;
    }

    const frame = window.requestAnimationFrame(() => {
      focusCameraOnNode(sigma, selectedNodeId, 0.34);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [selectedNodeId, sigma]);

  return null;
}

function GraphControls({
  selectedNodeId,
  onClearSelection
}: {
  selectedNodeId: string | null;
  onClearSelection: () => void;
}) {
  const sigma = useSigma();

  const fitGraph = () => {
    sigma.getCamera().animatedReset();
  };

  const resetZoom = () => {
    const state = sigma.getCamera().getState();
    sigma.getCamera().animate(
      {
        ...state,
        ratio: 1,
        angle: 0
      },
      { duration: 280 }
    );
  };

  const focusSelected = () => {
    if (!selectedNodeId) {
      return;
    }
    focusCameraOnNode(sigma, selectedNodeId, 0.34);
  };

  const clearSelectionAndFit = () => {
    onClearSelection();
    sigma.getCamera().animatedReset();
  };

  return (
    <div className="graph-controls">
      <button
        className="control-button icon-only"
        type="button"
        onClick={clearSelectionAndFit}
        title="Clear focus and fit graph"
        aria-label="Clear focus and fit graph"
      >
        <svg viewBox="0 0 16 16" aria-hidden="true">
          <path
            d="M3 2.5h3.2v1H4v2.2H3V2.5zm9.8 0v3.2h-1V3.5H9.5v-1h3.3zM4 10.3v2.2h2.2v1H3v-3.2h1zm7.8 0h1v3.2H9.5v-1h2.3v-2.2zM8 5.7a2.3 2.3 0 1 0 0 4.6 2.3 2.3 0 0 0 0-4.6zm-3.3 2.3a3.3 3.3 0 1 1 6.6 0 3.3 3.3 0 0 1-6.6 0z"
            fill="currentColor"
          />
        </svg>
      </button>
      <button className="control-button" type="button" onClick={fitGraph}>
        Fit Graph
      </button>
      <button className="control-button" type="button" onClick={resetZoom}>
        Reset Zoom
      </button>
      <button
        className="control-button"
        type="button"
        onClick={focusSelected}
        disabled={!selectedNodeId}
      >
        Focus Selected
      </button>
    </div>
  );
}

export function GraphCanvas({
  data,
  selectedNodeId,
  hoveredNodeId,
  onSelectNode,
  onClearSelection
}: GraphCanvasProps) {
  const graph = useMemo(() => {
    const g = new Graph();

    const filteredNodes = [...data.nodes].sort((a, b) => a.id.localeCompare(b.id));

    const allowed = new Set(filteredNodes.map((node) => node.id));
    const degreeByNode = new Map<string, number>();

    for (const edge of data.edges) {
      degreeByNode.set(edge.sourceId, (degreeByNode.get(edge.sourceId) ?? 0) + 1);
      degreeByNode.set(edge.targetId, (degreeByNode.get(edge.targetId) ?? 0) + 1);
    }

    const angleStep = filteredNodes.length > 0 ? (Math.PI * 2) / filteredNodes.length : 0;

    filteredNodes.forEach((node, index) => {
      const degree = degreeByNode.get(node.id) ?? 0;
      const depthRing = 1.15 + node.depth * 0.48;
      const seed = toUnitHash(node.id);
      const angle = index * angleStep + seed * 0.92;
      const radius = depthRing + (seed - 0.5) * 0.24;
      const baseSize = Math.max(5.2, Math.min(15, 5.4 + Math.log2(degree + 1) * 3.1));
      const baseColor = NODE_COLORS[node.type];

      g.addNode(node.id, {
        label: node.title,
        x: Math.cos(angle) * radius,
        y: Math.sin(angle) * radius,
        size: baseSize,
        color: baseColor,
        baseSize,
        baseColor
      } satisfies NodeAttrs);
    });

    data.edges
      .filter((edge) => allowed.has(edge.sourceId) && allowed.has(edge.targetId))
      .forEach((edge) => {
        if (g.hasEdge(edge.id)) {
          return;
        }

        g.addEdgeWithKey(edge.id, edge.sourceId, edge.targetId, {
          size: 1.55,
          color: "#64748b",
          baseSize: 1.55,
          baseColor: "#64748b"
        } satisfies EdgeAttrs);
      });

    return g;
  }, [data]);

  return (
    <div className="graph-canvas-shell">
      <SigmaContainer
        style={{ height: "100%", width: "100%" }}
        settings={{
          labelRenderedSizeThreshold: 7,
          renderLabels: true,
          defaultEdgeType: "line",
          labelColor: { color: "#0f172a" }
        }}
      >
        <GraphLoader
          graph={graph}
          selectedNodeId={selectedNodeId}
          hoveredNodeId={hoveredNodeId}
          onSelectNode={onSelectNode}
        />
        <GraphControls selectedNodeId={selectedNodeId} onClearSelection={onClearSelection} />
      </SigmaContainer>
    </div>
  );
}
