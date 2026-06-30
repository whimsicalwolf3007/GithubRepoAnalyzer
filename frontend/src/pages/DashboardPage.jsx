import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  CheckCircle2,
  Clock3,
  GitBranch,
  Layers,
  ShieldAlert,
  Wrench,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  getDashboardStats,
  getFeasibilityOverview,
  getRecentActivity,
  getTechDistribution,
} from '../api/client';
import './DashboardPage.css';

const CHART_COLORS = ['#00d4aa', '#fbbf24', '#ef4444', '#3b82f6', '#667eea'];

function formatStatus(status) {
  if (!status) return 'Unknown';
  return status
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ');
}

function formatWhen(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleString();
}

export default function DashboardPage() {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [tech, setTech] = useState(null);
  const [overview, setOverview] = useState(null);
  const [recent, setRecent] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [statsRes, techRes, overviewRes, recentRes] = await Promise.all([
          getDashboardStats(),
          getTechDistribution(),
          getFeasibilityOverview(),
          getRecentActivity(),
        ]);
        setStats(statsRes.data);
        setTech(techRes.data);
        setOverview(overviewRes.data);
        setRecent(Array.isArray(recentRes.data) ? recentRes.data : []);
      } catch (error) {
        console.error('Failed to load dashboard:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  const feasibilityPie = useMemo(() => {
    if (!overview) return [];
    return [
      { name: 'Buildable', value: overview.buildable || 0 },
      { name: 'With Fixes', value: overview.buildable_with_fixes || 0 },
      { name: 'Not Buildable', value: overview.not_buildable || 0 },
      { name: 'Pending', value: overview.pending || 0 },
    ];
  }, [overview]);

  const languageBars = useMemo(() => {
    if (!tech?.languages?.length) return [];
    return tech.languages.slice(0, 8).map((item) => ({
      name: item.name,
      count: item.count,
    }));
  }, [tech]);

  if (loading) {
    return (
      <div className="page-container">
        <div className="dashboard__loading">
          <div className="spinner spinner-lg"></div>
          <p>Loading dashboard data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container">
      <div className="dashboard__header">
        <div>
          <h1 className="page-title"><span className="text-gradient">Dashboard</span></h1>
          <p className="page-subtitle">Repository feasibility and analysis overview</p>
        </div>
        <div className="dashboard__header-stats">
          <div className="dashboard__avg-score">
            <Layers size={16} />
            Avg score
            <strong>{stats?.avg_feasibility_score ?? 0}</strong>
          </div>
        </div>
      </div>

      <div className="dashboard__cards">
        <div className="stat-card glass-card">
          <div className="stat-card__icon" style={{ background: 'rgba(59,130,246,0.15)' }}>
            <GitBranch size={22} color="#3b82f6" />
          </div>
          <div className="stat-card__content">
            <span className="stat-card__value">{stats?.total_repos ?? 0}</span>
            <span className="stat-card__label">Total Repositories</span>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-card__icon" style={{ background: 'rgba(0,212,170,0.15)' }}>
            <CheckCircle2 size={22} color="#00d4aa" />
          </div>
          <div className="stat-card__content">
            <span className="stat-card__value">{stats?.buildable ?? 0}</span>
            <span className="stat-card__label">Buildable</span>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-card__icon" style={{ background: 'rgba(251,191,36,0.15)' }}>
            <Wrench size={22} color="#fbbf24" />
          </div>
          <div className="stat-card__content">
            <span className="stat-card__value">{stats?.buildable_with_fixes ?? 0}</span>
            <span className="stat-card__label">Buildable with Fixes</span>
          </div>
        </div>

        <div className="stat-card glass-card">
          <div className="stat-card__icon" style={{ background: 'rgba(239,68,68,0.15)' }}>
            <ShieldAlert size={22} color="#ef4444" />
          </div>
          <div className="stat-card__content">
            <span className="stat-card__value">{stats?.not_buildable ?? 0}</span>
            <span className="stat-card__label">Not Buildable</span>
          </div>
        </div>
      </div>

      <div className="dashboard__charts">
        <div className="chart-card glass-card">
          <h3 className="chart-card__title"><Activity size={18} /> Feasibility Mix</h3>
          {feasibilityPie.some((item) => item.value > 0) ? (
            <ResponsiveContainer width="100%" height={280}>
              <PieChart>
                <Pie data={feasibilityPie} dataKey="value" nameKey="name" innerRadius={55} outerRadius={95}>
                  {feasibilityPie.map((entry, index) => (
                    <Cell key={entry.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: '#10182a',
                    border: '1px solid rgba(255,255,255,0.12)',
                    borderRadius: '8px',
                    color: '#f1f5f9',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No feasibility data yet</p></div>
          )}
        </div>

        <div className="chart-card glass-card">
          <h3 className="chart-card__title"><Layers size={18} /> Top Languages</h3>
          {languageBars.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={languageBars}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: '#10182a',
                    border: '1px solid rgba(255,255,255,0.12)',
                    borderRadius: '8px',
                    color: '#f1f5f9',
                  }}
                />
                <Bar dataKey="count" radius={[8, 8, 0, 0]}>
                  {languageBars.map((entry, index) => (
                    <Cell key={entry.name} fill={CHART_COLORS[index % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No language data yet</p></div>
          )}
        </div>
      </div>

      <div className="activity-card glass-card">
        <h3 className="chart-card__title"><Clock3 size={18} /> Recent Activity</h3>
        {recent.length === 0 ? (
          <div className="empty-state"><p>No recent activity</p></div>
        ) : (
          <div className="activity-list">
            {recent.map((item) => (
              <div
                key={item.repo_id || `${item.repo_name}-${item.timestamp}`}
                className="activity-item"
                onClick={() => item.repo_id && navigate(`/repositories/${item.repo_id}`)}
              >
                <div className="activity-item__info">
                  <GitBranch size={16} className="activity-item__icon" />
                  <span className="activity-item__name">{item.repo_name}</span>
                </div>
                <div className="activity-item__meta">
                  <span>{formatStatus(item.status)}</span>
                  {typeof item.feasibility_score === 'number' && (
                    <span className="activity-item__score">{item.feasibility_score.toFixed(1)}</span>
                  )}
                  <span>{formatWhen(item.timestamp)}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
