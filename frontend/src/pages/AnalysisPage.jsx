import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft, GitBranch, ExternalLink, Star, GitFork,
  Code, Layers, Box, Terminal, Shield, Lightbulb,
  CheckCircle, AlertTriangle, XCircle, Clock
} from 'lucide-react';
import { getRepository, triggerAnalysis, generateAutoFix } from '../api/client';
import './AnalysisPage.css';

const SEVERITY_COLORS = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#fbbf24',
  low: '#3b82f6',
};

export default function AnalysisPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [fixingRecs, setFixingRecs] = useState({});

  useEffect(() => {
    fetchData();
  }, [id]);

  const fetchData = async () => {
    try {
      const res = await getRepository(id);
      setData(res.data);
    } catch (err) {
      console.error('Failed to fetch repository:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReAnalyze = async () => {
    try {
      await triggerAnalysis(id);
      setTimeout(fetchData, 2000);
    } catch (err) {
      console.error('Re-analysis failed:', err);
    }
  };

  const handleAutoFix = async (recId) => {
    setFixingRecs(prev => ({ ...prev, [recId]: { status: 'loading' } }));
    try {
      const res = await generateAutoFix(recId);
      setFixingRecs(prev => ({ ...prev, [recId]: { status: 'success', prUrl: res.data.pr_url } }));
    } catch (err) {
      console.error('Auto-fix failed:', err);
      setFixingRecs(prev => ({ ...prev, [recId]: { status: 'error', error: err.response?.data?.detail || 'Failed to generate PR' } }));
    }
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="analysis__loading"><div className="spinner spinner-lg"></div></div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="page-container">
        <div className="empty-state"><h3>Repository not found</h3></div>
      </div>
    );
  }

  const { repository: repo, analysis } = data;
  const score = analysis?.feasibility_score || 0;
  const securityScore = analysis?.security_score || 0;
  const fc = analysis?.feasibility_class;

  const getScoreColor = () => {
    if (score >= 75) return '#00d4aa';
    if (score >= 40) return '#fbbf24';
    return '#ef4444';
  };

  const getSecurityScoreColor = () => {
    if (securityScore >= 90) return '#00d4aa';
    if (securityScore >= 70) return '#fbbf24';
    return '#ef4444';
  };

  const getClassBadge = () => {
    if (fc === 'buildable') return { class: 'badge-buildable', icon: CheckCircle, label: 'Buildable' };
    if (fc === 'buildable_with_fixes') return { class: 'badge-fixes', icon: AlertTriangle, label: 'Buildable with Fixes' };
    if (fc === 'not_buildable') return { class: 'badge-not-buildable', icon: XCircle, label: 'Not Buildable' };
    return { class: 'badge-pending', icon: Clock, label: 'Pending' };
  };

  const classBadge = getClassBadge();

  // Language percentages
  const totalBytes = analysis?.languages ? Object.values(analysis.languages).reduce((a, b) => a + b, 0) : 0;
  const langItems = analysis?.languages
    ? Object.entries(analysis.languages)
      .sort((a, b) => b[1] - a[1])
      .map(([name, bytes]) => ({
        name,
        percentage: ((bytes / totalBytes) * 100).toFixed(1),
        bytes,
      }))
    : [];

  const tabs = [
    { id: 'overview', label: 'Overview', icon: Layers },
    { id: 'build', label: 'Build Logs', icon: Terminal },
    { id: 'recommendations', label: 'AI Recommendations', icon: Lightbulb },
  ];

  return (
    <div className="page-container">
      {/* Header */}
      <button className="analysis__back" onClick={() => navigate('/repositories')}>
        <ArrowLeft size={18} /> Back to Repositories
      </button>

      <div className="analysis__header glass-card">
        <div className="analysis__header-info">
          <div className="analysis__header-top">
            <h1 className="analysis__repo-name">
              <GitBranch size={24} />
              {repo.owner}/{repo.name}
            </h1>
            <a href={repo.url} target="_blank" rel="noopener noreferrer" className="btn btn-secondary btn-sm">
              <ExternalLink size={14} /> GitHub
            </a>
          </div>
          {repo.description && (
            <p className="analysis__description">{repo.description}</p>
          )}
          <div className="analysis__meta">
            <span><Star size={14} /> {repo.stars}</span>
            <span><GitFork size={14} /> {repo.forks}</span>
            <span className={`badge ${classBadge.class}`}>
              <classBadge.icon size={12} /> {classBadge.label}
            </span>
          </div>
        </div>

        {/* Score Gauges */}
        {analysis && (
          <div className="analysis__scores-container">
            <div className="analysis__score-section">
              <div className="score-gauge">
                <svg viewBox="0 0 120 120" width="120" height="120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
                  <circle
                    cx="60" cy="60" r="50" fill="none"
                    stroke={getScoreColor()}
                    strokeWidth="10"
                    strokeLinecap="round"
                    strokeDasharray={`${(score / 100) * 314} 314`}
                  />
                </svg>
                <span className="score-value" style={{ color: getScoreColor() }}>{score}</span>
              </div>
              <span className="analysis__score-label">Feasibility Score</span>
            </div>

            <div className="analysis__score-section">
              <div className="score-gauge">
                <svg viewBox="0 0 120 120" width="120" height="120">
                  <circle cx="60" cy="60" r="50" fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="10" />
                  <circle
                    cx="60" cy="60" r="50" fill="none"
                    stroke={getSecurityScoreColor()}
                    strokeWidth="10"
                    strokeLinecap="round"
                    strokeDasharray={`${(securityScore / 100) * 314} 314`}
                  />
                </svg>
                <span className="score-value" style={{ color: getSecurityScoreColor() }}>{securityScore}</span>
              </div>
              <span className="analysis__score-label">Security Score</span>
            </div>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="analysis__tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={`analysis__tab ${activeTab === tab.id ? 'analysis__tab--active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <tab.icon size={16} /> {tab.label}
            {tab.id === 'recommendations' && analysis?.recommendations?.length > 0 && (
              <span className="analysis__tab-count">{analysis.recommendations.length}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="analysis__content">
        {activeTab === 'overview' && analysis && (
          <div className="analysis__overview animate-fade-in">
            {/* Languages */}
            <div className="analysis__section glass-card">
              <h3><Code size={18} /> Languages</h3>
              <div className="analysis__lang-bar">
                {langItems.map((lang, i) => (
                  <div
                    key={lang.name}
                    className="analysis__lang-segment"
                    style={{
                      width: `${lang.percentage}%`,
                      background: ['#667eea', '#764ba2', '#00d4aa', '#fbbf24', '#ef4444', '#3b82f6'][i % 6],
                    }}
                    title={`${lang.name}: ${lang.percentage}%`}
                  />
                ))}
              </div>
              <div className="analysis__lang-list">
                {langItems.map((lang, i) => (
                  <span key={lang.name} className="analysis__lang-item">
                    <span
                      className="analysis__lang-dot"
                      style={{ background: ['#667eea', '#764ba2', '#00d4aa', '#fbbf24', '#ef4444', '#3b82f6'][i % 6] }}
                    />
                    {lang.name} ({lang.percentage}%)
                  </span>
                ))}
              </div>
            </div>

            {/* Frameworks & Tech */}
            <div className="analysis__grid">
              <div className="analysis__section glass-card">
                <h3><Box size={18} /> Frameworks</h3>
                <div className="analysis__tags">
                  {analysis.frameworks?.length > 0 ? (
                    analysis.frameworks.map((fw) => (
                      <span key={fw} className="analysis__tag">{fw}</span>
                    ))
                  ) : (
                    <span className="analysis__empty-tag">No frameworks detected</span>
                  )}
                </div>
              </div>

              <div className="analysis__section glass-card">
                <h3><Shield size={18} /> Detected Files</h3>
                <div className="analysis__file-list">
                  {analysis.detected_files?.map((f) => (
                    <span key={f} className="analysis__file-item">{f}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Score Breakdown */}
            {analysis.score_breakdown && Object.keys(analysis.score_breakdown).length > 0 && (
              <div className="analysis__section glass-card">
                <h3><Layers size={18} /> Score Breakdown</h3>
                <div className="analysis__breakdown">
                  {Object.entries(analysis.score_breakdown).map(([key, val]) => (
                    <div key={key} className="breakdown-item">
                      <div className="breakdown-item__header">
                        <span className="breakdown-item__name">{val.description}</span>
                        <span className="breakdown-item__score">{val.weighted_score}/{val.weight}</span>
                      </div>
                      <div className="breakdown-item__bar">
                        <div
                          className="breakdown-item__fill"
                          style={{
                            width: `${(val.weighted_score / val.weight) * 100}%`,
                            background: val.weighted_score / val.weight >= 0.7 ? '#00d4aa' :
                              val.weighted_score / val.weight >= 0.4 ? '#fbbf24' : '#ef4444',
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'build' && (
          <div className="analysis__build animate-fade-in">
            <div className="analysis__section glass-card">
              <h3><Terminal size={18} /> Build Output</h3>
              <div className="analysis__build-meta">
                <span className={`badge ${analysis?.build_status === 'success' ? 'badge-buildable' : 'badge-not-buildable'}`}>
                  {analysis?.build_status || 'N/A'}
                </span>
                {analysis?.build_duration_seconds > 0 && (
                  <span className="analysis__build-time">
                    <Clock size={14} /> {analysis.build_duration_seconds.toFixed(1)}s
                  </span>
                )}
              </div>
              <pre className="analysis__build-logs">
                {analysis?.build_logs || 'No build logs available. Run analysis first.'}
              </pre>
            </div>
          </div>
        )}

        {activeTab === 'recommendations' && (
          <div className="analysis__recs animate-fade-in">
            {analysis?.recommendations?.length > 0 ? (
              analysis.recommendations.map((rec, i) => (
                <div key={i} className={`rec-card glass-card ${rec.category === 'security' ? 'rec-card--security' : ''}`}>
                  <div className="rec-card__header">
                    <span
                      className="rec-card__severity"
                      style={{ background: SEVERITY_COLORS[rec.severity] || '#64748b' }}
                    >
                      {rec.severity}
                    </span>
                    <span className="rec-card__category">
                      {rec.category === 'security' ? <Shield size={12} style={{ marginRight: '4px' }} /> : null}
                      {rec.category}
                    </span>
                    <span className="rec-card__provider">via {rec.ai_provider}</span>
                  </div>
                  <h4 className="rec-card__title">{rec.title}</h4>
                  <p className="rec-card__description">{rec.description}</p>
                  <div className="rec-card__fix">
                    <strong>Fix:</strong> <code>{rec.fix}</code>
                  </div>
                  <div className="rec-card__footer">
                    <div className="rec-card__meta-info">
                      <span className="rec-card__effort">Effort: {rec.effort}</span>
                      {rec.estimated_time && (
                        <span className="rec-card__time">
                          <Clock size={12} /> {rec.estimated_time}
                        </span>
                      )}
                    </div>
                    <div className="rec-card__action">
                      {fixingRecs[rec.id]?.status === 'loading' ? (
                        <button className="btn btn-secondary btn-sm" disabled>
                          <div className="spinner spinner-sm"></div> Generating PR...
                        </button>
                      ) : fixingRecs[rec.id]?.status === 'success' ? (
                        <a href={fixingRecs[rec.id].prUrl} target="_blank" rel="noopener noreferrer" className="btn btn-success btn-sm">
                          ✅ PR Created: View on GitHub
                        </a>
                      ) : fixingRecs[rec.id]?.status === 'error' ? (
                        <div className="rec-card__error" title={fixingRecs[rec.id].error}>
                          ❌ Auto-Fix Failed
                        </div>
                      ) : (
                        <button className="btn btn-primary btn-sm" onClick={() => handleAutoFix(rec.id)}>
                          🚀 Auto-Fix Code
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="empty-state glass-card">
                <Lightbulb size={48} />
                <h3>No recommendations yet</h3>
                <p>Run analysis to get AI-powered fix recommendations.</p>
                <button className="btn btn-primary" onClick={handleReAnalyze}>
                  Run Analysis
                </button>
              </div>
            )}
          </div>
        )}

        {!analysis && (
          <div className="empty-state glass-card animate-fade-in">
            <Layers size={48} />
            <h3>No analysis data</h3>
            <p>Run analysis on this repository to see tech stack, build results, and recommendations.</p>
            <button className="btn btn-primary btn-lg" onClick={handleReAnalyze}>
              Run Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
