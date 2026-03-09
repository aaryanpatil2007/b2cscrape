import React, { useState, useEffect, useCallback } from "react";
import { Zap, Database, Search } from "lucide-react";
import ScrapePanel from "./components/ScrapePanel";
import FilterBar from "./components/FilterBar";
import CompanyTable from "./components/CompanyTable";
import NotesModal from "./components/NotesModal";
import EmailModal from "./components/EmailModal";
import SearchPanel from "./components/SearchPanel";
import { getCompanies, getFilters, updateCompany, enrichAllEmails } from "./api/client";

export default function App() {
  const [tab, setTab] = useState("leads");
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
  const [emailModal, setEmailModal] = useState(null);
  const [enriching, setEnriching] = useState(false);

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

  const handleCompanyUpdate = (companyId, updates) => {
    setCompanies((prev) =>
      prev.map((c) => (c.id === companyId ? { ...c, ...updates } : c))
    );
  };

  const handleEmailSent = (companyId) => {
    setCompanies((prev) =>
      prev.map((c) =>
        c.id === companyId ? { ...c, outreach_done: true } : c
      )
    );
  };

  const handleEnrichAll = async () => {
    setEnriching(true);
    try {
      const results = await enrichAllEmails();
      for (const r of results) {
        if (r.email) {
          handleCompanyUpdate(r.company_id, {
            founder_email: r.email,
            email_verified: r.verified,
          });
        }
      }
    } catch (e) {
      console.error("Enrich all failed:", e);
    } finally {
      setEnriching(false);
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
              <p className="text-xs text-gray-400">Accelerator Scraper</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex items-center gap-1 bg-gray-800 rounded-lg p-1">
            <button
              onClick={() => setTab("leads")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === "leads"
                  ? "bg-violet-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              <Database className="w-3.5 h-3.5" />
              Leads
            </button>
            <button
              onClick={() => setTab("search")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                tab === "search"
                  ? "bg-violet-600 text-white"
                  : "text-gray-400 hover:text-gray-200"
              }`}
            >
              <Search className="w-3.5 h-3.5" />
              Search
            </button>
          </div>

          <div className="flex items-center gap-4">
            {tab === "leads" && (
              <>
                <button
                  onClick={handleEnrichAll}
                  disabled={enriching || companies.length === 0}
                  className="text-sm px-3 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-gray-300 hover:bg-gray-700 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {enriching ? "Enriching..." : "Enrich All Emails"}
                </button>
                <div className="text-sm text-gray-400">
                  {companies.length} companies
                </div>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {tab === "leads" ? (
          <>
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
              onOpenEmail={setEmailModal}
              onCompanyUpdate={handleCompanyUpdate}
            />
          </>
        ) : (
          <SearchPanel />
        )}
      </main>

      {notesModal && (
        <NotesModal
          company={notesModal}
          onSave={handleSaveNotes}
          onClose={() => setNotesModal(null)}
        />
      )}

      {emailModal && (
        <EmailModal
          company={emailModal}
          onSent={handleEmailSent}
          onClose={() => setEmailModal(null)}
        />
      )}
    </div>
  );
}
