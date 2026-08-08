// TypeScript types matching the FastAPI backend responses

export interface Course {
  course_id: string;
  title: string;
  credits: number;
  description?: string;
  prerequisite_groups: string[][];
  corequisites?: string[];
  department: string;
  level: string;
  semesters_offered: string[];
  category: string;
  tags: string[];
}

export interface RequirementBlock {
  name: string;
  course_ids: string[];
  choose_n: number | null;
  credits_required: number | null;
  notes: string;
}

export interface Concentration {
  name: string;
  requirement_blocks: RequirementBlock[];
  description: string;
}

export interface Program {
  program_id: string;
  name: string;
  level: "undergrad" | "graduate";
  college: string;
  department: string;
  catalog_year: string;
  total_credits: number;
  requirement_blocks: RequirementBlock[];
  concentrations: Concentration[];
  catalog_url: string;
}

export interface StudentPreferences {
  interests: string[];
  max_credits_per_semester: number;
  min_credits_per_semester: number;
  preferred_schedule: string;
  concentration_choice: string | null;
  notes: string;
}

export interface Student {
  student_id: string;
  name: string;
  program_id: string;
  catalog_year: string;
  current_semester: string;
  target_graduation: string;
  completed_courses: string[];
  current_courses: string[];
  gpa: number | null;
  preferences: StudentPreferences;
}

export interface SemesterPlan {
  term: string;
  courses: string[];
  total_credits: number;
  rationale: string;
  current?: boolean;
  historical?: boolean;
}

export interface Pathway {
  student_id: string;
  generated_at: string;
  semester_plans: SemesterPlan[];
  summary: string;
  warnings: string[];
}

export interface BlockCompletion {
  block_name: string;
  target: number;
  covered_credits: number;
  covered_courses: string[];
  will_be_satisfied: boolean;
  gap_credits: number;
  is_open: boolean;
  notes: string;
  choose_n: number | null;
  course_ids: string[];
}

export interface DegreeCompletion {
  total_target: number;
  total_scheduled_credits: number;
  percent_complete: number;
  block_analysis: BlockCompletion[];
  incomplete_blocks: BlockCompletion[];
  total_gap: number;
  is_fully_on_track: boolean;
}

export interface RequirementStatus {
  block_name: string;
  total_required_credits: number;
  completed_credits: number;
  completed_courses: string[];
  remaining_options: string[];
  remaining_needed: number;
  fully_satisfied: boolean;
}

export interface PathwayResponse {
  student: Student;
  program: Program;
  pathway: Pathway;
  history: SemesterPlan[];
  current_term_plan: SemesterPlan | null;
  requirement_blocks: RequirementStatus[];
  completion: DegreeCompletion;
  applied_ops: Operation[];
  failed_ops: { op: Operation; error: string }[];
  diff: PathwayDiff | null;
}

export type Operation =
  | { type: "move"; course: string; from_term: string; to_term: string }
  | { type: "remove"; course: string; from_term: string }
  | { type: "add"; course: string; to_term: string }
  | { type: "change_concentration"; concentration: string }
  | { type: "change_credits"; value: number }
  | { type: "change_schedule"; value: string }
  | { type: "change_interests"; value: string[] };

export interface PathwayDiff {
  added: { course: string; term: string }[];
  removed: { course: string; term: string }[];
  moved: { course: string; from: string; to: string }[];
  unchanged: number;
}

export interface ValidatedOp {
  op: Operation;
  ok: boolean;
  error?: string;
  description: string;
}

export interface AgentResponse {
  routing: {
    intent: string;
    confidence: number;
    note: string;
  };
  agent: string;
  operations: Operation[];
  reasoning: string;
  is_answer?: boolean;
  validated: ValidatedOp[];
}

export interface PrefsOverride {
  interests?: string[];
  max_credits_per_semester?: number;
  preferred_schedule?: string;
  concentration_choice?: string | null;
}

export const NYIT_GOLD = "#FFB800";
export const NYIT_BLUE = "#002d72";
