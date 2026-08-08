"use client";

import type { SemesterPlan } from "@/lib/types";
import { NYIT_BLUE, NYIT_GOLD } from "@/lib/types";

export default function SemesterCard({
  plan,
  kind = "planned",
  editable = false,
  allTerms = [],
  courseTitles = {},
  onMove,
  onRemove,
}: {
  plan: SemesterPlan;
  kind?: "historical" | "current" | "planned";
  editable?: boolean;
  allTerms?: string[];
  courseTitles?: Record<string, { title: string; credits: number }>;
  onMove?: (course: string, fromTerm: string, toTerm: string) => void;
  onRemove?: (course: string, fromTerm: string) => void;
}) {
  const accent =
    kind === "historical" ? "#9ca3af" : kind === "current" ? "#f59e0b" : NYIT_GOLD;
  const bg = kind === "historical" ? "#f9fafb" : "white";
  const label = kind === "historical" ? "past" : kind === "current" ? "in progress" : "planned";
  const labelBg =
    kind === "historical" ? "#e5e7eb" : kind === "current" ? "#fef3c7" : NYIT_GOLD;
  const labelColor =
    kind === "historical" ? "#4b5563" : kind === "current" ? "#92400e" : NYIT_BLUE;

  return (
    <div
      className="border rounded-xl p-4 mb-3 shadow-sm"
      style={{
        borderColor: "#e5e7eb",
        borderLeft: `4px solid ${accent}`,
        background: bg,
      }}
    >
      <div className="flex items-baseline justify-between mb-2 flex-wrap gap-2">
        <span className="font-semibold text-lg" style={{ color: NYIT_BLUE }}>
          {plan.term}
          <span
            className="ml-2 text-xs px-2 py-0.5 rounded-full font-medium"
            style={{ background: labelBg, color: labelColor }}
          >
            {label}
          </span>
        </span>
        <span
          className="text-xs font-semibold px-3 py-1 rounded-full"
          style={{ background: NYIT_GOLD, color: NYIT_BLUE }}
        >
          {plan.total_credits.toFixed(0)} credits
        </span>
      </div>
      <div className="space-y-1">
        {plan.courses.map((cid) => {
          const c = courseTitles[cid];
          return (
            <div key={cid} className="flex items-center justify-between text-sm py-0.5">
              <div className="flex-1 min-w-0">
                <span className="font-semibold" style={{ color: NYIT_BLUE }}>
                  {cid}
                </span>
                {" · "}
                <span className="text-gray-700">
                  {c?.title || "(course details TBD)"}
                </span>
                <span className="text-gray-400 ml-1">
                  ({c?.credits || "?"} cr)
                </span>
              </div>
              {editable && (
                <div className="flex items-center gap-1 ml-2">
                  <select
                    value=""
                    onChange={(e) => {
                      if (e.target.value && onMove) {
                        onMove(cid, plan.term, e.target.value);
                      }
                      e.target.value = "";
                    }}
                    className="text-xs border border-gray-200 rounded px-1 py-0.5 text-gray-600 bg-white"
                    title="Move to a different semester"
                  >
                    <option value="">↔ move</option>
                    {allTerms
                      .filter((t) => t !== plan.term)
                      .map((t) => (
                        <option key={t} value={t}>
                          {t}
                        </option>
                      ))}
                  </select>
                  <button
                    onClick={() => onRemove && onRemove(cid, plan.term)}
                    className="text-xs px-1.5 py-0.5 rounded text-red-500 hover:bg-red-50"
                    title="Remove from plan"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {plan.rationale && (
        <div className="text-xs text-gray-500 italic mt-2">{plan.rationale}</div>
      )}
    </div>
  );
}
