import React from "react";
import {
  ExternalLink,
  Linkedin,
  StickyNote,
  Loader2,
  Building2,
} from "lucide-react";

export default function CompanyTable({
  companies,
  loading,
  onToggleOutreach,
  onOpenNotes,
}) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-gray-400">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Loading companies...
      </div>
    );
  }

  if (companies.length === 0) {
    return (
      <div className="text-center py-20">
        <Building2 className="w-12 h-12 text-gray-700 mx-auto mb-3" />
        <p className="text-gray-400 text-lg">No companies found</p>
        <p className="text-gray-600 text-sm mt-1">
          Run the scraper above to populate your leads
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left">
              <th className="px-4 py-3 text-gray-400 font-medium w-10">
                <span className="sr-only">Outreach</span>
              </th>
              <th className="px-4 py-3 text-gray-400 font-medium">Company</th>
              <th className="px-4 py-3 text-gray-400 font-medium hidden md:table-cell">
                Description
              </th>
              <th className="px-4 py-3 text-gray-400 font-medium">Source</th>
              <th className="px-4 py-3 text-gray-400 font-medium">Batch</th>
              <th className="px-4 py-3 text-gray-400 font-medium">Links</th>
              <th className="px-4 py-3 text-gray-400 font-medium w-10">
                <span className="sr-only">Notes</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => (
              <tr
                key={c.id}
                className="border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors"
              >
                {/* Outreach toggle */}
                <td className="px-4 py-3">
                  <button
                    onClick={() => onToggleOutreach(c)}
                    className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-colors ${
                      c.outreach_done
                        ? "bg-emerald-600 border-emerald-600"
                        : "border-gray-600 hover:border-gray-400"
                    }`}
                    title={
                      c.outreach_done ? "Mark as not contacted" : "Mark as contacted"
                    }
                  >
                    {c.outreach_done && (
                      <svg
                        className="w-3 h-3 text-white"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={3}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M5 13l4 4L19 7"
                        />
                      </svg>
                    )}
                  </button>
                </td>

                {/* Company name + logo */}
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {c.logo_url ? (
                      <img
                        src={c.logo_url}
                        alt=""
                        className="w-6 h-6 rounded object-cover bg-gray-800"
                        onError={(e) => (e.target.style.display = "none")}
                      />
                    ) : (
                      <div className="w-6 h-6 rounded bg-gray-800 flex items-center justify-center text-gray-500 text-xs font-bold">
                        {c.name?.[0]}
                      </div>
                    )}
                    <span className="font-medium text-gray-100">{c.name}</span>
                  </div>
                </td>

                {/* Description */}
                <td className="px-4 py-3 text-gray-400 hidden md:table-cell max-w-xs truncate">
                  {c.description}
                </td>

                {/* Source */}
                <td className="px-4 py-3">
                  <span className="inline-flex px-2 py-0.5 rounded-full text-xs font-medium bg-violet-900/50 text-violet-300 border border-violet-800/50">
                    {c.accelerator}
                  </span>
                </td>

                {/* Batch */}
                <td className="px-4 py-3 text-gray-400">{c.batch || "-"}</td>

                {/* Links */}
                <td className="px-4 py-3">
                  <div className="flex items-center gap-2">
                    {c.website && (
                      <a
                        href={c.website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-violet-400 transition-colors"
                        title="Website"
                      >
                        <ExternalLink className="w-4 h-4" />
                      </a>
                    )}
                    {c.linkedin_url && (
                      <a
                        href={c.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-gray-400 hover:text-blue-400 transition-colors"
                        title="LinkedIn"
                      >
                        <Linkedin className="w-4 h-4" />
                      </a>
                    )}
                  </div>
                </td>

                {/* Notes */}
                <td className="px-4 py-3">
                  <button
                    onClick={() => onOpenNotes(c)}
                    className={`transition-colors ${
                      c.notes
                        ? "text-amber-400 hover:text-amber-300"
                        : "text-gray-600 hover:text-gray-400"
                    }`}
                    title={c.notes || "Add notes"}
                  >
                    <StickyNote className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
