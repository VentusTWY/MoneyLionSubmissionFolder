"use client";

import { useEffect, useState } from "react";

type RegistryModel = {
  version: string;
  created_at_utc: string | null;
  status: string | null;
  metrics: Record<string, number>;
  is_active: boolean;
  is_previous: boolean;
};

export default function AdminPanel({ actor }: { actor: string }) {
  const [models, setModels] = useState<RegistryModel[] | null>(null);
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadModels() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/admin/models");
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Unable to load model registry");
      setModels(body.models as RegistryModel[]);
    } catch (requestError) {
      setModels(null);
      setError(requestError instanceof Error ? requestError.message : "Unable to load model registry");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    let cancelled = false;
    fetch("/api/admin/models")
      .then(async (response) => {
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail ?? "Unable to load model registry");
        if (!cancelled) setModels(body.models as RegistryModel[]);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : "Unable to load model registry");
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function changeModel(action: "promote" | "rollback", version?: string) {
    if (reason.trim().length < 5) {
      setError("Enter a reason of at least five characters before changing the champion.");
      return;
    }
    const label = action === "rollback" ? "roll back to the previous approved model" : `promote ${version}`;
    if (!window.confirm(`Confirm: ${label}? This changes the production scoring model immediately.`)) return;

    setLoading(true);
    setError("");
    try {
      const path = action === "rollback" ? "/api/admin/models/rollback" : `/api/admin/models/${encodeURIComponent(version ?? "")}/promote`;
      const response = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reason: reason.trim() }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? "Model change failed");
      setReason("");
      await loadModels();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Model change failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="admin-panel" aria-label="Admin model operations">
      <div>
        <p className="eyebrow">Restricted access</p>
        <h2>Model operations</h2>
        <p>Signed in as {actor}. Use only during approved model governance or an investigated incident. Every change is recorded with your identity and reason.</p>
      </div>
      <div className="admin-controls">
        <label>Reason<input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="e.g. Approved rollback after drift investigation" /></label>
        {models ? <div className="model-list">{models.map((model) => (
          <article key={model.version} className={model.is_active ? "registry-model active" : "registry-model"}>
            <div><strong>{model.version}</strong><small>{model.is_active ? "Active champion" : model.is_previous ? "Rollback target" : model.status ?? "Registered"}</small><small>{model.created_at_utc ? new Date(model.created_at_utc).toLocaleString() : "Creation time unavailable"}</small></div>
            <div className="registry-metrics">{Object.entries(model.metrics).map(([name, value]) => <small key={name}>{name}: {value.toFixed(3)}</small>)}</div>
            {!model.is_active ? <button type="button" className="secondary-button" disabled={loading} onClick={() => changeModel("promote", model.version)}>Promote</button> : null}
          </article>
        ))}</div> : null}
        {models ? <button type="button" className="rollback-button" disabled={loading || !models.some((model) => model.is_previous)} onClick={() => changeModel("rollback")}>Roll back to previous champion</button> : null}
        {loading ? <p>Loading model registry…</p> : null}
        {error ? <p className="error-message">{error}</p> : null}
      </div>
    </section>
  );
}
