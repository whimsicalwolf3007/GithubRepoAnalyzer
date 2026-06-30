import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard, Upload, GitBranch, FileText,
  ChevronLeft, ChevronRight, Cpu
} from 'lucide-react';
import { useState } from 'react';
import './Sidebar.css';

const navItems = [
  { path: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { path: '/upload', icon: Upload, label: 'Upload' },
  { path: '/repositories', icon: GitBranch, label: 'Repositories' },
  { path: '/reports', icon: FileText, label: 'Reports' },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`}>
      <div className="sidebar__header">
        <div className="sidebar__logo">
          <div className="sidebar__logo-icon">
            <Cpu size={24} />
          </div>
          {!collapsed && (
            <div className="sidebar__logo-text">
              <span className="sidebar__brand">AutoDev</span>
              <span className="sidebar__brand-sub">Intelligence</span>
            </div>
          )}
        </div>
        <button
          className="sidebar__toggle"
          onClick={() => setCollapsed(!collapsed)}
          aria-label="Toggle sidebar"
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <nav className="sidebar__nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
            }
            title={collapsed ? item.label : undefined}
          >
            <item.icon size={20} className="sidebar__link-icon" />
            {!collapsed && <span className="sidebar__link-label">{item.label}</span>}
            {!collapsed && location.pathname === item.path && (
              <div className="sidebar__link-indicator" />
            )}
          </NavLink>
        ))}
      </nav>

      <div className="sidebar__footer">
        {!collapsed && (
          <div className="sidebar__version">
            <span>v1.0.0</span>
            <span className="sidebar__dot">●</span>
            <span>Samsung PRISM</span>
          </div>
        )}
      </div>
    </aside>
  );
}
