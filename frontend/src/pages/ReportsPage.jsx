import { useState, useEffect } from 'react';
import { FileText, Download, FileJson, Loader, BarChart3 } from 'lucide-react';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import {
  downloadExcelReport, downloadJsonReport,
  getTechDistribution, getFeasibilityOverview
} from '../api/client';
import './ReportsPage.css';

const COLORS = ['#667eea', '#764ba2', '#00d4aa', '#fbbf24', '#ef4444', '#3b82f6', '#8b5cf6', '#ec4899'];

export default function ReportsPage() {
  const [downloading, setDownloading] = useState(null);
  const [techDist, setTechDist] = useState(null);
  const [feasibility, setFeasibility] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      const [techRes, feasRes] = await Promise.all([
        getTechDistribution(),
        getFeasibilityOverview(),
      ]);
      setTechDist(techRes.data);
      setFeasibility(feasRes.data);
    } catch (err) {
      console.error('Failed to fetch report data:', err);
    }
  };

  const handleDownloadExcel = async () => {
    setDownloading('excel');
    try {
      const res = await downloadExcelReport();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'autodev_report.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
      alert('No data available for report. Analyze repositories first.');
    } finally {
      setDownloading(null);
    }
  };

  const handleDownloadJson = async () => {
    setDownloading('json');
    try {
      const res = await downloadJsonReport();
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'autodev_report.json');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Download failed:', err);
    } finally {
      setDownloading(null);
    }
  };

  const scoreDistData = feasibility?.score_distribution || [];

  return (
    <div className="page-container">
      <h1 className="page-title"><span className="text-gradient">Reports</span></h1>
      <p className="page-subtitle">Generate and download analysis reports</p>

      {/* Download Cards */}
      <div className="reports__downloads">
        <div className="download-card glass-card animate-slide-up" onClick={handleDownloadExcel}>
          <div className="download-card__icon" style={{ background: 'rgba(0, 212, 170, 0.1)' }}>
            {downloading === 'excel' ? (
              <Loader size={28} className="dropzone__spinner" style={{ color: '#00d4aa' }} />
            ) : (
              <FileText size={28} style={{ color: '#00d4aa' }} />
            )}
          </div>
          <h3>Excel Report</h3>
          <p>Complete analysis with summary, scores, and recommendations</p>
          <span className="download-card__format">.xlsx</span>
        </div>

        <div className="download-card glass-card animate-slide-up" style={{ animationDelay: '100ms' }} onClick={handleDownloadJson}>
          <div className="download-card__icon" style={{ background: 'rgba(102, 126, 234, 0.1)' }}>
            {downloading === 'json' ? (
              <Loader size={28} className="dropzone__spinner" style={{ color: '#667eea' }} />
            ) : (
              <FileJson size={28} style={{ color: '#667eea' }} />
            )}
          </div>
          <h3>JSON Export</h3>
          <p>Raw analysis data for integration with other tools</p>
          <span className="download-card__format">.json</span>
        </div>
      </div>

      {/* Charts */}
      <div className="reports__charts">
        <div className="chart-card glass-card animate-slide-up">
          <h3 className="chart-card__title">
            <BarChart3 size={18} /> Score Distribution
          </h3>
          {scoreDistData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={scoreDistData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis dataKey="range" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <Tooltip
                  contentStyle={{
                    background: '#1a1f36', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px', color: '#f1f5f9'
                  }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                  {scoreDistData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No data available</p></div>
          )}
        </div>

        <div className="chart-card glass-card animate-slide-up">
          <h3 className="chart-card__title">
            <BarChart3 size={18} /> Framework Distribution
          </h3>
          {techDist?.frameworks?.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={techDist.frameworks.slice(0, 10)} layout="vertical" margin={{ left: 30 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 12 }} />
                <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 12 }} width={100} />
                <Tooltip
                  contentStyle={{
                    background: '#1a1f36', border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: '8px', color: '#f1f5f9'
                  }}
                />
                <Bar dataKey="count" radius={[0, 6, 6, 0]}>
                  {techDist.frameworks.slice(0, 10).map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="empty-state"><p>No framework data available</p></div>
          )}
        </div>
      </div>
    </div>
  );
}
