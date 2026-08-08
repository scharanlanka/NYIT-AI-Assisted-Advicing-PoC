"use client";

import type { Program, Student } from "@/lib/types";
import { NYIT_BLUE } from "@/lib/types";

function getInitials(name: string) {
  return name.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between items-start gap-2 py-1.5 border-b border-gray-50 last:border-0">
      <span className="text-gray-400 text-xs shrink-0">{label}</span>
      <span className="text-gray-700 text-xs font-medium text-right leading-snug">{value}</span>
    </div>
  );
}

export default function Sidebar({
  students,
  programs,
  selectedId,
  onSelect,
  editCount,
  hasPrefsOverride,
  student,
  program,
}: {
  students: Student[];
  programs: Record<string, Program>;
  selectedId: string;
  onSelect: (id: string) => void;
  editCount: number;
  hasPrefsOverride: boolean;
  student: Student | undefined;
  program: Program | null;
}) {
  return (
    <div className="flex flex-col gap-4 p-4 h-full">
      {/* Session selector */}
      <div>
        <label className="text-xs font-semibold text-gray-400 uppercase tracking-wider block mb-1.5">
          Advising Session
        </label>
        <select
          value={selectedId}
          onChange={(e) => onSelect(e.target.value)}
          className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 bg-gray-50 text-gray-800 cursor-pointer"
        >
          {students.map((s) => (
            <option key={s.student_id} value={s.student_id}>
              {s.name}
            </option>
          ))}
        </select>
      </div>

      {/* Student profile */}
      {student && program && (
        <>
          <div className="flex flex-col items-center text-center py-3 border-t border-gray-100">
            <div
              className="w-14 h-14 rounded-full flex items-center justify-center text-lg font-bold text-white mb-3 shadow-sm"
              style={{ background: NYIT_BLUE }}
            >
              {getInitials(student.name)}
            </div>
            <div className="text-sm font-semibold text-gray-800 leading-tight">
              {student.name}
            </div>
            <div className="text-xs text-gray-400 mt-0.5">{student.student_id}</div>
            <span
              className="mt-2.5 text-xs px-2.5 py-0.5 rounded-full font-semibold"
              style={{ background: "rgba(0,45,114,0.08)", color: NYIT_BLUE }}
            >
              {student.program_id}
            </span>
          </div>

          <div className="border-t border-gray-100 pt-1">
            <Row label="Program" value={program.name} />
            <Row label="Current term" value={student.current_semester} />
            <Row label="Target grad" value={student.target_graduation} />
            <Row label="GPA" value={student.gpa?.toString() ?? "N/A"} />
            {student.preferences?.concentration_choice && (
              <Row label="Concentration" value={student.preferences.concentration_choice} />
            )}
          </div>
        </>
      )}

      {/* Session status */}
      <div className="mt-auto pt-2 border-t border-gray-100">
        {editCount > 0 || hasPrefsOverride ? (
          <div
            className="text-xs rounded-lg px-3 py-2 font-medium"
            style={{ background: "#fffbeb", color: "#92400e", border: "1px solid #fde68a" }}
          >
            ✏️{" "}
            {hasPrefsOverride && "Prefs modified"}
            {hasPrefsOverride && editCount > 0 && " · "}
            {editCount > 0 && `${editCount} plan edit${editCount !== 1 ? "s" : ""}`}
          </div>
        ) : (
          <div className="text-xs text-gray-400 text-center">
            {students.length} students · {Object.keys(programs).length} programs
          </div>
        )}
      </div>
    </div>
  );
}
