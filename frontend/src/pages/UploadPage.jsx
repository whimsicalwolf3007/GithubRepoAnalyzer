import { useState, useCallback, useEffect, useRef } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  Upload, FileSpreadsheet, Link, Loader, CheckCircle, AlertCircle,
  Rocket, Clock, Search, Code, Cpu, Package, XCircle
} from 'lucide-react';
import { uploadExcel, uploadUrl, triggerBatchAnalysis, getRepositories } from '../api/client';
import { useNavigate } from 'react-router-dom';
import './UploadPage.css';

const ANALYSIS_STEPS = [
  { key: 'queued', label: 'Queued', icon: Clock, description: 'Waiting to start...' },
  { key: 'scraping', label: 'Scraping', icon: Search, description: 'Fetching GitHub data...' },
  { key: 'analyzing', label: 'Analyzing', icon: Code, description: 'Analyzing tech stack...' },
  { key: 'building', label: 'Building', icon: Package, description: 'Running build simulation...' },
  { key: 'completed', label: 'Complete', icon: CheckCircle, description: 'Analysis finished!' },
];

const STEP_ORDER = { queued: 0, scraping: 1, analyzing: 2, building: 3, completed: 4, failed: 4 };

export default function UploadPage() {
  const [uploadResult, setUploadResult] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [urlInput, setUrlInput] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStatus, setAnalysisStatus] = useState(null); // null | { status, repoId, repoName }
  const [analysisFailed, setAnalysisFailed] = useState(false);
  const pollingRef = useRef(null);
  const navigate = useNavigate();

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadResult(null);
    setAnalysisStatus(null);
    setAnalysisFailed(false);

    try {
      const res = await uploadExcel(file);
      setUploadResult(res.data);
    } catch (err) {
      if (!err.response) {
        setError('Cannot connect to the backend server. Please verify VITE_API_URL or CORS settings.');
      } else {
        setError(err.response.data?.detail || 'Upload failed. Please check the file format.');
      }
    } finally {
      setUploading(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
      'application/vnd.ms-excel': ['.xls'],
    },
    maxFiles: 1,
  });

  const handleUrlSubmit = async (e) => {
    e.preventDefault();
    if (!urlInput.trim()) return;

    setUploading(true);
    setError(null);
    setUploadResult(null);
    setAnalysisStatus(null);
    setAnalysisFailed(false);

    try {
      const res = await uploadUrl(urlInput.trim());
      setUploadResult(res.data);
    } catch (err) {
      if (!err.response) {
        setError('Cannot connect to the backend server. Please verify VITE_API_URL or CORS settings.');
      } else {
        setError(err.response.data?.detail || 'Invalid GitHub URL');
      }
    } finally {
      setUploading(false);
    }
  };

  const pollBatchRepos = (batchId) => {
    // Poll the repositories list, filtering by the batch, to track progress
    const poll = async () => {
      try {
        const res = await getRepositories({ limit: 100 });
        const batchRepos = res.data.repositories.filter(
          (r) => r.batch_id === batchId
        );
        if (batchRepos.length === 0) return;

        // Find the "worst" (least progressed) status among batch repos
        const allStatuses = batchRepos.map((r) => r.status);
        const anyFailed = allStatuses.some((s) => s === 'failed');
        const allCompleted = allStatuses.every((s) => s === 'completed' || s === 'failed');

        // Find the current step to display (use the least progressed repo)
        let currentStatus = 'queued';
        for (const s of ['queued', 'scraping', 'analyzing', 'building']) {
          if (allStatuses.includes(s)) {
            currentStatus = s;
            break;
          }
        }
        if (allCompleted) currentStatus = 'completed';

        const firstRepo = batchRepos[0];
        setAnalysisStatus({
          status: currentStatus,
          repoId: firstRepo.id,
          repoName: `${firstRepo.owner}/${firstRepo.name}`,
          totalRepos: batchRepos.length,
          completedCount: batchRepos.filter((r) => r.status === 'completed').length,
          failedCount: batchRepos.filter((r) => r.status === 'failed').length,
        });

        if (allCompleted) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;

          if (anyFailed && batchRepos.length === 1) {
            setAnalysisFailed(true);
          } else {
            // Auto-navigate after a short success animation delay
            setTimeout(() => {
              if (batchRepos.length === 1) {
                navigate(`/repositories/${firstRepo.id}`);
              } else {
                navigate('/repositories');
              }
            }, 1500);
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    };

    // Initial poll immediately
    poll();
    // Then poll every 2 seconds
    pollingRef.current = setInterval(poll, 2000);
  };

  const handleStartAnalysis = async () => {
    if (!uploadResult?.batch_id) return;
    setAnalyzing(true);
    setError(null);
    setAnalysisFailed(false);
    try {
      await triggerBatchAnalysis(uploadResult.batch_id);
      // Don't navigate immediately — start polling instead
      setAnalysisStatus({ status: 'queued', repoName: '', totalRepos: uploadResult.total_repos });
      pollBatchRepos(uploadResult.batch_id);
    } catch (err) {
      setError('Failed to start analysis');
    } finally {
      setAnalyzing(false);
    }
  };

  const currentStepIndex = analysisStatus ? (STEP_ORDER[analysisStatus.status] ?? 0) : -1;

  return (
    <div className="page-container">
      <h1 className="page-title"><span className="text-gradient">Upload Repositories</span></h1>
      <p className="page-subtitle">Upload an Excel file with GitHub repository links or paste URLs directly</p>

      {/* Analysis Progress Tracker - shown after analysis is started */}
      {analysisStatus && (
        <div className="analysis-progress glass-card animate-slide-up">
          <div className="analysis-progress__header">
            {analysisStatus.status === 'completed' ? (
              <>
                <CheckCircle size={28} className="analysis-progress__icon--success" />
                <div>
                  <h3>Analysis Complete!</h3>
                  <p>Redirecting to results...</p>
                </div>
              </>
            ) : analysisFailed ? (
              <>
                <XCircle size={28} className="analysis-progress__icon--failed" />
                <div>
                  <h3>Analysis Failed</h3>
                  <p>Something went wrong during analysis.</p>
                </div>
              </>
            ) : (
              <>
                <Loader size={28} className="dropzone__spinner" />
                <div>
                  <h3>Analyzing {analysisStatus.repoName || 'repository'}...</h3>
                  <p>
                    {analysisStatus.totalRepos > 1
                      ? `${analysisStatus.completedCount || 0}/${analysisStatus.totalRepos} repositories completed`
                      : ANALYSIS_STEPS[currentStepIndex]?.description || 'Processing...'}
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Step indicators */}
          <div className="analysis-progress__steps">
            {ANALYSIS_STEPS.map((step, idx) => {
              const StepIcon = step.icon;
              let stepClass = 'analysis-progress__step';
              if (idx < currentStepIndex) stepClass += ' analysis-progress__step--done';
              else if (idx === currentStepIndex) {
                stepClass += analysisStatus.status === 'failed'
                  ? ' analysis-progress__step--failed'
                  : ' analysis-progress__step--active';
              }

              return (
                <div key={step.key} className={stepClass}>
                  <div className="analysis-progress__step-icon">
                    <StepIcon size={18} />
                  </div>
                  <span className="analysis-progress__step-label">{step.label}</span>
                  {idx < ANALYSIS_STEPS.length - 1 && (
                    <div className={`analysis-progress__connector ${idx < currentStepIndex ? 'analysis-progress__connector--done' : ''}`} />
                  )}
                </div>
              );
            })}
          </div>

          {/* Progress bar */}
          <div className="analysis-progress__bar">
            <div
              className={`analysis-progress__bar-fill ${analysisStatus.status === 'completed' ? 'analysis-progress__bar-fill--complete' : ''} ${analysisStatus.status === 'failed' ? 'analysis-progress__bar-fill--failed' : ''}`}
              style={{ width: `${Math.max(5, (currentStepIndex / (ANALYSIS_STEPS.length - 1)) * 100)}%` }}
            />
          </div>

          {analysisFailed && (
            <div className="analysis-progress__actions">
              <button className="btn btn-primary" onClick={() => { setAnalysisStatus(null); setAnalysisFailed(false); }}>
                Try Again
              </button>
              <button className="btn btn-secondary" onClick={() => navigate('/repositories')}>
                View Repositories
              </button>
            </div>
          )}
        </div>
      )}

      {/* Only show upload forms when not in analysis progress mode */}
      {!analysisStatus && (
        <>
          <div className="upload-grid">
            {/* Excel Upload */}
            <div className="upload-section glass-card animate-slide-up">
              <h2 className="upload-section__title">
                <FileSpreadsheet size={20} /> Excel File Upload
              </h2>
              <p className="upload-section__desc">
                Upload an .xlsx file containing GitHub repository URLs in any column
              </p>

              <div
                {...getRootProps()}
                className={`dropzone ${isDragActive ? 'dropzone--active' : ''} ${uploading ? 'dropzone--disabled' : ''}`}
              >
                <input {...getInputProps()} />
                {uploading ? (
                  <div className="dropzone__content">
                    <Loader size={40} className="dropzone__spinner" />
                    <p>Processing file...</p>
                  </div>
                ) : isDragActive ? (
                  <div className="dropzone__content">
                    <Upload size={40} className="dropzone__icon dropzone__icon--active" />
                    <p>Drop your Excel file here</p>
                  </div>
                ) : (
                  <div className="dropzone__content">
                    <Upload size={40} className="dropzone__icon" />
                    <p><strong>Drag & drop</strong> your Excel file here</p>
                    <span className="dropzone__hint">or click to browse (.xlsx, .xls)</span>
                  </div>
                )}
              </div>
            </div>

            {/* URL Input */}
            <div className="upload-section glass-card animate-slide-up" style={{ animationDelay: '100ms' }}>
              <h2 className="upload-section__title">
                <Link size={20} /> Quick URL Input
              </h2>
              <p className="upload-section__desc">
                Paste a GitHub repository URL for instant analysis
              </p>

              <form onSubmit={handleUrlSubmit} className="url-form">
                <div className="url-form__input-wrapper">
                  <input
                    type="text"
                    className="url-form__input"
                    placeholder="https://github.com/owner/repo"
                    value={urlInput}
                    onChange={(e) => setUrlInput(e.target.value)}
                  />
                </div>
                <button
                  type="submit"
                  className="btn btn-primary btn-lg"
                  disabled={!urlInput.trim() || uploading}
                >
                  {uploading ? <Loader size={18} className="dropzone__spinner" /> : <Upload size={18} />}
                  Submit
                </button>
              </form>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="upload-error animate-fade-in">
              <AlertCircle size={18} />
              <span>{error}</span>
            </div>
          )}

          {/* Results */}
          {uploadResult && (
            <div className="upload-result glass-card animate-slide-up">
              <div className="upload-result__header">
                <CheckCircle size={24} className="upload-result__icon" />
                <div>
                  <h3>{uploadResult.message}</h3>
                  <p>Found <strong>{uploadResult.total_repos}</strong> repositories</p>
                </div>
              </div>

              <div className="upload-result__repos">
                {uploadResult.repositories.map((url, i) => (
                  <div key={i} className="upload-result__repo-item">
                    <FileSpreadsheet size={14} />
                    <span>{url}</span>
                  </div>
                ))}
              </div>

              <div className="upload-result__actions">
                <button
                  className="btn btn-success btn-lg"
                  onClick={handleStartAnalysis}
                  disabled={analyzing}
                >
                  {analyzing ? <Loader size={18} className="dropzone__spinner" /> : <Rocket size={18} />}
                  {analyzing ? 'Starting...' : 'Start Analysis'}
                </button>
                <button className="btn btn-secondary" onClick={() => navigate('/repositories')}>
                  View Repositories
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
