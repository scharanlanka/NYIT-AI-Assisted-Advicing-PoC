"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type {
  AgentResponse,
  Operation,
  PathwayResponse,
  PrefsOverride,
  Program,
  Student,
} from "@/lib/types";
import { NYIT_BLUE, NYIT_GOLD } from "@/lib/types";
import SemesterCard from "./SemesterCard";

function nextSemester(term: string): string {
  const [season, year] = term.split(" ");
  const y = parseInt(year);
  if (season === "Fall") return `Spring ${y + 1}`;
  if (season === "Spring") return `Fall ${y}`;
  return `Fall ${y + 1}`;
}

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3 text-center">
      <div className="text-xl font-bold" style={{ color: NYIT_BLUE }}>
        {value}
      </div>
      <div className="text-xs text-gray-500 mt-1">{label}</div>
    </div>
  );
}

export default function Journey({
  student,
  program,
  pathwayData,
  snapshot,
  onDismissSnapshot,
  applyOp,
  applyAiProposal,
  resetOverrides,
  overrides,
  studentId,
  prefsOverride,
}: {
  student: Student;
  program: Program;
  pathwayData: PathwayResponse;
  snapshot: { studentId: string; label: string; plans: { term: string; courses: string[] }[] } | null;
  onDismissSnapshot: () => void;
  applyOp: (op: Operation) => void;
  applyAiProposal: (proposal: AgentResponse) => void;
  resetOverrides: () => void;
  overrides: Operation[];
  studentId: string;
  prefsOverride: PrefsOverride | undefined;
}) {
  const [aiEditRequest, setAiEditRequest] = useState("");
  const [aiProposal, setAiProposal] = useState<AgentResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [explanation, setExplanation] = useState("");
  const [explanationLoading, setExplanationLoading] = useState(false);
  const [showCompletionDetails, setShowCompletionDetails] = useState(false);
  const [courseIndex, setCourseIndex] = useState<Record<string, { title: string; credits: number }>>({});

  // Load course titles for all mentioned courses
  useEffect(() => {
    const allCids = new Set<string>();
    pathwayData.pathway.semester_plans.forEach((p) =>
      p.courses.forEach((c) => allCids.add(c))
    );
    pathwayData.history.forEach((p) => p.courses.forEach((c) => allCids.add(c)));
    if (pathwayData.current_term_plan) {
      pathwayData.current_term_plan.courses.forEach((c) => allCids.add(c));
    }
    const missing = Array.from(allCids).filter((c) => !courseIndex[c]);
    if (missing.length === 0) return;
    Promise.all(missing.map((c) => api.getCourse(c).catch(() => null))).then((results) => {
      const updates: Record<string, { title: string; credits: number }> = {};
      results.forEach((r, i) => {
        if (r) updates[missing[i]] = { title: r.title, credits: r.credits };
      });
      setCourseIndex((prev) => ({ ...prev, ...updates }));
    });
  }, [pathwayData]);

  // Reset AI editor state when student changes
  useEffect(() => {
    setAiEditRequest("");
    setAiProposal(null);
    setExplanation("");
    setShowCompletionDetails(false);
  }, [studentId]);

  const submitAiEdit = async () => {
    if (!aiEditRequest.trim() || aiLoading) return;
    setAiLoading(true);
    setAiProposal(null);
    try {
      const result = await api.orchestrate(
        studentId,
        aiEditRequest,
        prefsOverride,
        overrides
      );
      setAiProposal(result);
    } catch (e) {
      console.error("AI edit failed:", e);
    } finally {
      setAiLoading(false);
    }
  };

  const confirmAiProposal = () => {
    if (!aiProposal) return;
    applyAiProposal(aiProposal);
    setAiProposal(null);
    setAiEditRequest("");
  };

  const askExplanation = async () => {
    setExplanationLoading(true);
    try {
      const result = await api.explain(studentId, prefsOverride, overrides);
      setExplanation(result.text);
    } finally {
      setExplanationLoading(false);
    }
  };

  // Compute diff locally from snapshot
  const recentDiff = (() => {
    if (!snapshot || snapshot.studentId !== studentId) return null;
    const oldMap: Record<string, string> = {};
    snapshot.plans.forEach((p) => p.courses.forEach((c) => (oldMap[c] = p.term)));
    const newMap: Record<string, string> = {};
    pathwayData.pathway.semester_plans.forEach((p) =>
      p.courses.forEach((c) => (newMap[c] = p.term))
    );
    const oldSet = new Set(Object.keys(oldMap));
    const newSet = new Set(Object.keys(newMap));
    const added: { course: string; term: string }[] = [];
    const removed: { course: string; term: string }[] = [];
    const moved: { course: string; from: string; to: string }[] = [];
    let unchanged = 0;
    for (const c of Array.from(newSet)) {
      if (!oldSet.has(c)) added.push({ course: c, term: newMap[c] });
      else if (oldMap[c] !== newMap[c])
        moved.push({ course: c, from: oldMap[c], to: newMap[c] });
      else unchanged++;
    }
    for (const c of Array.from(oldSet)) {
      if (!newSet.has(c)) removed.push({ course: c, term: oldMap[c] });
    }
    if (added.length + removed.length + moved.length === 0) return null;
    return { added, removed, moved, unchanged, label: snapshot.label };
  })();

  const completion = pathwayData.completion;
  const isGood = completion.is_fully_on_track;
  const isMedium = !isGood && completion.percent_complete >= 80;
  const bg = isGood ? "#f0fdf4" : isMedium ? "#fffbeb" : "#fef2f2";
  const border = isGood ? "#86efac" : isMedium ? "#fcd34d" : "#fca5a5";
  const barColor = isGood ? "#16a34a" : isMedium ? "#f59e0b" : "#dc2626";
  const textColor = isGood ? "#166534" : isMedium ? "#92400e" : "#991b1b";

  const existingTerms = pathwayData.pathway.semester_plans.map((p) => p.term);
  const lastTerm =
    existingTerms[existingTerms.length - 1] || student.current_semester;
  const extraTerms: string[] = [];
  let t = lastTerm;
  for (let i = 0; i < 4; i++) {
    t = nextSemester(t);
    extraTerms.push(t);
  }
  const allTerms = [...existingTerms, ...extraTerms];

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1" style={{ color: NYIT_BLUE }}>
        Academic Journey
      </h2>
      <p className="text-xs text-gray-500 mb-4">
        Full timeline: past terms, current enrollment, and the deterministic plan
        for future semesters. Manual edits and AI-assisted modifications are
        guarded by prereq, program-scope, and semester-offering rules.
      </p>

      {/* Degree completion strip */}
      <div className="mb-4 p-3 rounded-lg border" style={{ background: bg, borderColor: border }}>
        <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-sm font-semibold" style={{ color: NYIT_BLUE }}>
              Degree Completion
            </span>
            <span className="text-lg font-bold" style={{ color: NYIT_BLUE }}>
              {completion.total_scheduled_credits.toFixed(0)} / {completion.total_target} cr
            </span>
            <span className="text-sm font-medium" style={{ color: textColor }}>
              {completion.percent_complete}%
            </span>
          </div>
          <button
            onClick={() => setShowCompletionDetails(!showCompletionDetails)}
            className="text-xs text-gray-600 hover:text-gray-900 underline"
          >
            {showCompletionDetails ? "Hide details" : "Show details"}
          </button>
        </div>
        <div className="h-2 bg-white rounded-full overflow-hidden mb-2">
          <div
            className="h-full rounded-full transition-all"
            style={{ width: `${completion.percent_complete}%`, background: barColor }}
          />
        </div>
        <div className="text-xs" style={{ color: textColor }}>
          {isGood ? (
            <>✅ All {completion.block_analysis.length} requirement blocks on track</>
          ) : (
            <>
              ⚠ {completion.incomplete_blocks.length} block
              {completion.incomplete_blocks.length !== 1 ? "s" : ""} incomplete, {completion.total_gap.toFixed(0)} cr short of graduation
            </>
          )}
        </div>
        {showCompletionDetails && completion.incomplete_blocks.length > 0 && (
          <div className="mt-3 pt-3 border-t space-y-1.5" style={{ borderColor: "rgba(0,0,0,0.08)" }}>
            <div className="text-xs font-semibold" style={{ color: textColor }}>
              Blocks not yet fulfilled ({completion.incomplete_blocks.length})
            </div>
            {completion.incomplete_blocks.map((b, i) => (
              <div key={i} className="text-xs bg-white/60 rounded p-2">
                <div>
                  <span className="font-semibold">⚠ {b.block_name}</span>
                  <span className="text-gray-600 ml-2">
                    {b.covered_credits.toFixed(0)}/{b.target} cr
                  </span>
                </div>
                {b.is_open && (
                  <div className="text-gray-500 italic mt-0.5">
                    Open-ended block: advisor selects qualifying courses. {b.notes}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* AI editor */}
      <div className="mb-4 p-3 rounded border" style={{ background: "#eff6ff", borderColor: "#bfdbfe" }}>
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-semibold" style={{ color: NYIT_BLUE }}>
            💬 AI plan editor
          </span>
          <span className="text-xs text-gray-500">
            Describe changes in plain English. The AI system routes to the right specialist, guardrails validate before you approve.
          </span>
        </div>
        <textarea
          value={aiEditRequest}
          onChange={(e) => setAiEditRequest(e.target.value)}
          placeholder={'e.g. "Move CSCI 465 to Fall 2027" or "switch to cybersecurity concentration"'}
          rows={2}
          className="w-full text-sm border border-gray-300 rounded p-2 mb-2 resize-none"
        />
        <div className="flex gap-2 items-center flex-wrap">
          <button
            onClick={submitAiEdit}
            disabled={aiLoading || !aiEditRequest.trim()}
            className="text-xs px-3 py-1.5 rounded text-white font-medium disabled:opacity-50"
            style={{ background: NYIT_BLUE }}
          >
            {aiLoading ? "Thinking..." : "🤖 Ask AI to propose changes"}
          </button>
          {overrides.length > 0 && (
            <button
              onClick={resetOverrides}
              className="text-xs px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-50"
            >
              ↺ Reset all edits ({overrides.length})
            </button>
          )}
        </div>

        {aiProposal && (
          <div className="mt-3 p-3 bg-white rounded border border-gray-200">
            {aiProposal.routing && (
              <div className="text-xs mb-2 flex items-center gap-2 flex-wrap">
                <span
                  className="px-2 py-0.5 rounded-full font-medium"
                  style={{ background: "#e5e7eb", color: "#374151" }}
                >
                  🔀 Router
                </span>
                <span className="text-gray-500">
                  {aiProposal.routing.intent} ({Math.round((aiProposal.routing.confidence || 0) * 100)}%)
                </span>
                <span className="text-gray-400">→</span>
                <span
                  className="px-2 py-0.5 rounded-full font-medium"
                  style={{ background: NYIT_GOLD, color: NYIT_BLUE }}
                >
                  🤖 {aiProposal.agent}
                </span>
              </div>
            )}
            {aiProposal.is_answer ? (
              <>
                <div className="text-xs font-semibold mb-1" style={{ color: NYIT_BLUE }}>
                  Answer
                </div>
                <div className="text-sm whitespace-pre-wrap">{aiProposal.reasoning}</div>
                <button
                  onClick={() => setAiProposal(null)}
                  className="mt-2 text-xs px-3 py-1 rounded border border-gray-300"
                >
                  Close
                </button>
              </>
            ) : (
              <>
                <div className="text-xs font-semibold mb-2" style={{ color: NYIT_BLUE }}>
                  Proposed changes
                </div>
                {aiProposal.reasoning && (
                  <div className="text-xs text-gray-600 italic mb-2 max-h-24 overflow-y-auto">
                    {aiProposal.reasoning}
                  </div>
                )}
                {aiProposal.validated && aiProposal.validated.length === 0 ? (
                  <div className="text-xs text-gray-500">No operations proposed.</div>
                ) : (
                  <ul className="space-y-1 mb-2">
                    {aiProposal.validated.map((v, i) => (
                      <li key={i} className="text-xs flex items-start gap-1">
                        <span className={v.ok ? "text-green-600" : "text-red-500"}>
                          {v.ok ? "✓" : "✕"}
                        </span>
                        <span>
                          {v.description}
                          {!v.ok && (
                            <span className="text-red-500 ml-1 italic">
                              (rejected: {v.error})
                            </span>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                <div className="flex gap-2 pt-1">
                  {aiProposal.validated.some((v) => v.ok) && (
                    <button
                      onClick={confirmAiProposal}
                      className="text-xs px-3 py-1 rounded text-white font-medium"
                      style={{ background: NYIT_BLUE }}
                    >
                      Apply valid changes
                    </button>
                  )}
                  <button
                    onClick={() => setAiProposal(null)}
                    className="text-xs px-3 py-1 rounded border border-gray-300"
                  >
                    Discard
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Diff banner */}
      {recentDiff && (
        <div
          className="mb-4 p-3 rounded border"
          style={{ background: "#f0fdf4", borderColor: "#86efac" }}
        >
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-semibold flex items-center gap-2" style={{ color: "#166534" }}>
              ✨ Plan updated: what changed
              <span className="text-xs font-normal text-gray-500">({recentDiff.label})</span>
            </div>
            <button
              onClick={onDismissSnapshot}
              className="text-xs text-gray-500 hover:text-gray-700"
            >
              Dismiss
            </button>
          </div>
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div>
              <div className="font-semibold mb-1" style={{ color: "#166534" }}>
                Added ({recentDiff.added.length})
              </div>
              {recentDiff.added.length === 0 ? (
                <div className="text-gray-400">—</div>
              ) : (
                recentDiff.added.map((a, i) => (
                  <div key={i}>
                    <strong>{a.course}</strong> <span className="text-gray-500">→ {a.term}</span>
                  </div>
                ))
              )}
            </div>
            <div>
              <div className="font-semibold mb-1" style={{ color: "#b91c1c" }}>
                Removed ({recentDiff.removed.length})
              </div>
              {recentDiff.removed.length === 0 ? (
                <div className="text-gray-400">—</div>
              ) : (
                recentDiff.removed.map((r, i) => (
                  <div key={i}>
                    <strong>{r.course}</strong> <span className="text-gray-500">was in {r.term}</span>
                  </div>
                ))
              )}
            </div>
            <div>
              <div className="font-semibold mb-1" style={{ color: "#92400e" }}>
                Moved ({recentDiff.moved.length})
              </div>
              {recentDiff.moved.length === 0 ? (
                <div className="text-gray-400">—</div>
              ) : (
                recentDiff.moved.map((m, i) => (
                  <div key={i}>
                    <strong>{m.course}</strong>{" "}
                    <span className="text-gray-500">
                      {m.from} → {m.to}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
          {recentDiff.unchanged > 0 && (
            <div className="text-xs text-gray-500 mt-2 pt-2 border-t border-green-200">
              {recentDiff.unchanged} course{recentDiff.unchanged === 1 ? "" : "s"} unchanged
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mb-4">
        <StatBox label="Past terms" value={pathwayData.history.length} />
        <StatBox label="Current term" value={pathwayData.current_term_plan ? 1 : 0} />
        <StatBox label="Planned" value={pathwayData.pathway.semester_plans.length} />
        <StatBox label="Edits" value={overrides.length} />
      </div>

      {pathwayData.pathway.warnings.map((w, i) => (
        <div
          key={i}
          className="text-xs p-2 mb-2 rounded"
          style={{ background: "#fff3cd", color: "#856404" }}
        >
          ⚠ {w}
        </div>
      ))}

      {pathwayData.history.length > 0 && (
        <>
          <h3 className="text-sm font-semibold mt-2 mb-2 text-gray-500 uppercase tracking-wide">
            Past terms{" "}
            <span className="text-xs font-normal normal-case text-gray-400">
              (estimated from completed courses)
            </span>
          </h3>
          {pathwayData.history.map((p, i) => (
            <SemesterCard key={"h" + i} plan={p} kind="historical" courseTitles={courseIndex} />
          ))}
        </>
      )}

      {pathwayData.current_term_plan && (
        <>
          <h3
            className="text-sm font-semibold mt-4 mb-2 uppercase tracking-wide"
            style={{ color: "#92400e" }}
          >
            Current term
          </h3>
          <SemesterCard plan={pathwayData.current_term_plan} kind="current" courseTitles={courseIndex} />
        </>
      )}

      {pathwayData.pathway.semester_plans.length > 0 && (
        <>
          <h3
            className="text-sm font-semibold mt-4 mb-2 uppercase tracking-wide flex items-center gap-2"
            style={{ color: NYIT_BLUE }}
          >
            Recommended plan
            <span className="text-xs font-normal normal-case text-gray-500">
              (hover a course to edit)
            </span>
          </h3>
          {pathwayData.pathway.semester_plans.map((p, i) => (
            <SemesterCard
              key={"p" + i}
              plan={p}
              kind="planned"
              editable
              allTerms={allTerms}
              courseTitles={courseIndex}
              onMove={(course, from_term, to_term) =>
                applyOp({ type: "move", course, from_term, to_term })
              }
              onRemove={(course, from_term) =>
                applyOp({ type: "remove", course, from_term })
              }
            />
          ))}
        </>
      )}

      <button
        onClick={askExplanation}
        disabled={explanationLoading}
        className="mt-4 px-4 py-2 rounded text-white text-sm font-medium disabled:opacity-50"
        style={{ background: NYIT_BLUE }}
      >
        {explanationLoading ? "Thinking..." : "🤖 Ask AI why this plan"}
      </button>
      {explanation && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded text-sm whitespace-pre-wrap">
          {explanation}
        </div>
      )}
    </div>
  );
}
