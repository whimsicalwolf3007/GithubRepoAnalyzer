import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileSpreadsheet, Link, Loader, CheckCircle, AlertCircle, Rocket } from 'lucide-react';
import { uploadExcel, uploadUrl, triggerBatchAnalysis } from '../api/client';
import { useNavigate } from 'react-router-dom';
import './UploadPage.css';

export default function UploadPage() {
  const [uploadResult, setUploadResult] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [urlInput, setUrlInput] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const navigate = useNavigate();

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadResult(null);

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

  const handleStartAnalysis = async () => {
    if (!uploadResult?.batch_id) return;
    setAnalyzing(true);
    try {
      await triggerBatchAnalysis(uploadResult.batch_id);
      navigate('/repositories');
    } catch (err) {
      setError('Failed to start analysis');
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="page-container">
      <h1 className="page-title"><span className="text-gradient">Upload Repositories</span></h1>
      <p className="page-subtitle">Upload an Excel file with GitHub repository links or paste URLs directly</p>

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
    </div>
  );
}
