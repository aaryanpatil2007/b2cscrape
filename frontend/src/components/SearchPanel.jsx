import React, { useState, useRef, useEffect } from "react";
import {
  Search,
  Loader2,
  ExternalLink,
  Globe,
  CheckCircle2,
  XCircle,
  StopCircle,
  Clock,
  Trash2,
  ChevronDown,
  ChevronUp,
} from "lucide-react";

const HISTORY_KEY = "leadflow_search_history";

function loadHistory() {
  try {
    return JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveHistory(history) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

function ResultsTable({ results }) {
  if (!results || results.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-left">
            <th className="px-4 py-3 text-gray-400 font-medium">Company</th>
            <th className="px-4 py-3 text-gray-400 font-medium hidden md:table-cell">Description</th>
            <th className="px-4 py-3 text-gray-400 font-medium">Founders</th>
            <th className="px-4 py-3 text-gray-400 font-medium">Batch</th>
            <th className="px-4 py-3 text-gray-400 font-medium">Email</th>
            <th className="px-4 py-3 text-gray-400 font-medium">Links</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors animate-fadeIn">
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  {r.logo_url ? (
                    <img src={r.logo_url} alt="" className="w-6 h-6 rounded object-cover bg-gray-800" onError={(e) => (e.target.style.display = "none")} />
                  ) : (
                    <div className="w-6 h-6 rounded bg-gray-800 flex items-center justify-center text-gray-500 text-xs font-bold">{r.name?.[0]}</div>
                  )}
                  <span className="font-medium text-gray-100">{r.name}</span>
                </div>
              </td>
              <td className="px-4 py-3 text-gray-400 hidden md:table-cell max-w-xs truncate">{r.description}</td>
              <td className="px-4 py-3 text-gray-300 text-xs max-w-[140px] truncate">{r.founders || "-"}</td>
              <td className="px-4 py-3 text-gray-400">{r.batch || "-"}</td>
              <td className="px-4 py-3">
                {r.founder_email ? (
                  <div className="flex items-center gap-1 min-w-0">
                    {r.email_verified ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" title="Verified" />
                    ) : (
                      <XCircle className="w-3.5 h-3.5 text-amber-400 shrink-0" title="Unverified" />
                    )}
                    <a href={`mailto:${r.founder_email}`} className="text-gray-300 text-xs truncate max-w-[160px] hover:text-violet-400 transition-colors" title={r.founder_email}>
                      {r.founder_email}
                    </a>
                  </div>
                ) : (
                  <span className="text-gray-600 text-xs">-</span>
                )}
              </td>
              <td className="px-4 py-3">
                <div className="flex items-center gap-2">
                  {r.website && !r.website.includes("ycombinator.com") && (
                    <a href={r.website} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-violet-400 transition-colors" title="Website">
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  )}
                  {r.source_url && (
                    <a href={r.source_url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-orange-400 transition-colors" title="Accelerator page">
                      <Globe className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [total, setTotal] = useState(null);
  const [hunterCredits, setHunterCredits] = useState(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const abortRef = useRef(null);

  const [history, setHistory] = useState(loadHistory);
  const [viewMode, setViewMode] = useState("search"); // "search" | "history"
  const [expandedHistory, setExpandedHistory] = useState(null);

  // Save completed search to history
  const saveToHistory = (query, results) => {
    const entry = {
      id: Date.now(),
      query,
      results,
      count: results.length,
      date: new Date().toISOString(),
    };
    const updated = [entry, ...history].slice(0, 20); // Keep last 20
    setHistory(updated);
    saveHistory(updated);
  };

  const deleteHistoryEntry = (id) => {
    const updated = history.filter((h) => h.id !== id);
    setHistory(updated);
    saveHistory(updated);
    if (expandedHistory === id) setExpandedHistory(null);
  };

  const clearAllHistory = () => {
    setHistory([]);
    saveHistory([]);
    setExpandedHistory(null);
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    if (abortRef.current) abortRef.current.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setSearching(true);
    setError("");
    setResults([]);
    setTotal(null);
    setHunterCredits(null);
    setDone(false);
    setViewMode("search");

    const collectedResults = [];

    try {
      const res = await fetch("/api/search/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim() }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(`API error ${res.status}: ${text}`);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === "total") {
              setTotal(event.count);
              setHunterCredits(event.hunter_credits);
            } else if (event.type === "result") {
              collectedResults.push(event.data);
              setResults((prev) => [...prev, event.data]);
            } else if (event.type === "done") {
              setDone(true);
            } else if (event.type === "error") {
              setError(event.message);
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        setError(e.message);
      }
    } finally {
      setSearching(false);
      setDone(true);
      // Save to history if we got results
      if (collectedResults.length > 0) {
        saveToHistory(query.trim(), collectedResults);
      }
    }
  };

  const handleStop = () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setSearching(false);
    setDone(true);
  };

  const formatDate = (iso) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  };

  return (
    <div className="space-y-6">
      {/* Search bar */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2 mb-4">
          <Globe className="w-5 h-5 text-violet-400" />
          Accelerator Search
        </h2>
        <p className="text-sm text-gray-400 mb-4">
          Search any accelerator portfolio live. Scrapes company pages and finds founder emails in real-time.
        </p>
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. yc w25, yc S24, yc winter 2025 fintech..."
              className="w-full bg-gray-800 border border-gray-700 text-gray-200 rounded-lg pl-9 pr-3 py-2.5 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none placeholder-gray-500"
            />
          </div>
          {searching ? (
            <button type="button" onClick={handleStop} className="flex items-center gap-2 bg-red-600 hover:bg-red-500 text-white font-medium py-2.5 px-5 rounded-lg text-sm transition-colors whitespace-nowrap">
              <StopCircle className="w-4 h-4" />
              Stop
            </button>
          ) : (
            <button type="submit" disabled={!query.trim()} className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-2.5 px-5 rounded-lg text-sm transition-colors whitespace-nowrap">
              <Search className="w-4 h-4" />
              Search
            </button>
          )}
        </form>

        {error && (
          <div className="mt-3 text-sm text-red-400 bg-red-900/20 border border-red-800/50 rounded-lg p-3">{error}</div>
        )}
      </div>

      {/* Sub-tabs: Current Search / History */}
      {(results.length > 0 || history.length > 0 || total !== null) && (
        <div className="flex items-center gap-1 bg-gray-900 border border-gray-800 rounded-lg p-1 w-fit">
          <button
            onClick={() => setViewMode("search")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              viewMode === "search" ? "bg-violet-600 text-white" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <Search className="w-3.5 h-3.5" />
            Current Search
          </button>
          <button
            onClick={() => setViewMode("history")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
              viewMode === "history" ? "bg-violet-600 text-white" : "text-gray-400 hover:text-gray-200"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            History
            {history.length > 0 && (
              <span className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded-full ml-1">{history.length}</span>
            )}
          </button>
        </div>
      )}

      {viewMode === "search" && (
        <>
          {/* Progress bar */}
          {total !== null && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
              {hunterCredits === false && (
                <div className="text-sm text-amber-400 bg-amber-900/20 border border-amber-800/50 rounded-lg p-3">
                  Hunter.io credits exhausted — companies will be scraped but emails won't be enriched until credits reset.
                </div>
              )}
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-300">
                  {searching ? (
                    <span className="flex items-center gap-2">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Scraping company pages{hunterCredits ? " & finding emails" : ""}...
                    </span>
                  ) : (
                    "Search complete"
                  )}
                </span>
                <span className="text-gray-400">{results.length} / {total} companies</span>
              </div>
              <div className="w-full bg-gray-800 rounded-full h-2">
                <div className="bg-violet-600 h-2 rounded-full transition-all duration-300" style={{ width: `${total > 0 ? (results.length / total) * 100 : 0}%` }} />
              </div>
            </div>
          )}

          {/* Current results */}
          {results.length > 0 && (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <ResultsTable results={results} />
            </div>
          )}

          {done && results.length === 0 && !error && total !== null && (
            <div className="text-center py-12 text-gray-400 bg-gray-900 border border-gray-800 rounded-xl">
              No results found for "{query}"
            </div>
          )}
        </>
      )}

      {viewMode === "history" && (
        <div className="space-y-3">
          {history.length === 0 ? (
            <div className="text-center py-12 text-gray-400 bg-gray-900 border border-gray-800 rounded-xl">
              No search history yet. Run a search to save results here.
            </div>
          ) : (
            <>
              <div className="flex justify-end">
                <button onClick={clearAllHistory} className="text-xs text-gray-500 hover:text-red-400 transition-colors flex items-center gap-1">
                  <Trash2 className="w-3 h-3" />
                  Clear all
                </button>
              </div>
              {history.map((entry) => (
                <div key={entry.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                  {/* Header — click to expand */}
                  <button
                    onClick={() => setExpandedHistory(expandedHistory === entry.id ? null : entry.id)}
                    className="w-full flex items-center justify-between px-5 py-4 hover:bg-gray-800/30 transition-colors text-left"
                  >
                    <div className="flex items-center gap-3">
                      <Search className="w-4 h-4 text-violet-400 shrink-0" />
                      <div>
                        <span className="font-medium text-gray-100">{entry.query}</span>
                        <span className="text-gray-500 text-sm ml-3">
                          {entry.count} companies
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-gray-500">{formatDate(entry.date)}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); deleteHistoryEntry(entry.id); }}
                        className="text-gray-600 hover:text-red-400 transition-colors p-1"
                        title="Delete"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                      {expandedHistory === entry.id ? (
                        <ChevronUp className="w-4 h-4 text-gray-500" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-gray-500" />
                      )}
                    </div>
                  </button>

                  {/* Expanded results table */}
                  {expandedHistory === entry.id && (
                    <div className="border-t border-gray-800">
                      <ResultsTable results={entry.results} />
                    </div>
                  )}
                </div>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  );
}
