import React, { useState } from "react";
import { X, Save } from "lucide-react";

export default function NotesModal({ company, onSave, onClose }) {
  const [notes, setNotes] = useState(company.notes || "");

  const handleSave = () => {
    onSave(company, notes);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-700 rounded-xl w-full max-w-lg mx-4 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-800">
          <h3 className="text-lg font-semibold text-white">
            Notes — {company.name}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Add outreach notes, follow-up reminders, etc..."
            rows={6}
            className="w-full bg-gray-800 border border-gray-700 text-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-violet-500 focus:border-violet-500 outline-none placeholder-gray-500 resize-none"
          />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 px-5 py-4 border-t border-gray-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-400 hover:text-gray-200 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white font-medium py-2 px-4 rounded-lg text-sm transition-colors"
          >
            <Save className="w-4 h-4" />
            Save Notes
          </button>
        </div>
      </div>
    </div>
  );
}
