"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type { Operation, PrefsOverride, Student } from "@/lib/types";
import { NYIT_BLUE } from "@/lib/types";

export default function AdvisorSummary({
  student,
  studentId,
  prefsOverride,
  overrides,
}: {
  student: Student;
  studentId: string;
  prefsOverride: PrefsOverride | undefined;
  overrides: Operation[];
}) {
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);

  const generate = async () => {
    setLoading(true);
    try {
      const result = await api.advisorSummary(studentId, prefsOverride, overrides);
      setSummary(result.text);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1" style={{ color: NYIT_BLUE }}>
        Advisor Summary Memo
      </h2>
      <p className="text-xs text-gray-500 mb-4">
        Printable memo combining the deterministic plan with LLM-drafted rationale.
      </p>
      <button
        onClick={generate}
        disabled={loading}
        className="px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50 transition-opacity mb-4"
        style={{ background: NYIT_BLUE }}
      >
        {loading ? "Drafting memo..." : "📝 Generate Advisor Summary"}
      </button>
      {summary && (
        <div className="nyit-card p-5 h-96 overflow-y-auto">
          <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
            {summary}
          </pre>
        </div>
      )}
    </div>
  );
}
