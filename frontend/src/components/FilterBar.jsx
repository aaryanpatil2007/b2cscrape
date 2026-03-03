import React from "react";
import { Search, Filter } from "lucide-react";

export default function FilterBar({ filters, activeFilters, onChange }) {
  const update = (key, value) => {
    onChange({ ...activeFilters, [key]: value });
  };

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <div className="flex flex-wrap items-center gap-3">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <input
            type="text"
            placeholder="Search companies..."
            value={activeFilters.search}
            onChange={(e) => update("search", e.target.value)}
            className="w-full bg-gray-800 border border-gray-700 text-gray-200 rounded-lg pl-9 pr-3 py-2 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none placeholder-gray-500"
          />
        </div>

        {/* Accelerator filter */}
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <select
            value={activeFilters.accelerator}
            onChange={(e) => update("accelerator", e.target.value)}
            className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none"
          >
            <option value="">All Accelerators</option>
            {filters.accelerators.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>

        {/* Batch filter */}
        <select
          value={activeFilters.batch}
          onChange={(e) => update("batch", e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none"
        >
          <option value="">All Batches</option>
          {filters.batches.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>

        {/* Outreach status filter */}
        <select
          value={activeFilters.outreach_done}
          onChange={(e) => update("outreach_done", e.target.value)}
          className="bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none"
        >
          <option value="">All Status</option>
          <option value="false">Not Contacted</option>
          <option value="true">Contacted</option>
        </select>
      </div>
    </div>
  );
}
