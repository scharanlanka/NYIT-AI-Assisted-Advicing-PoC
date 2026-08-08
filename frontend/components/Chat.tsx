"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { Operation, PrefsOverride, Program, Student } from "@/lib/types";
import { NYIT_BLUE } from "@/lib/types";

export default function Chat({
  student,
  program,
  studentId,
  prefsOverride,
  overrides,
}: {
  student: Student;
  program: Program;
  studentId: string;
  prefsOverride: PrefsOverride | undefined;
  overrides: Operation[];
}) {
  const [history, setHistory] = useState<{ role: string; content: string }[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistory([]);
    setInput("");
  }, [studentId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [history]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const question = input;
    setInput("");
    const newHistory = [...history, { role: "user", content: question }];
    setHistory(newHistory);
    setLoading(true);
    try {
      const result = await api.chat(
        studentId,
        question,
        newHistory.slice(0, -1),
        prefsOverride,
        overrides
      );
      setHistory([...newHistory, { role: "assistant", content: result.text }]);
    } catch (e: any) {
      setHistory([
        ...newHistory,
        { role: "assistant", content: `Error: ${e.message}` },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-xl font-semibold mb-1" style={{ color: NYIT_BLUE }}>
        Ask about {student.name.split(" ")[0]}'s pathway
      </h2>
      <p className="text-xs text-gray-500 mb-4">
        Natural-language Q&A grounded in the actual pathway.
      </p>
      <div className="h-80 overflow-y-auto p-4 bg-gray-50 rounded-xl border border-gray-100 mb-3 space-y-3">
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="text-3xl">💬</div>
            <p className="text-sm text-gray-500 font-medium">Ask anything about this pathway</p>
            <div className="flex flex-wrap gap-2 justify-center">
              {[
                "Why was this pathway recommended?",
                "What prereqs am I missing?",
                "When can I take Machine Learning?",
              ].map((q) => (
                <button
                  key={q}
                  onClick={() => setInput(q)}
                  className="text-xs px-3 py-1.5 rounded-full border border-gray-200 bg-white text-gray-600 hover:border-blue-300 hover:text-blue-700 transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          history.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`px-3 py-2 rounded-lg text-sm max-w-md ${
                  msg.role === "user" ? "text-white" : "bg-white border border-gray-200"
                }`}
                style={msg.role === "user" ? { background: NYIT_BLUE } : {}}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
              </div>
            </div>
          ))
        )}
        {loading && (
          <div className="flex justify-start">
            <div className="px-3 py-2 rounded-lg text-sm bg-white border border-gray-200 text-gray-500 italic">
              Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>
      <div className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="Ask about courses, prereqs, or your pathway..."
          className="flex-1 text-sm border border-gray-200 rounded-xl px-4 py-2.5 bg-gray-50"
        />
        <button
          onClick={send}
          disabled={loading}
          className="px-5 py-2.5 rounded-xl text-white text-sm font-semibold disabled:opacity-50 transition-opacity"
          style={{ background: NYIT_BLUE }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
