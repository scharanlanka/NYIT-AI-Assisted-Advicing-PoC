import type {
  Course,
  Operation,
  PathwayResponse,
  PrefsOverride,
  Program,
  Student,
  StudentPreferences,
  AgentResponse,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

const DEFAULT_PREFERENCES: StudentPreferences = {
  interests: [],
  max_credits_per_semester: 12,
  min_credits_per_semester: 0,
  preferred_schedule: "no_preference",
  concentration_choice: null,
  notes: "",
};

function normalizeStudent(student: Student): Student {
  return {
    ...student,
    completed_courses: Array.isArray(student.completed_courses)
      ? student.completed_courses
      : [],
    current_courses: Array.isArray(student.current_courses)
      ? student.current_courses
      : [],
    current_semester:
      typeof student.current_semester === "string" ? student.current_semester : "",
    target_graduation:
      typeof student.target_graduation === "string" ? student.target_graduation : "",
    name: typeof student.name === "string" ? student.name : "Unknown Student",
    program_id: typeof student.program_id === "string" ? student.program_id : "",
    catalog_year: typeof student.catalog_year === "string" ? student.catalog_year : "",
    gpa: typeof student.gpa === "number" ? student.gpa : null,
    preferences: {
      ...DEFAULT_PREFERENCES,
      ...(student.preferences || {}),
      interests: Array.isArray(student.preferences?.interests)
        ? student.preferences.interests
        : DEFAULT_PREFERENCES.interests,
    },
  };
}

function normalizePathwayResponse(response: PathwayResponse): PathwayResponse {
  return {
    ...response,
    student: normalizeStudent(response.student),
  };
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${API_URL}${path}`);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

async function post<T>(path: string, body: any): Promise<T> {
  const r = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export const api = {
  health: () => get<{ status: string; llm_provider: string; programs: number; courses: number; students: number }>("/health"),

  listPrograms: () => get<{ programs: Program[] }>("/programs"),
  getProgram: (id: string) => get<Program>(`/programs/${id}`),
  getProgramUniverse: (id: string) =>
    get<{ program_id: string; count: number; courses: string[] }>(
      `/programs/${id}/universe`
    ),

  listStudents: async () => {
    const data = await get<{ students: Student[] }>("/students");
    return { students: data.students.map(normalizeStudent) };
  },
  getStudent: async (id: string) => normalizeStudent(await get<Student>(`/students/${id}`)),

  listCourses: () => get<{ courses: Course[] }>("/courses"),
  getCourse: (id: string) => get<Course>(`/courses/${encodeURIComponent(id)}`),
  getPrereqChain: (id: string) =>
    get<{
      target: string;
      nodes: string[];
      edges: { source: string; target: string }[];
      prereq_groups_by_course: Record<string, string[][]>;
    }>(`/courses/${encodeURIComponent(id)}/prereq-chain`),
  getDependents: (id: string) =>
    get<{ course_id: string; direct_dependents: string[] }>(
      `/courses/${encodeURIComponent(id)}/dependents`
    ),

  pathwayWithOverrides: (
    student_id: string,
    prefs_override?: PrefsOverride,
    pathway_overrides: Operation[] = [],
    previous_plans?: { term: string; courses: string[] }[]
  ) =>
    post<PathwayResponse>("/pathway/with-overrides", {
      student_id,
      prefs_override,
      pathway_overrides,
      previous_plans,
    }).then(normalizePathwayResponse),

  validateOperation: (
    student_id: string,
    operation: Operation,
    prefs_override?: PrefsOverride,
    pathway_overrides: Operation[] = []
  ) =>
    post<{ ok: boolean; error?: string; description: string }>(
      "/pathway/validate-operation",
      { student_id, operation, prefs_override, pathway_overrides }
    ),

  orchestrate: (
    student_id: string,
    query: string,
    prefs_override?: PrefsOverride,
    pathway_overrides: Operation[] = []
  ) =>
    post<AgentResponse>("/agents/orchestrate", {
      student_id,
      query,
      prefs_override,
      pathway_overrides,
    }),

  explain: (student_id: string, prefs_override?: PrefsOverride, pathway_overrides: Operation[] = []) =>
    post<{ text: string; provider: string; is_template: boolean }>(
      "/agents/explain",
      { student_id, prefs_override, pathway_overrides }
    ),

  advisorSummary: (student_id: string, prefs_override?: PrefsOverride, pathway_overrides: Operation[] = []) =>
    post<{ text: string; provider: string; is_template: boolean }>(
      "/agents/advisor-summary",
      { student_id, prefs_override, pathway_overrides }
    ),

  chat: (
    student_id: string,
    question: string,
    history: { role: string; content: string }[],
    prefs_override?: PrefsOverride,
    pathway_overrides: Operation[] = []
  ) =>
    post<{ text: string; provider: string; is_template: boolean }>(
      "/agents/chat",
      { student_id, question, history, prefs_override, pathway_overrides }
    ),
};
