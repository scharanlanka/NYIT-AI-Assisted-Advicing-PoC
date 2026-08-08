"use client";

import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { Course, Program, Student } from "@/lib/types";
import { NYIT_BLUE, NYIT_GOLD } from "@/lib/types";

interface GraphNode {
  id: string;
  x: number;
  y: number;
}
interface GraphLayout {
  nodes: GraphNode[];
  edges: { from: GraphNode; to: GraphNode }[];
  width: number;
  height: number;
}

function layoutGraph(chain: Record<string, string[][]>, targetId: string): GraphLayout {
  const nodes = Object.keys(chain);
  if (nodes.length === 0) return { nodes: [], edges: [], width: 0, height: 0 };
  const parents: Record<string, string[]> = {};
  for (const n of nodes) parents[n] = [];
  for (const target of Object.keys(chain)) {
    for (const group of chain[target]) {
      for (const source of group) {
        if (!parents[source]) parents[source] = [];
        parents[target].push(source);
      }
    }
  }
  const depth: Record<string, number> = {};
  const roots = nodes.filter((n) => parents[n].length === 0);
  for (const r of roots) depth[r] = 0;
  let changed = true;
  let iters = 0;
  while (changed && iters < 50) {
    changed = false;
    iters++;
    for (const n of nodes) {
      if (parents[n].length === 0) continue;
      const parentDepths = parents[n]
        .map((p) => depth[p])
        .filter((d) => d !== undefined);
      if (parentDepths.length === 0) continue;
      const newD = Math.max(...parentDepths) + 1;
      if (depth[n] !== newD) {
        depth[n] = newD;
        changed = true;
      }
    }
  }
  for (const n of nodes) if (depth[n] === undefined) depth[n] = 0;
  const levels: Record<number, string[]> = {};
  for (const n of nodes) {
    const d = depth[n];
    if (!levels[d]) levels[d] = [];
    levels[d].push(n);
  }
  const maxDepth = Math.max(...Object.keys(levels).map((d) => parseInt(d)));
  const width = 780;
  const height = 60 + maxDepth * 90;
  const positioned: GraphNode[] = [];
  for (const dStr of Object.keys(levels)) {
    const d = parseInt(dStr);
    levels[d].sort();
    const y = 40 + d * 90;
    const spacing = width / (levels[d].length + 1);
    levels[d].forEach((n, i) => {
      positioned.push({ id: n, x: spacing * (i + 1), y });
    });
  }
  const posMap: Record<string, GraphNode> = {};
  positioned.forEach((p) => (posMap[p.id] = p));
  const edges: { from: GraphNode; to: GraphNode }[] = [];
  for (const target of Object.keys(chain)) {
    for (const group of chain[target]) {
      for (const source of group) {
        if (posMap[source] && posMap[target]) {
          edges.push({ from: posMap[source], to: posMap[target] });
        }
      }
    }
  }
  return { nodes: positioned, edges, width, height };
}

