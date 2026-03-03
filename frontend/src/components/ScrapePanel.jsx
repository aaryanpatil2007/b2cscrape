import React, { useState } from "react";
import {
  Play,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Settings2,
} from "lucide-react";
import { runScrape } from "../api/client";

const SOURCES = [
  { key: "yc", label: "Y Combinator" },
  { key: "a16z", label: "a16z Speedrun" },
  { key: "pearx", label: "PearX" },
];

const YEAR_OPTIONS = [
  { value: 1, label: "Last 1 Year" },
  { value: 2, label: "Last 2 Years" },
  { value: 3, label: "Last 3 Years" },
  { value: 5, label: "Last 5 Years" },
  { value: 10, label: "Last 10 Years" },
];

export default function ScrapePanel({ onComplete }) {
  const [selectedSources, setSelectedSources] = useState(["yc"]);
  const [yearsBack, setYearsBack] = useState(1);
  const [headless, setHeadless] = useState(true);
  const [scraping, setScraping] = useState(false);
  const [results, setResults] = useState(null);
  const [expanded, setExpanded] = useState(false);

  const toggleSource = (key) => {
    setSelectedSources((prev) =>
      prev.includes(key) ? prev.filter((s) => s !== key) : [...prev, key]
    );
  };

  const handleScrape = async () => {
    if (selectedSources.length === 0) return;
    setScraping(true);
    setResults(null);
    try {
      const data = await runScrape({
        sources: selectedSources,
        years_back: yearsBack,
        headless,
      });
      setResults(data);
      onComplete();
    } catch (e) {
      setResults([
        {
          source: "Error",
          new_companies: 0,
          skipped_duplicates: 0,
          errors: [e.message],
        },
      ]);
    } finally {
      setScraping(false);
    }
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Settings2 className="w-5 h-5 text-violet-400" />
          Scrape Engine
        </h2>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-sm text-gray-400 hover:text-gray-200 transition-colors"
        >
          {expanded ? "Collapse" : "Configure"}
        </button>
      </div>

      {expanded && (
        <div className="space-y-4 mb-4">
          {/* Source selection */}
          <div>
            <label className="text-sm text-gray-400 mb-2 block">Sources</label>
            <div className="flex flex-wrap gap-2">
              {SOURCES.map((s) => (
                <button
                  key={s.key}
                  onClick={() => toggleSource(s.key)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    selectedSources.includes(s.key)
                      ? "bg-violet-600 text-white"
                      : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                  }`}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Year filter */}
          <div>
            <label className="text-sm text-gray-400 mb-2 block">
              Recency Filter
            </label>
            <select
              value={yearsBack}
              onChange={(e) => setYearsBack(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none"
            >
              {YEAR_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>

          {/* Headless toggle */}
          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={headless}
              onChange={() => setHeadless(!headless)}
              className="w-4 h-4 rounded bg-gray-800 border-gray-600 text-violet-600 focus:ring-violet-500"
            />
            <span className="text-sm text-gray-300">Headless mode</span>
          </label>
        </div>
      )}

      {/* Run button */}
      <button
        onClick={handleScrape}
        disabled={scraping || selectedSources.length === 0}
        className="w-full flex items-center justify-center gap-2 bg-violet-600 hover:bg-violet-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-2.5 px-4 rounded-lg transition-colors"
      >
        {scraping ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Scraping...
          </>
        ) : (
          <>
            <Play className="w-4 h-4" />
            Run Scraper
          </>
        )}
      </button>

      {/* Results */}
      {results && (
        <div className="mt-4 space-y-2">
          {results.map((r, i) => (
            <div
              key={i}
              className={`flex items-start gap-2 text-sm p-3 rounded-lg ${
                r.errors.length > 0
                  ? "bg-red-900/20 border border-red-800/50"
                  : "bg-emerald-900/20 border border-emerald-800/50"
              }`}
            >
              {r.errors.length > 0 ? (
                <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
              ) : (
                <CheckCircle2 className="w-4 h-4 text-emerald-400 mt-0.5 shrink-0" />
              )}
              <div>
                <span className="font-medium text-gray-200">{r.source}:</span>{" "}
                <span className="text-gray-400">
                  {r.new_companies} new, {r.skipped_duplicates} duplicates
                  skipped
                </span>
                {r.errors.length > 0 && (
                  <div className="text-red-400 text-xs mt-1">
                    {r.errors.join("; ")}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
