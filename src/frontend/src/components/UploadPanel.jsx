import { useState, useRef } from "react";
import { Upload, Shield, MessageSquareText, BarChart3 } from "lucide-react";

const SAMPLES = [
  { name: "SME Lending",      filename: "sme_lending.csv",     desc: "18 months of loan applications, approvals & defaults across 4 regions", icon: "🏦" },
  { name: "Customer Support", filename: "customer_support.csv", desc: "26 weeks of banking support metrics — branch, phone, app & chat",       icon: "🎧" },
  { name: "Digital Banking",  filename: "digital_banking.csv",  desc: "90 days of mobile, web & ATM usage — signups, transactions & crashes",   icon: "📱" },
];

const FEATURES = [
  { icon: <MessageSquareText size={20} color="var(--primary)" />, title: "Ask in plain English", desc: "No SQL or formulas needed. Ask questions just like you'd ask a colleague." },
  { icon: <BarChart3 size={20} color="var(--primary)" />, title: "Instant visualisations", desc: "Charts and tables appear automatically, tailored to your question." },
  { icon: <Shield size={20} color="var(--primary)" />, title: "Completely private", desc: "Your data never leaves your device. Everything runs locally on your machine." },
];

export default function UploadPanel({ onUpload, onSampleLoad, loading }) {
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef();

  const handleDrop = (e) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onUpload(file);
  };

  return (
    <>
      {/* Upload zone */}
      <div
        className={`upload-card ${dragOver ? "drag-over" : ""} ${loading ? "loading" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => !loading && fileRef.current?.click()}
      >
        <input
          ref={fileRef} type="file" accept=".csv,.tsv" hidden
          onChange={(e) => e.target.files[0] && onUpload(e.target.files[0])}
        />
        {loading ? (
          <div className="upload-spinner">
            <div className="spinner" />
            <p className="upload-spinner-text">Analysing your dataset…</p>
            <p className="upload-spinner-sub">Building your data dictionary with AI</p>
          </div>
        ) : (
          <>
            <div className="upload-icon-circle"><Upload size={22} color="var(--primary)" /></div>
            <h3>Drop your CSV file here</h3>
            <p>or click anywhere to browse your files</p>
            <span className="upload-hint">Supports CSV and TSV · Any size</span>
          </>
        )}
      </div>

      {/* Sample datasets */}
      <div className="samples-section">
        <p className="samples-label">Or explore a sample dataset</p>
        <div className="sample-grid">
          {SAMPLES.map((s) => (
            <button
              key={s.filename}
              className="sample-btn"
              onClick={() => onSampleLoad(s.filename)}
              disabled={loading}
            >
              <span className="sample-emoji">{s.icon}</span>
              <span className="sample-name">{s.name}</span>
              <span className="sample-desc">{s.desc}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
