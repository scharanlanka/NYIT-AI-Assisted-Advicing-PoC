"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { api } from "@/lib/api";
import type {
  Operation,
  PathwayResponse,
  PrefsOverride,
  Program,
  Student,
  AgentResponse,
} from "@/lib/types";
import { NYIT_BLUE, NYIT_GOLD } from "@/lib/types";
import Sidebar from "@/components/Sidebar";
import Overview from "@/components/Overview";
import Journey from "@/components/Journey";
import PrereqExplorer from "@/components/PrereqExplorer";
import Chat from "@/components/Chat";
import AdvisorSummary from "@/components/AdvisorSummary";

type TabId = "overview" | "journey" | "prereqs" | "chat" | "summary";

export default function Home() {
  const [students, setStudents] = useState<Student[]>([]);
  const [programs, setPrograms] = useState<Record<string, Program>>({});
  const [selectedStudentId, setSelectedStudentId] = useState<string>("");
  const [tab, setTab] = useState<TabId>("overview");
  const [prefsOverrides, setPrefsOverrides] = useState<Record<string, PrefsOverride>>({});
  const [pathwayOverrides, setPathwayOverrides] = useState<Record<string, Operation[]>>({});
  const [snapshot, setSnapshot] = useState<{
    studentId: string;
    label: string;
    plans: { term: string; courses: string[] }[];
  } | null>(null);
  const [pathwayData, setPathwayData] = useState<PathwayResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<{ llm_provider: string } | null>(null);

  // Initial data load
  useEffect(() => {
    Promise.all([api.listStudents(), api.listPrograms(), api.health()])
      .then(([sRes, pRes, h]) => {
        setStudents(sRes.students);
        const progMap: Record<string, Program> = {};
        pRes.programs.forEach((p) => {
          progMap[p.program_id] = p;
        });
        setPrograms(progMap);
        setHealth(h);
        if (sRes.students.length > 0) {
          setSelectedStudentId(sRes.students[0].student_id);
        }
      })
      .catch((e) => console.error("Failed to load initial data:", e));
  }, []);

  // Reload pathway whenever student or overrides change
  const reloadPathway = useCallback(
    async (previousPlans?: { term: string; courses: string[] }[]) => {
      if (!selectedStudentId) return;
      setLoading(true);
      try {
        const data = await api.pathwayWithOverrides(
          selectedStudentId,
          prefsOverrides[selectedStudentId],
          pathwayOverrides[selectedStudentId] || [],
          previousPlans
        );
        setPathwayData(data);
      } catch (e) {
        console.error("Failed to load pathway:", e);
      } finally {
        setLoading(false);
      }
    },
    [selectedStudentId, prefsOverrides, pathwayOverrides]
  );

  useEffect(() => {
    reloadPathway();
    // Reset snapshot when switching students
    setSnapshot((s) => (s && s.studentId === selectedStudentId ? s : null));
  }, [selectedStudentId, prefsOverrides, pathwayOverrides]);

  const takeSnapshot = (label: string) => {
    if (!pathwayData) return;
    setSnapshot({
      studentId: selectedStudentId,
      label,
      plans: pathwayData.pathway.semester_plans.map((p) => ({
        term: p.term,
        courses: [...p.courses],
      })),
    });
  };

  const applyOp = async (op: Operation) => {
    takeSnapshot("Manual edit");
    setPathwayOverrides((prev) => ({
      ...prev,
      [selectedStudentId]: [...(prev[selectedStudentId] || []), op],
    }));
  };

  const applyAiProposal = (proposal: AgentResponse) => {
    if (!proposal || !proposal.validated) return;
    const validOps = proposal.validated.filter((v) => v.ok).map((v) => v.op);
    if (validOps.length === 0) return;
    takeSnapshot(`AI change via ${proposal.agent}`);

    const PREF_TYPES = new Set([
      "change_concentration",
      "change_credits",
      "change_schedule",
      "change_interests",
    ]);
    const prefOps = validOps.filter((op) => PREF_TYPES.has(op.type));
    const pathOps = validOps.filter((op) => !PREF_TYPES.has(op.type));

    if (prefOps.length > 0) {
      setPrefsOverrides((prev) => {
        const cur = prev[selectedStudentId] || {};
        const updated: PrefsOverride = { ...cur };
        for (const op of prefOps) {
          if (op.type === "change_concentration") updated.concentration_choice = op.concentration;
          if (op.type === "change_credits") updated.max_credits_per_semester = op.value;
          if (op.type === "change_schedule") updated.preferred_schedule = op.value;
          if (op.type === "change_interests") updated.interests = op.value;
        }
        return { ...prev, [selectedStudentId]: updated };
      });
      // Concentration change invalidates course overrides
      if (prefOps.some((op) => op.type === "change_concentration")) {
        setPathwayOverrides((prev) => {
          const next = { ...prev };
          delete next[selectedStudentId];
          return next;
        });
      }
    }
    if (pathOps.length > 0) {
      setPathwayOverrides((prev) => ({
        ...prev,
        [selectedStudentId]: [...(prev[selectedStudentId] || []), ...pathOps],
      }));
    }
  };

  const resetOverrides = () => {
    setPathwayOverrides((prev) => {
      const next = { ...prev };
      delete next[selectedStudentId];
      return next;
    });
    setSnapshot(null);
  };

  const resetPrefsOverride = () => {
    setPrefsOverrides((prev) => {
      const next = { ...prev };
      delete next[selectedStudentId];
      return next;
    });
  };

  const setPrefOverride = (override: PrefsOverride) => {
    setPrefsOverrides((prev) => ({ ...prev, [selectedStudentId]: override }));
  };

  const selectedStudent = students.find((s) => s.student_id === selectedStudentId);
  const student = pathwayData?.student || selectedStudent;
  const program = pathwayData?.program || (student ? programs[student.program_id] : null);

  const currentOverrides = pathwayOverrides[selectedStudentId] || [];

  return (
    <div className="flex flex-col overflow-hidden" style={{ height: "100dvh" }}>
      {/* Gold accent bar */}
      <div className="shrink-0 h-1" style={{ background: NYIT_GOLD }} />

      {/* Header */}
      <header className="nyit-header px-4 md:px-6 py-3 shrink-0">
        <div className="flex items-center justify-between gap-3">
          {/* Logo + title */}
          <div className="flex items-center gap-3 min-w-0">
            <Image
              src="/NewYorkTechLogo.webp"
              alt="New York Tech Logo"
              height={50}
              width={50}
              className="object-contain rounded shrink-0"
              priority
            />
            <div className="h-9 w-px opacity-30 shrink-0" style={{ background: NYIT_GOLD }} />
            <div className="min-w-0">
              <h1 className="text-base md:text-lg font-semibold text-white m-0 leading-tight tracking-tight truncate">
                AI-Assisted Academic Advising
              </h1>
              <p className="text-xs m-0 mt-0.5 opacity-70 text-white hidden sm:block">
                College of Engineering & Computing Sciences
              </p>
            </div>
          </div>

          {/* Student selector — visible on everything below lg (mobile, tablet, iPad) */}
          <div className="lg:hidden flex items-center gap-2 shrink-0">
            {student && (
              <div
                className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0"
                style={{ background: "rgba(255,255,255,0.2)" }}
              >
                {student.name.split(" ").map((n: string) => n[0]).join("").slice(0, 2).toUpperCase()}
              </div>
            )}
            <select
              value={selectedStudentId}
              onChange={(e) => setSelectedStudentId(e.target.value)}
              className="text-sm rounded-lg px-3 py-1.5 font-medium cursor-pointer"
              style={{ background: "rgba(255,255,255,0.12)", color: "#fff", border: "1px solid rgba(255,255,255,0.25)" }}
            >
              {students.map((s) => (
                <option key={s.student_id} value={s.student_id} style={{ color: "#111", background: "#fff" }}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          <span
            className="text-xs px-2.5 py-1 rounded-full font-medium hidden lg:inline-block shrink-0"
            style={{ background: "rgba(255,184,0,0.15)", color: NYIT_GOLD, border: "1px solid rgba(255,184,0,0.3)" }}
          >
            Proof of Concept
          </span>
        </div>
      </header>

      {/* App body */}
      <div className="flex-1 overflow-hidden flex flex-row">

        {/* Full sidebar — only on lg+ (1024px+) */}
        <div className="hidden lg:flex lg:w-64 xl:w-72 shrink-0 flex-col overflow-y-auto border-r border-gray-200 bg-white">
          <Sidebar
            students={students}
            programs={programs}
            selectedId={selectedStudentId}
            onSelect={setSelectedStudentId}
            editCount={currentOverrides.length}
            hasPrefsOverride={!!prefsOverrides[selectedStudentId]}
            student={student}
            program={program}
          />
        </div>

        {/* Main content: always scrolls within this container */}
        <div className="flex-1 overflow-y-auto min-h-0" style={{ background: "#eef1f7" }}>
          <div className="p-4 max-w-5xl mx-auto">
            {/* Tabs */}
            <div className="bg-white rounded-t-xl border border-b-0 border-gray-200 flex overflow-x-auto shadow-sm">
              {(
                [
                  ["overview", "Overview"],
                  ["journey", "Academic Journey"],
                  ["prereqs", "Prerequisite Explorer"],
                  ["chat", "Chat"],
                  ["summary", "Advisor Summary"],
                ] as [TabId, string][]
              ).map(([id, label]) => (
                <button
                  key={id}
                  onClick={() => setTab(id)}
                  className={`px-4 md:px-5 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                    tab === id
                      ? ""
                      : "border-transparent text-gray-500 hover:text-gray-700 hover:bg-gray-50"
                  }`}
                  style={tab === id ? { borderBottomColor: NYIT_GOLD, color: NYIT_BLUE } : {}}
                >
                  {label}
                </button>
              ))}
            </div>

            <div className="bg-white rounded-b-xl border border-gray-200 p-4 md:p-6 shadow-sm">
              {!student || !program || !pathwayData ? (
                <div className="text-center py-16 text-gray-500">
                  {loading ? "Loading..." : "Select a student"}
                </div>
              ) : (
                <>
                  {tab === "overview" && (
                    <Overview
                      student={student}
                      program={program}
                      pathwayData={pathwayData}
                      prefsOverride={prefsOverrides[selectedStudentId]}
                      onSavePrefs={setPrefOverride}
                      onResetPrefs={resetPrefsOverride}
                    />
                  )}
                  {tab === "journey" && (
                    <Journey
                      student={student}
                      program={program}
                      pathwayData={pathwayData}
                      snapshot={snapshot}
                      onDismissSnapshot={() => setSnapshot(null)}
                      applyOp={applyOp}
                      applyAiProposal={applyAiProposal}
                      resetOverrides={resetOverrides}
                      overrides={currentOverrides}
                      studentId={selectedStudentId}
                      prefsOverride={prefsOverrides[selectedStudentId]}
                    />
                  )}
                  {tab === "prereqs" && (
                    <PrereqExplorer
                      student={student}
                      program={program}
                    />
                  )}
                  {tab === "chat" && (
                    <Chat
                      student={student}
                      program={program}
                      studentId={selectedStudentId}
                      prefsOverride={prefsOverrides[selectedStudentId]}
                      overrides={currentOverrides}
                    />
                  )}
                  {tab === "summary" && (
                    <AdvisorSummary
                      student={student}
                      studentId={selectedStudentId}
                      prefsOverride={prefsOverrides[selectedStudentId]}
                      overrides={currentOverrides}
                    />
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Footer */}
      <footer className="shrink-0 border-t border-gray-200 bg-white">
        <div className="flex items-center justify-between px-4 py-2.5">
          <span className="text-xs text-gray-400">
            Demo · Data:{" "}
            <a href="https://catalog.nyit.edu" style={{ color: NYIT_BLUE }} className="hover:underline">
              catalog.nyit.edu
            </a>{" "}
            (2026–2027) · Synthetic student profiles
          </span>
          <span className="text-xs text-gray-300 hidden md:inline">
            Built for NYIT · AI Enablement & Solutions
          </span>
        </div>
      </footer>
    </div>
  );
}