export default function PrereqExplorer({
  student,
  program,
}: {
  student: Student;
  program: Program;
}) {
  const [universeCourses, setUniverseCourses] = useState<string[]>([]);
  const [allCoursesList, setAllCoursesList] = useState<string[]>([]);
  const [courseIndex, setCourseIndex] = useState<Record<string, Course>>({});
  const [selectedCourseId, setSelectedCourseId] = useState<string>("");
  const [scope, setScope] = useState<"program" | "all">("program");
  const [chain, setChain] = useState<Record<string, string[][]>>({});
  const [dependents, setDependents] = useState<string[]>([]);
  const [courseError, setCourseError] = useState<string>("");

  useEffect(() => {
    // Load program universe
    api.getProgramUniverse(program.program_id).then((r) => {
      setUniverseCourses(r.courses);
    });
    // Load full course list for the "all" scope
    api.listCourses().then((r) => {
      const ids = r.courses.map((c) => c.course_id).sort();
      setAllCoursesList(ids);
      // Build small index
      const idx: Record<string, Course> = {};
      r.courses.forEach((c) => (idx[c.course_id] = c as any));
      setCourseIndex(idx);
    });
  }, [program.program_id]);

  const validUniverseCourses = useMemo(
    () => universeCourses.filter((cid) => !!courseIndex[cid]),
    [universeCourses, courseIndex]
  );

  const availableCourses = scope === "program" ? validUniverseCourses : allCoursesList;

  useEffect(() => {
    if (availableCourses.length === 0) {
      setSelectedCourseId("");
      return;
    }
    if (!selectedCourseId || !availableCourses.includes(selectedCourseId)) {
      setSelectedCourseId(availableCourses[0]);
    }
  }, [availableCourses, selectedCourseId]);

  useEffect(() => {
    if (!selectedCourseId) return;
    setCourseError("");
    setChain({});
    setDependents([]);

    api.getPrereqChain(selectedCourseId)
      .then((r) => setChain(r.prereq_groups_by_course))
      .catch(() => {
        setChain({});
        setCourseError(`No prerequisite graph is available for ${selectedCourseId}.`);
      });

    api.getDependents(selectedCourseId)
      .then((r) => setDependents(r.direct_dependents))
      .catch(() => setDependents([]));

    if (!courseIndex[selectedCourseId]) {
      api.getCourse(selectedCourseId)
        .then((c) =>
          setCourseIndex((prev) => ({ ...prev, [selectedCourseId]: c }))
        )
        .catch(() => {
          setCourseError(`Course details for ${selectedCourseId} are not available in the catalog.`);
        });
    }
  }, [selectedCourseId, courseIndex]);

  const layout = useMemo(
    () => layoutGraph(chain, selectedCourseId),
    [chain, selectedCourseId]
  );

  const completedOnly = new Set(student.completed_courses);
  const currentSet = new Set(student.current_courses);
  const completed = new Set([...student.completed_courses, ...student.current_courses]);
  const c = courseIndex[selectedCourseId];
  const alreadyCompleted = completedOnly.has(selectedCourseId);
  const inProgress = currentSet.has(selectedCourseId);

  // Check prereq status
  const prereqStatus = (() => {
    if (!c) return { satisfied: true, missing: [] };
    if (!c.prerequisite_groups || c.prerequisite_groups.length === 0) {
      return { satisfied: true, missing: [] };
    }
    const missing: string[][] = [];
    for (const group of c.prerequisite_groups) {
      if (!group.some((p) => completed.has(p))) missing.push(group);
    }
    return { satisfied: missing.length === 0, missing };
  })();

  const shownDependents =
    scope === "program"
      ? dependents.filter((d) => validUniverseCourses.includes(d))
      : dependents;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1" style={{ color: NYIT_BLUE }}>
        Prerequisite Chain Explorer
      </h2>
      <p className="text-xs text-gray-500 mb-4">
        Gold = target. Green = already completed. Amber dashed = in progress. White = still needed.
      </p>

      <div className="flex items-center justify-between mb-2">
        <label className="text-xs text-gray-600">
          Choose a course ({availableCourses.length} shown)
        </label>
        <div className="text-xs flex items-center gap-3">
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="radio"
              checked={scope === "program"}
              onChange={() => setScope("program")}
            />
            <span>Just {program.program_id}</span>
          </label>
          <label className="flex items-center gap-1 cursor-pointer">
            <input
              type="radio"
              checked={scope === "all"}
              onChange={() => setScope("all")}
            />
            <span>All programs</span>
          </label>
        </div>
      </div>
      <select
        value={selectedCourseId}
        onChange={(e) => setSelectedCourseId(e.target.value)}
        className="w-full text-sm border border-gray-300 rounded px-2 py-1 mb-4"
      >
        {availableCourses.map((cid) => (
          <option key={cid} value={cid}>
            {cid} {courseIndex[cid] ? `: ${courseIndex[cid].title}` : ""}
          </option>
        ))}
      </select>

      {courseError && (
        <div className="mb-3 rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          {courseError}
        </div>
      )}

      {c && (
        <div className="mb-3">
          <div className="font-semibold" style={{ color: NYIT_BLUE }}>
            {c.title}
          </div>
          <div className="text-xs text-gray-500">
            {c.department} • {c.credits} cr • Offered: {(c.semesters_offered || []).join(", ")}
          </div>
          <div className="mt-2 text-sm">
            {alreadyCompleted ? (
              <div className="p-2 bg-green-50 border border-green-200 rounded">
                ✅ <strong>{student.name}</strong> has already completed{" "}
                <strong>{selectedCourseId}</strong> in a prior term.
              </div>
            ) : inProgress ? (
              <div
                className="p-2 rounded"
                style={{ background: "#fff8e1", border: "1px solid #ffc107" }}
              >
                ⏳ <strong>{student.name}</strong> is currently enrolled in{" "}
                <strong>{selectedCourseId}</strong> this term.
              </div>
            ) : prereqStatus.satisfied ? (
              <div className="p-2 bg-green-50 border border-green-200 rounded">
                ✅ <strong>{student.name}</strong> can register for{" "}
                <strong>{selectedCourseId}</strong>.
              </div>
            ) : (
              <div className="p-2 bg-red-50 border border-red-200 rounded">
                🚫 Still needs:{" "}
                {prereqStatus.missing
                  .map((g) => `(${g.join(" OR ")})`)
                  .join(" AND ")}
              </div>
            )}
          </div>
        </div>
      )}

      {layout.nodes.length <= 1 ? (
        <div className="p-4 text-center text-gray-500 text-sm bg-gray-50 rounded">
          {selectedCourseId} has no prerequisites.
        </div>
      ) : (
        <div className="overflow-x-auto bg-white border border-gray-200 rounded-lg p-2">
          <svg width={layout.width} height={layout.height} style={{ minWidth: layout.width }}>
            <defs>
              <marker
                id="arrow"
                viewBox="0 0 10 10"
                refX="9"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#888" />
              </marker>
            </defs>
            {layout.edges.map((e, i) => (
              <line
                key={i}
                x1={e.from.x}
                y1={e.from.y + 18}
                x2={e.to.x}
                y2={e.to.y - 18}
                stroke="#888"
                strokeWidth="1.4"
                markerEnd="url(#arrow)"
              />
            ))}
            {layout.nodes.map((n) => {
              const isTarget = n.id === selectedCourseId;
              const isCompleted = completedOnly.has(n.id);
              const isCurrent = currentSet.has(n.id);
              let fill = "white";
              let stroke: string = NYIT_BLUE;
              let strokeDasharray: string | undefined;
              if (isTarget && isCompleted) {
                fill = "#c8e6c9";
                stroke = NYIT_GOLD;
              } else if (isTarget && isCurrent) {
                fill = "#fff8e1";
                stroke = NYIT_GOLD;
              } else if (isTarget) {
                fill = NYIT_GOLD;
                stroke = NYIT_BLUE;
              } else if (isCompleted) {
                fill = "#c8e6c9";
                stroke = "#2e7d32";
              } else if (isCurrent) {
                fill = "#fff8e1";
                stroke = "#ffa000";
                strokeDasharray = "4 3";
              }
              return (
                <g key={n.id}>
                  <rect
                    x={n.x - 42}
                    y={n.y - 16}
                    width="84"
                    height="32"
                    rx="4"
                    fill={fill}
                    stroke={stroke}
                    strokeWidth={isTarget ? 2.5 : 1.4}
                    strokeDasharray={strokeDasharray}
                  />
                  <text
                    x={n.x}
                    y={n.y + 4}
                    textAnchor="middle"
                    fontSize="11"
                    fontWeight="600"
                    fill={NYIT_BLUE}
                  >
                    {n.id}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>
      )}

      <h3 className="mt-4 font-semibold text-sm" style={{ color: NYIT_BLUE }}>
        What does this unlock?
      </h3>
      <div className="text-sm">
        {shownDependents.length === 0 ? (
          <div className="text-gray-500">
            {dependents.length === 0
              ? "No downstream courses depend on this one."
              : `No downstream courses in ${program.program_id}. Switch to "All programs" to see ${dependents.length}.`}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-1">
            {shownDependents.map((cid) => (
              <div key={cid}>
                → <strong style={{ color: NYIT_BLUE }}>{cid}</strong>{" "}
                <span className="text-gray-600">{courseIndex[cid]?.title || ""}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
