import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout/Layout';
import DashboardPage from './pages/DashboardPage';
import UploadPage from './pages/UploadPage';
import RepositoriesPage from './pages/RepositoriesPage';
import AnalysisPage from './pages/AnalysisPage';
import ReportsPage from './pages/ReportsPage';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="upload" element={<UploadPage />} />
          <Route path="repositories" element={<RepositoriesPage />} />
          <Route path="repositories/:id" element={<AnalysisPage />} />
          <Route path="reports" element={<ReportsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
