import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  GitBranch, Search, Filter, Play, Trash2,
  ExternalLink, RefreshCw, Loader
} from 'lucide-react';
import { getRepositories, triggerAnalysis, deleteRepository } from '../api/client';
import './RepositoriesPage.css';

export default function RepositoriesPage() {
  const [repos, setRepos] = useState([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [analyzingId, setAnalyzingId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    fetchRepos();
  }, [statusFilter]);

  const fetchRepos = async () => {
    setLoading(true);
    try {
      const params = { limit: 100 };
      if (statusFilter) params.status = statusFilter;
      if (search) params.search = search;
      const res = await getRepositories(params);
      setRepos(res.data.repositories);
      setTotal(res.data.total);
    } catch (err) {
      console.error('Failed to fetch repos:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    fetchRepos();
  };

  const handleAnalyze = async (repoId, e) => {
    e.stopPropagation();
    setAnalyzingId(repoId);
    try {
      await triggerAnalysis(repoId);
      setTimeout(fetchRepos, 1000);
    } catch (err) {
      console.error('Failed to trigger analysis:', err);
    } finally {
      setAnalyzingId(null);
    }
  };

  const handleDelete = async (repoId, e) => {
    e.stopPropagation();
    if (!confirm('Delete this repository?')) return;
    try {
      await deleteRepository(repoId);
      fetchRepos();
    } catch (err) {
      console.error('Failed to delete repo:', err);
    }
  };

  const getStatusBadge = (repo) => {
    if (repo.status === 'completed') {
      return null; // Will show feasibility badge instead from analysis
    }
    const statusMap = {
      queued: 'badge-pending',
      scraping: 'badge-processing',
      analyzing: 'badge-processing',
      building: 'badge-processing',
      failed: 'badge-not-buildable',
    };
    const labelMap = {
      queued: 'Queued',
      scraping: 'Scraping',
      analyzing: 'Analyzing',
      building: 'Building',
      failed: 'Failed',
    };
    return (
      <span className={`badge ${statusMap[repo.status] || 'badge-pending'}`}>
        {labelMap[repo.status] || repo.status}
      </span>
    );
  };

  return (
    <div className="page-container">
      <h1 className="page-title"><span className="text-gradient">Repositories</span></h1>
      <p className="page-subtitle">Manage and analyze your GitHub repositories</p>

      {/* Controls */}
      <div className="repos__controls glass-card">
        <form onSubmit={handleSearch} className="repos__search">
          <Search size={18} className="repos__search-icon" />
          <input
            type="text"
            placeholder="Search repositories..."
            className="repos__search-input"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </form>

        <div className="repos__filters">
          <Filter size={16} />
          <select
            className="repos__filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All Status</option>
            <option value="queued">Queued</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
        </div>

        <button className="btn btn-secondary" onClick={fetchRepos}>
          <RefreshCw size={16} /> Refresh
        </button>

        <span className="repos__count">{total} repositories</span>
      </div>

      {/* Table */}
      {loading ? (
        <div className="repos__loading">
          <div className="spinner spinner-lg"></div>
        </div>
      ) : repos.length === 0 ? (
        <div className="empty-state glass-card">
          <GitBranch size={48} />
          <h3>No repositories found</h3>
          <p>Upload an Excel file or paste a GitHub URL to get started.</p>
          <button className="btn btn-primary" onClick={() => navigate('/upload')}>
            Go to Upload
          </button>
        </div>
      ) : (
        <div className="repos__table-wrapper glass-card">
          <table className="repos__table">
            <thead>
              <tr>
                <th>Repository</th>
                <th>Owner</th>
                <th>Stars</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {repos.map((repo) => (
                <tr
                  key={repo.id}
                  className="repos__row"
                  onClick={() => navigate(`/repositories/${repo.id}`)}
                >
                  <td>
                    <div className="repos__name-cell">
                      <GitBranch size={16} className="repos__name-icon" />
                      <span className="repos__name">{repo.name}</span>
                    </div>
                  </td>
                  <td className="repos__owner">{repo.owner}</td>
                  <td className="repos__stars">⭐ {repo.stars}</td>
                  <td>{getStatusBadge(repo)}</td>
                  <td>
                    <div className="repos__actions" onClick={(e) => e.stopPropagation()}>
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={(e) => handleAnalyze(repo.id, e)}
                        disabled={analyzingId === repo.id}
                        title="Run Analysis"
                      >
                        {analyzingId === repo.id ? (
                          <Loader size={14} className="dropzone__spinner" />
                        ) : (
                          <Play size={14} />
                        )}
                      </button>
                      <a
                        href={repo.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="btn btn-sm btn-secondary"
                        title="Open on GitHub"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <ExternalLink size={14} />
                      </a>
                      <button
                        className="btn btn-sm btn-danger"
                        onClick={(e) => handleDelete(repo.id, e)}
                        title="Delete"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
