"use client";

import type { CSSProperties, FormEvent } from "react";
import { useEffect, useState } from "react";

type Prediction = {
  adverse_probability: number;
  risk_band: "low" | "medium" | "high";
  decision: "pass" | "review";
  model_version: string;
  feature_contract_version: string;
  request_id: string;
};

type ModelInfo = {
  model_version: string;
  feature_contract_version: string;
  decision_threshold: number;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const initialForm = {
  applicationDate: new Date().toISOString().slice(0, 10),
  loanAmount: "500",
  leadCost: "25",
    leadType: "bvMandatory",
  payFrequency: "B",
  state: "CA",
  has_clarity_report: false,
};

export default function Home() {
  const [form, setForm] = useState(initialForm);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [model, setModel] = useState<ModelInfo | null>(null);
  const [serviceReady, setServiceReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"single" | "batch">("single");
  const [batchInput, setBatchInput] = useState("[");
  const [batchResults, setBatchResults] = useState<Prediction[] | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/health/ready`).then((response) => {
        if (!response.ok) throw new Error("Service unavailable");
        return response.json();
      }),
      fetch(`${API_BASE}/v1/model`).then((response) => {
        if (!response.ok) throw new Error("Model unavailable");
        return response.json();
      }),
    ])
      .then(([, modelInfo]) => {
        setServiceReady(true);
        setModel(modelInfo);
      })
      .catch(() => setServiceReady(false));
  }, []);

  function updateField(name: string, value: string | boolean) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function batchContainsUnknowns(): boolean {
    if (mode !== "batch") return false;
    try {
      const payload = JSON.parse(batchInput);
      if (!Array.isArray(payload)) return false;
      return payload.some((p: any) => {
        const lt = (p.leadType || "").toString().toLowerCase();
        const st = (p.state || "").toString();
        return lt === "others" || st.toLowerCase() === "other";
      });
    } catch {
      return false;
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setBatchResults(null);

    try {
      if (mode === "single") {
        const response = await fetch(`${API_BASE}/v1/predict`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...form,
            applicationDate: `${form.applicationDate}T12:00:00Z`,
            loanAmount: Number(form.loanAmount),
            leadCost: Number(form.leadCost),
          }),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Prediction request failed");
        setPrediction(body);
      } else {
        // Batch mode: expect JSON array of application objects
        let payload: any;
        try {
          payload = JSON.parse(batchInput);
          if (!Array.isArray(payload)) throw new Error("Batch input must be a JSON array");
        } catch (parseErr) {
          throw new Error("Invalid JSON batch input");
        }
        const response = await fetch(`${API_BASE}/v1/predict/batch`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload.map((p: any) => ({
            ...p,
            applicationDate: p.applicationDate ? `${p.applicationDate}T12:00:00Z` : `${form.applicationDate}T12:00:00Z`,
            loanAmount: Number(p.loanAmount ?? form.loanAmount),
            leadCost: Number(p.leadCost ?? form.leadCost),
          }))),
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Batch prediction request failed");
        if (!Array.isArray(body)) throw new Error("Batch response malformed");
        setBatchResults(body as Prediction[]);
        setPrediction(body[0] ?? null);
      }
    } catch (requestError) {
      setPrediction(null);
      setBatchResults(null);
      setError(requestError instanceof Error ? requestError.message : "Prediction request failed");
    } finally {
      setLoading(false);
    }
  }

  const score = prediction ? Math.round(prediction.adverse_probability * 1000) / 10 : null;
  const scoreStyle = prediction
    ? ({ "--score": prediction.adverse_probability } as CSSProperties)
    : undefined;

  return (
    <main>
      <header className="topbar">
        <a className="brand" href="#top" aria-label="LoanRiskCalculator home">
          <span className="brand-mark">LRC</span>
          <span><strong>LoanRiskCalculator</strong><small>Decision intelligence</small></span>
        </a>
        <div className="service-status" aria-live="polite">
          <span className={serviceReady ? "status-dot ready" : "status-dot"} />
          {serviceReady ? "Scoring service online" : "Scoring service offline"}
        </div>
      </header>

      <section className="hero" id="top">
        <div>
          <p className="eyebrow">Pre-pricing risk assessment</p>
          <h1>Make the next lending decision with clarity.</h1>
          <p className="hero-copy">
            Estimate adverse repayment risk using the currently promoted model,
            with a traceable version and decision on every request.
          </p>
        </div>
        <div className="model-card">
          <span>Active model</span>
          <strong>{model?.model_version ?? "Waiting for service"}</strong>
          <div><small>Contract</small><b>{model?.feature_contract_version ?? "—"}</b></div>
          <div><small>Review threshold</small><b>{model ? `${Math.round(model.decision_threshold * 100)}%` : "—"}</b></div>
        </div>
      </section>

      <section className="workspace" aria-label="Loan risk workspace">
        <form className="application-form" onSubmit={submit}>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <button type="button" className={mode === "single" ? "active" : ""} onClick={() => setMode("single")}>Single</button>
            <button type="button" className={mode === "batch" ? "active" : ""} onClick={() => setMode("batch")}>Batch</button>
          </div>
          <div className="section-heading">
            <span>01</span>
            <div><h2>Application details</h2><p>Enter information available before pricing.</p></div>
          </div>

          {mode === "single" ? (
            <div className="form-grid">
            <label>
              Application date
              <input type="date" required value={form.applicationDate} onChange={(event) => updateField("applicationDate", event.target.value)} />
            </label>
            <label>
              Loan amount
              <span className="money-input"><span>$</span><input type="number" min="1" step="1" required value={form.loanAmount} onChange={(event) => updateField("loanAmount", event.target.value)} /></span>
            </label>
            <label>
              Lead acquisition cost
              <span className="money-input"><span>$</span><input type="number" min="0" step="0.01" required value={form.leadCost} onChange={(event) => updateField("leadCost", event.target.value)} /></span>
            </label>
            <label>
              Lead type
              <select value={form.leadType} onChange={(event) => updateField("leadType", event.target.value)}>
                <option value="bvMandatory">Bank verification mandatory</option>
                <option value="lead">Standard lead</option>
                <option value="organic">Organic</option>
                <option value="prescreen">Pre-screen</option>
                <option value="others">Others (new)</option>
              </select>
            </label>
            <label>
              Pay frequency
              <select value={form.payFrequency} onChange={(event) => updateField("payFrequency", event.target.value)}>
                <option value="B">Biweekly</option><option value="W">Weekly</option><option value="S">Semi-monthly</option><option value="M">Monthly</option>
              </select>
            </label>
            <label>
              State
              <select value={form.state} onChange={(event) => updateField("state", event.target.value)}>
                <option value="">Select state</option>
                <option value="AL">Alabama</option>
                <option value="AK">Alaska</option>
                <option value="AZ">Arizona</option>
                <option value="AR">Arkansas</option>
                <option value="CA">California</option>
                <option value="CO">Colorado</option>
                <option value="CT">Connecticut</option>
                <option value="DE">Delaware</option>
                <option value="FL">Florida</option>
                <option value="GA">Georgia</option>
                <option value="HI">Hawaii</option>
                <option value="ID">Idaho</option>
                <option value="IL">Illinois</option>
                <option value="IN">Indiana</option>
                <option value="IA">Iowa</option>
                <option value="KS">Kansas</option>
                <option value="KY">Kentucky</option>
                <option value="LA">Louisiana</option>
                <option value="ME">Maine</option>
                <option value="MD">Maryland</option>
                <option value="MA">Massachusetts</option>
                <option value="MI">Michigan</option>
                <option value="MN">Minnesota</option>
                <option value="MS">Mississippi</option>
                <option value="MO">Missouri</option>
                <option value="MT">Montana</option>
                <option value="NE">Nebraska</option>
                <option value="NV">Nevada</option>
                <option value="NH">New Hampshire</option>
                <option value="NJ">New Jersey</option>
                <option value="NM">New Mexico</option>
                <option value="NY">New York</option>
                <option value="NC">North Carolina</option>
                <option value="ND">North Dakota</option>
                <option value="OH">Ohio</option>
                <option value="OK">Oklahoma</option>
                <option value="OR">Oregon</option>
                <option value="PA">Pennsylvania</option>
                <option value="RI">Rhode Island</option>
                <option value="SC">South Carolina</option>
                <option value="SD">South Dakota</option>
                <option value="TN">Tennessee</option>
                <option value="TX">Texas</option>
                <option value="UT">Utah</option>
                <option value="VT">Vermont</option>
                <option value="VA">Virginia</option>
                <option value="WA">Washington</option>
                <option value="WV">West Virginia</option>
                <option value="WI">Wisconsin</option>
                <option value="WY">Wyoming</option>
                <option value="Other">Other (new)</option>
              </select>
            </label>
          </div>
          ) : (
            <div>
              <label>
                Batch JSON input
                <textarea value={batchInput} onChange={(e) => setBatchInput(e.target.value)} rows={10} style={{ width: "100%", fontFamily: "monospace" }} />
              </label>
              <p><small>Provide a JSON array of application objects. Missing fields will use the single-form defaults.</small></p>
            </div>
          )}
            {/* Show warning when unknown categories are used */}
            {((mode === "single" && (form.leadType === "others" || (form.state || "").toString().toLowerCase() === "other")) || batchContainsUnknowns()) && (
              <p className="warning-message" style={{ color: "#b04", marginTop: 8 }}>
                Warning: one or more fields use an unknown category ("Others" or "Other"). These indicate new or unmapped data and may produce unexpected results.
              </p>
            )}
          </div>

          <label className="check-row">
            <input type="checkbox" checked={form.has_clarity_report} onChange={(event) => updateField("has_clarity_report", event.target.checked)} />
            <span><strong>Clarity report available</strong><small>Include the presence signal in this assessment.</small></span>
          </label>

          <button type="submit" disabled={loading || !serviceReady}>
            {loading ? "Calculating risk…" : "Run risk assessment"}<span aria-hidden="true">→</span>
          </button>
          {error && <p className="error-message">{error}</p>}
        </form>

        <aside className="result-panel" aria-live="polite">
          <div className="section-heading inverse">
            <span>02</span>
            <div><h2>Decision result</h2><p>Model score and operational action.</p></div>
          </div>

          {prediction ? (
            <div className="result-content">
              <div className={`score-orbit ${prediction.risk_band}`} style={scoreStyle}>
                <div><strong>{score}%</strong><span>adverse probability</span></div>
              </div>
              <div className="decision-row">
                <div><span>Risk band</span><strong className={`risk-label ${prediction.risk_band}`}>{prediction.risk_band}</strong></div>
                <div><span>Recommended action</span><strong>{prediction.decision}</strong></div>
              </div>
              <div className="explanation">
                <span>Decision context</span>
                <p>{prediction.decision === "review" ? "This score meets or exceeds the review threshold. Route the application for an approved manual assessment." : "This score is below the configured review threshold. Continue through the standard decision workflow."}</p>
              </div>
              <dl className="trace-details">
                <div><dt>Model version</dt><dd>{prediction.model_version}</dd></div>
                <div><dt>Request ID</dt><dd>{prediction.request_id}</dd></div>
              </dl>
            </div>
          ) : (
            <div className="empty-result">
              <div className="empty-orbit"><span>—</span></div>
              <h3>Ready when you are</h3>
              <p>Complete the application details to generate a versioned risk assessment.</p>
              <ul><li>Probability and risk band</li><li>Pass or review decision</li><li>Traceable request and model version</li></ul>
            </div>
          )}
        </aside>
      </section>

      <footer>
        <span>LoanRiskCalculator · Model-assisted decision support</span>
        <span>Predictions require approved human and policy oversight.</span>
      </footer>
    </main>
  );
}
