import React, { useState, useEffect, useCallback } from "react";
import { Zap } from "lucide-react";
import ScrapePanel from "./components/ScrapePanel";
import FilterBar from "./components/FilterBar";
import CompanyTable from "./components/CompanyTable";
import NotesModal from "./components/NotesModal";
import { getCompanies, getFilters, updateCompany } from "./api/client";

export default function App() {
  const [companies, setCompanies] = useState([]);
  const [filters, setFilters] = useState({ accelerators: [], batches: [] });
  const [activeFilters, setActiveFilters] = useState({
    accelerator: "",
    batch: "",
    outreach_done: "",
    search: "",
  });
  const [loading, setLoading] = useState(false);
  const [notesModal, setNotesModal] = useState(null);

  const fetchCompanies = useCallback(async () => {
    setLoading(true);
    try {
      const params = { ...activeFilters };
      if (params.outreach_done === "") delete params.outreach_done;
      const data = await getCompanies(params);
      setCompanies(data);
    } catch (e) {
      console.error("Failed to fetch companies:", e);
    } finally {
      setLoading(false);
    }
  }, [activeFilters]);

  const fetchFilters = async () => {
    try {
      const data = await getFilters();
      setFilters(data);
    } catch (e) {
      console.error("Failed to fetch filters:", e);
    }
  };

  useEffect(() => {
    fetchCompanies();
  }, [fetchCompanies]);

  useEffect(() => {
    fetchFilters();
  }, []);

  const handleToggleOutreach = async (company) => {
    try {
      await updateCompany(company.id, {
        outreach_done: !company.outreach_done,
      });
      setCompanies((prev) =>
        prev.map((c) =>
          c.id === company.id ? { ...c, outreach_done: !c.outreach_done } : c
        )
      );
    } catch (e) {
      console.error("Failed to update outreach:", e);
    }
  };

  const handleSaveNotes = async (company, notes) => {
    try {
      await updateCompany(company.id, { notes });
      setCompanies((prev) =>
        prev.map((c) => (c.id === company.id ? { ...c, notes } : c))
      );
      setNotesModal(null);
    } catch (e) {
      console.error("Failed to save notes:", e);
    }
  };

  const handleScrapeComplete = () => {
    fetchCompanies();
    fetchFilters();
  };

  return (
    <div className="min-h-screen bg-gray-950">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/80 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-violet-600 p-2 rounded-lg">
              <Zap className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">LeadFlow</h1>
              <p className="text-xs text-gray-400">
                Accelerator Scraper
              </p>
            </div>
          </div>
          <div className="text-sm text-gray-400">
            {companies.length} companies loaded
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        <ScrapePanel onComplete={handleScrapeComplete} />
        <FilterBar
          filters={filters}
          activeFilters={activeFilters}
          onChange={setActiveFilters}
        />
        <CompanyTable
          companies={companies}
          loading={loading}
          onToggleOutreach={handleToggleOutreach}
          onOpenNotes={setNotesModal}
        />
      </main>

      {notesModal && (
        <NotesModal
          company={notesModal}
          onSave={handleSaveNotes}
          onClose={() => setNotesModal(null)}
        />
      )}
    </div>
  );
}
