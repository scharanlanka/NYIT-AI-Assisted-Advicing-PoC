"use client";

import { useState } from "react";
import type {
  PathwayResponse,
  PrefsOverride,
  Program,
  Student,
} from "@/lib/types";
import { NYIT_BLUE, NYIT_GOLD } from "@/lib/types";

function StatBox({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="nyit-card p-4 text-center" style={{ borderTop: "3px solid #FFB800" }}>
      <div className="text-2xl font-bold tracking-tight" style={{ color: NYIT_BLUE }}>
        {value}
      </div>
      <div className="text-xs text-gray-400 mt-1 font-medium uppercase tracking-wide">{label}</div>
    </div>
  );
}

function PrefsEditor({
  student,
  program,
  onSave,
  onCancel,
}: {
  student: Student;
  program: Program;
  onSave: (o: PrefsOverride) => void;
  onCancel: () => void;
}) {
  const [interests, setInterests] = useState(student.preferences.interests.join(", "));
  const [maxCredits, setMaxCredits] = useState(student.preferences.max_credits_per_semester);
  const [schedule, setSchedule] = useState(student.preferences.preferred_schedule);
  const [concentration, setConcentration] = useState(
    student.preferences.concentration_choice || ""
  );

  return (
    <div className="text-sm space-y-3 mb-4 p-3 bg-gray-50 rounded border border-gray-200">
      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1">
          Interests (comma-separated)
        </label>
        <input
          type="text"
          value={interests}
          onChange={(e) => setInterests(e.target.value)}
          className="w-full text-sm border border-gray-300 rounded px-2 py-1"
        />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Credit cap: <span className="text-gray-500">{maxCredits}</span>
          </label>
          <input
            type="range"
            min="6"
            max="18"
            value={maxCredits}
            onChange={(e) => setMaxCredits(parseInt(e.target.value))}
            className="w-full"
          />
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Schedule preference
          </label>
          <select
            value={schedule}
            onChange={(e) => setSchedule(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1"
          >
            <option value="morning">Morning</option>
            <option value="afternoon">Afternoon</option>
            <option value="evening">Evening</option>
            <option value="no_preference">No preference</option>
          </select>
        </div>
      </div>
      {program.concentrations && program.concentrations.length > 0 && (
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1">
            Concentration
          </label>
          <select
            value={concentration}
            onChange={(e) => setConcentration(e.target.value)}
            className="w-full text-sm border border-gray-300 rounded px-2 py-1"
          >
            <option value="">Not selected</option>
            {program.concentrations.map((c) => (
              <option key={c.name} value={c.name}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      )}
      <div className="flex gap-2 pt-1">
        <button
          onClick={() =>
            onSave({
              interests: interests
                .split(",")
                .map((s) => s.trim())
                .filter(Boolean),
              max_credits_per_semester: maxCredits,
              preferred_schedule: schedule,
              concentration_choice: concentration || null,
            })
          }
          className="px-4 py-1.5 rounded text-white text-xs font-medium"
          style={{ background: NYIT_BLUE }}
        >
          Save & regenerate pathway
        </button>
        <button
          onClick={onCancel}
          className="px-4 py-1.5 rounded text-xs font-medium border border-gray-300"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default function Overview({
  student,
  program,
  pathwayData,
  prefsOverride,
  onSavePrefs,
  onResetPrefs,
}: {
  student: Student;
  program: Program;
  pathwayData: PathwayResponse;
  prefsOverride: PrefsOverride | undefined;
  onSavePrefs: (o: PrefsOverride) => void;
  onResetPrefs: () => void;
}) {
  const [editing, setEditing] = useState(false);

  const completed = student.completed_courses;
  const current = student.current_courses;
  const totalTarget = program.total_credits;
  // Effective student to display (base + override applied on the server, so use pathwayData.student)
  const s = pathwayData.student;
  const p = pathwayData.program;

  return (
    <div>
      <h2 className="text-xl font-semibold mb-4" style={{ color: NYIT_BLUE }}>
        {s.name}
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <StatBox
          label="Completed"
          value={`${pathwayData.completion.total_scheduled_credits.toFixed(0)} cr`}
        />
        <StatBox label="Target" value={`${totalTarget} cr`} />
        <StatBox
          label="Blocks OK"
          value={
            pathwayData.completion.block_analysis.length -
            pathwayData.completion.incomplete_blocks.length
          }
        />
        <StatBox
          label="Progress"
          value={`${pathwayData.completion.percent_complete}%`}
        />
      </div>
      <div className="h-2 bg-gray-100 rounded-full mb-4 overflow-hidden border border-gray-200">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${pathwayData.completion.percent_complete}%`,
            background: `linear-gradient(90deg, #002d72, #FFB800)`,
          }}
        />
      </div>

      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm m-0" style={{ color: NYIT_BLUE }}>
          Preferences
        </h3>
        <div className="flex items-center gap-2">
          {prefsOverride && (
            <button
              onClick={onResetPrefs}
              className="text-xs text-gray-500 hover:text-gray-700 underline"
            >
              Reset to defaults
            </button>
          )}
          <button
            onClick={() => setEditing(!editing)}
            className="text-xs px-2 py-1 rounded"
            style={{ background: NYIT_GOLD, color: NYIT_BLUE, fontWeight: 600 }}
          >
            {editing ? "Cancel" : "✏️ Edit"}
          </button>
        </div>
      </div>

      {!editing ? (
        <div className="text-sm space-y-1 mb-4">
          <div>
            <strong>Interests:</strong>{" "}
            {s.preferences.interests.join(", ") || "—"}
          </div>
          <div>
            <strong>Credit cap/term:</strong>{" "}
            {s.preferences.max_credits_per_semester}
          </div>
          <div>
            <strong>Schedule:</strong> {s.preferences.preferred_schedule}
          </div>
          <div>
            <strong>Concentration:</strong>{" "}
            {s.preferences.concentration_choice || "not selected"}
          </div>
          {s.preferences.notes && (
            <div className="text-gray-600 italic">Notes: {s.preferences.notes}</div>
          )}
          {prefsOverride && (
            <div className="text-xs mt-1 text-amber-700">
              ✏️ Modified this session. Pathway reflects updated preferences.
            </div>
          )}
        </div>
      ) : (
        <PrefsEditor
          student={s}
          program={p}
          onSave={(o) => {
            onSavePrefs(o);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
        />
      )}

      <h3 className="font-semibold mb-2 text-sm" style={{ color: NYIT_BLUE }}>
        Requirement blocks
      </h3>
      <div className="space-y-1">
        {pathwayData.requirement_blocks.map((b, i) => (
          <details key={i} className="text-sm bg-gray-50 rounded-lg p-2 border border-gray-100">
            <summary className="cursor-pointer">
              <span className="mr-2">{b.fully_satisfied ? "✅" : "🔲"}</span>
              <span className="font-medium">{b.block_name}</span>
              <span className="text-gray-500 ml-2">
                {b.completed_credits.toFixed(0)}/{b.total_required_credits.toFixed(0)} cr
              </span>
            </summary>
            <div className="mt-2 pl-6 text-xs">
              {b.completed_courses.length > 0 && (
                <div>
                  <strong>Covered:</strong> {b.completed_courses.join(", ")}
                </div>
              )}
              {!b.fully_satisfied && b.remaining_options.length > 0 && (
                <div className="mt-1">
                  <strong>Need {b.remaining_needed} more:</strong>{" "}
                  {b.remaining_options.slice(0, 12).join(", ")}
                  {b.remaining_options.length > 12 && "..."}
                </div>
              )}
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
