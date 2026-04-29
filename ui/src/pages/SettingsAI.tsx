import { useEffect, useState } from 'react';
import { j } from '../api';

type LLMProfileRow = {
  id: string;
  name: string;
  provider: string;
  model: string;
  api_format: string;
  base_url: string;
  has_api_key: boolean;
};

type AgentLLMBinding = {
  primary_profile_id: string | null;
  /** Saved profile UUIDs, in order; empty strings are transient UI slots before pick */
  fallback_profile_ids: string[];
};

type AI = {
  provider: string;
  base_url: string;
  has_api_key: boolean;
  model: string;
  headers: { name: string; value: string }[];
  temperature: number;
  max_tokens: number;
  openai_use_v1_prefix: boolean;
  api_format: 'openai' | 'responses' | 'path_chat' | 'auto';
  saved_profiles: LLMProfileRow[];
  active_profile_id: string | null;
  agent_llm: {
    jobshunt: AgentLLMBinding;
  };
};

type ProfileEditorPayload = {
  profile_id: string;
  profile_name: string;
  provider: string;
  base_url: string;
  has_api_key: boolean;
  model: string;
  headers: { name: string; value: string }[];
  temperature: number;
  max_tokens: number;
  openai_use_v1_prefix: boolean;
  api_format: AI['api_format'];
};

function cloneHeadersFromApi(h: unknown): { name: string; value: string }[] {
  if (!Array.isArray(h)) {
    return [];
  }
  return h.map((x) => ({
    name: typeof (x as { name?: string })?.name === 'string' ? (x as { name: string }).name : '',
    value: typeof (x as { value?: string })?.value === 'string' ? (x as { value: string }).value : '',
  }));
}

function normalizeBindingFromApi(raw: unknown): AgentLLMBinding {
  if (!raw || typeof raw !== 'object') {
    return { primary_profile_id: null, fallback_profile_ids: [] };
  }
  const o = raw as Record<string, unknown>;
  const primary = (o.primary_profile_id as string | null | undefined) ?? null;
  if (Array.isArray(o.fallback_profile_ids)) {
    return {
      primary_profile_id: primary,
      fallback_profile_ids: (o.fallback_profile_ids as unknown[]).filter(
        (x): x is string => typeof x === 'string' && x.length > 0,
      ),
    };
  }
  const legacy = o.fallback_profile_id as string | null | undefined;
  return {
    primary_profile_id: primary,
    fallback_profile_ids: legacy ? [String(legacy)] : [],
  };
}

function dedupeProfileIds(ids: string[]): string[] {
  const out: string[] = [];
  const seen = new Set<string>();
  for (const id of ids) {
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    out.push(id);
  }
  return out;
}

const providers = ['openai', 'anthropic', 'ollama', 'openai_compatible', 'openrouter'] as const;

const apiFormatOptions: { v: AI['api_format']; label: string; hint: string }[] = [
  { v: 'openai', label: 'OpenAI-style (…/v1/…/chat/completions)', hint: 'Default' },
  { v: 'responses', label: 'Responses API on long path (…/base/responses)', hint: 'Gateway model prefix + /responses' },
  { v: 'path_chat', label: 'Chat on long path (…/base/chat_completions)', hint: 'Underscored path segment' },
  { v: 'auto', label: 'Auto (from URL or probe on test)', hint: 'URL ending in /responses or /chat_completions, or try both on a prefix' },
];

function applyServer(r: AI, setS: React.Dispatch<React.SetStateAction<AI | null>>) {
  const am = (r as AI & { agent_llm?: unknown }).agent_llm || {};
  const jh = normalizeBindingFromApi(
    (am as Record<string, unknown>).jobshunt ?? (am as Record<string, unknown>).job_hunt,
  );
  setS({
    ...r,
    openai_use_v1_prefix: r.openai_use_v1_prefix !== false,
    api_format: r.api_format || 'openai',
    saved_profiles: r.saved_profiles || [],
    active_profile_id: r.active_profile_id ?? null,
    agent_llm: {
      jobshunt: jh,
    },
  });
}

export default function SettingsAI() {
  const [s, setS] = useState<AI | null>(null);
  const [key, setKey] = useState('');
  const [err, setErr] = useState('');
  const [testOk, setTestOk] = useState('');
  const [profileSaveName, setProfileSaveName] = useState('');
  const [inheritProfileId, setInheritProfileId] = useState<string | null>(null);

  useEffect(() => {
    j<AI>('/api/settings/ai')
      .then((r) => applyServer(r, setS))
      .catch((e) => setErr(String(e)));
  }, []);

  if (!s) {
    return (
      <div className="d-flex flex-column align-items-center justify-content-center py-5 px-3 text-center" style={{ minHeight: '40vh' }}>
        {err ? (
          <div className="alert alert-danger mb-0 w-100" style={{ maxWidth: 420 }}>
            {err}
          </div>
        ) : (
          <>
            <div
              className="rounded-circle mb-3"
              style={{
                width: 40,
                height: 40,
                border: '3px solid rgba(99,102,241,0.2)',
                borderTopColor: '#6366f1',
                animation: 'portico-spin 0.8s linear infinite',
              }}
              aria-hidden
            />
            <p className="text-secondary mb-0">Loading AI settings…</p>
          </>
        )}
      </div>
    );
  }

  const buildPutBody = (includeSaveName: boolean) => {
    const name = includeSaveName && profileSaveName.trim() ? profileSaveName.trim() : undefined;
    return {
      provider: s!.provider,
      base_url: s!.base_url,
      model: s!.model,
      temperature: s!.temperature,
      max_tokens: s!.max_tokens,
      headers: s!.headers,
      openai_use_v1_prefix: s!.openai_use_v1_prefix,
      api_format: s!.api_format,
      api_key: key || undefined,
      ...(name ? { save_as_profile_name: name } : {}),
      ...(inheritProfileId && !key.trim()
        ? { inherit_api_key_from_profile_id: inheritProfileId }
        : {}),
    };
  };

  const save = () => {
    if (!s) return;
    setErr('');
    setTestOk('');
    j<AI>('/api/settings/ai', {
      method: 'PUT',
      body: JSON.stringify(buildPutBody(true)),
    })
      .then((r) => {
        applyServer(r, setS);
        setKey('');
        setInheritProfileId(null);
        if (profileSaveName.trim()) setProfileSaveName('');
      })
      .catch((e) => setErr(String(e)));
  };

  const test = () => {
    if (!s) return;
    setErr('');
    setTestOk('');
    j<AI>('/api/settings/ai', { method: 'PUT', body: JSON.stringify(buildPutBody(false)) })
      .then((saved) => {
        applyServer(saved, setS);
        setKey('');
        return j<Record<string, string>>('/api/settings/ai/test', { method: 'POST' });
      })
      .then((d) => {
        const u = d.url_used ? ' URL: ' + d.url_used : '';
        setTestOk((d.message || d.status || 'OK') + u);
        j<AI>('/api/settings/ai').then((r) => applyServer(r, setS));
      })
      .catch((e) => setErr(String(e)));
  };

  const activate = (id: string) => {
    setErr('');
    j<AI>('/api/settings/ai/profiles/' + encodeURIComponent(id) + '/activate', { method: 'POST' })
      .then((r) => {
        applyServer(r, setS);
        setKey('');
        setInheritProfileId(null);
      })
      .catch((e) => setErr(String(e)));
  };

  const loadProfileFromRow = (id: string) => {
    setErr('');
    j<ProfileEditorPayload>('/api/settings/ai/profiles/' + encodeURIComponent(id) + '/editor')
      .then((r) => {
        const headers = cloneHeadersFromApi(r.headers);
        setS((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            provider: r.provider,
            base_url: r.base_url,
            model: r.model,
            headers,
            temperature: r.temperature,
            max_tokens: r.max_tokens,
            openai_use_v1_prefix: r.openai_use_v1_prefix !== false,
            api_format: (r.api_format || 'openai') as AI['api_format'],
            has_api_key: r.has_api_key,
          };
        });
        setProfileSaveName(r.profile_name);
        setInheritProfileId(r.profile_id);
        setKey('');
      })
      .catch((e) => setErr(String(e)));
  };

  const saveAgentRouting = () => {
    if (!s) return;
    if (s.saved_profiles.length > 0 && !s.agent_llm.jobshunt.primary_profile_id) {
      setErr('Choose a primary saved model for JobsHunt (or remove all saved profiles).');
      return;
    }
    setErr('');
    const agent_llm = {
      jobshunt: {
        primary_profile_id: s.agent_llm.jobshunt.primary_profile_id,
        fallback_profile_ids: dedupeProfileIds(
          s.agent_llm.jobshunt.fallback_profile_ids.filter((id) => id && id.trim()),
        ),
      },
    };
    j<AI>('/api/settings/ai', {
      method: 'PUT',
      body: JSON.stringify({ agent_llm }),
    })
      .then((r) => applyServer(r, setS))
      .catch((e) => setErr(String(e)));
  };

  const remove = (id: string) => {
    if (!confirm('Remove this saved connection from My models?')) return;
    setErr('');
    j<AI>('/api/settings/ai/profiles/' + encodeURIComponent(id), { method: 'DELETE' })
      .then((r) => {
        applyServer(r, setS);
        setKey('');
        setInheritProfileId((prev) => (prev === id ? null : prev));
      })
      .catch((e) => setErr(String(e)));
  };

  const ollama = s.provider === 'ollama';
  const useOpenPath = s.api_format === 'openai';
  const showV1 =
    (s.provider === 'openai' ||
      s.provider === 'openai_compatible' ||
      s.provider === 'openrouter' ||
      s.provider === 'ollama') && useOpenPath;
  const showPathHelp =
    s.provider === 'openai' || s.provider === 'openai_compatible' || s.provider === 'openrouter';
  const pathMode = s.api_format !== 'openai';

  const trBase = (u: string) => (u.length > 48 ? u.slice(0, 22) + '…' + u.slice(-20) : u);

  return (
    <div className="settings-ai-page">
      <header className="portico-page-header">
        <p className="portico-section-title mb-2">Connection</p>
        <h1 className="portico-page-title">OpenAI / AI</h1>
        <p className="portico-page-lead">
          Models and connection for this app. Save named profiles to switch (OpenAI-style, gateway paths,
          Anthropic, Ollama).
        </p>
      </header>

      {err && s && <div className="alert alert-danger py-2 mb-3">{err}</div>}
      {testOk && <div className="alert alert-success py-2 mb-3">{testOk}</div>}

      {s.saved_profiles.length > 0 && (
        <div className="portico-card mb-4">
          <div className="portico-card-header portico-card-header--readable">
            <span>My models (saved)</span>
          </div>
          <div className="portico-card-body">
            <p className="small text-secondary mb-3">
              Click a row to load that model into the form below (including the profile name). Change the name and save
              to add a new profile; keep the same name to update the existing one. Each entry stores the full form:
              provider, model, base URL, path format, headers, and API key on disk.
            </p>
            <div className="table-responsive portico-table-wrap">
              <table className="table table-sm portico-table align-middle mb-0 small">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Provider</th>
                    <th>Model</th>
                    <th>Path</th>
                    <th>Base URL</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {s.saved_profiles.map((p) => (
                    <tr
                      key={p.id}
                      role="button"
                      tabIndex={0}
                      className={p.id === s.active_profile_id ? 'table-info' : ''}
                      style={{
                        cursor: 'pointer',
                        ...(p.id === s.active_profile_id
                          ? { background: 'rgba(99, 102, 241, 0.08)' }
                          : {}),
                      }}
                      onClick={() => loadProfileFromRow(p.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          loadProfileFromRow(p.id);
                        }
                      }}
                    >
                      <td>
                        {p.name}
                        {p.id === s.active_profile_id && <span className="badge bg-primary ms-1">active</span>}
                      </td>
                      <td className="font-monospace">{p.provider}</td>
                      <td className="font-monospace">{p.model}</td>
                      <td className="font-monospace">{p.api_format}</td>
                      <td className="font-monospace text-truncate" style={{ maxWidth: '14rem' }} title={p.base_url}>
                        {trBase(p.base_url || '')}
                      </td>
                      <td className="text-nowrap text-end">
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-primary me-1"
                          onClick={(e) => {
                            e.stopPropagation();
                            activate(p.id);
                          }}
                        >
                          Switch
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-outline-danger"
                          onClick={(e) => {
                            e.stopPropagation();
                            remove(p.id);
                          }}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      <div className="portico-card mb-4">
        <div className="portico-card-header portico-card-header--readable">
          <span>JobsHunt model</span>
        </div>
        <div className="portico-card-body">
          <p className="small text-secondary mb-3">
            JobsHunt uses only the <strong>primary</strong> and <strong>fallback</strong> models you set here — not the
            “Switch” row highlight. The connection form below is for editing saved profiles and testing; the agent does not
            fall back to it automatically. Add fallbacks to try another profile if the primary request fails.
          </p>
          {(
            [['jobshunt', 'JobsHunt']] as const
          ).map(([agentKey, label]) => (
            <div key={agentKey} className="mb-4 pb-3 border-bottom border-light">
              <div className="row g-2 align-items-end">
                <div className="col-12 col-md-2">
                  <span className="small fw-semibold">{label}</span>
                </div>
                <div className="col-12 col-md-10">
                  <label className="form-label small text-secondary mb-1">Primary</label>
                  <select
                    className="form-select form-select-sm"
                    value={s.agent_llm[agentKey].primary_profile_id ?? ''}
                    onChange={(e) => {
                      const v = e.target.value || null;
                      setS((prev) =>
                        prev
                          ? {
                              ...prev,
                              agent_llm: {
                                ...prev.agent_llm,
                                [agentKey]: { ...prev.agent_llm[agentKey], primary_profile_id: v },
                              },
                            }
                          : prev,
                      );
                    }}
                  >
                    <option value="" disabled={s.saved_profiles.length > 0}>
                      {s.saved_profiles.length ? 'Select a saved model…' : 'Save a profile under My models first'}
                    </option>
                    {s.saved_profiles.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="row g-2 mt-2">
                <div className="col-12">
                  <label className="form-label small text-secondary mb-1">Fallbacks (order matters)</label>
                  {(s.agent_llm[agentKey].fallback_profile_ids.length
                    ? s.agent_llm[agentKey].fallback_profile_ids
                    : []
                  ).map((fid, idx) => (
                    <div key={`${agentKey}-fb-${idx}`} className="d-flex flex-wrap gap-1 align-items-center mb-1">
                      <select
                        className="form-select form-select-sm flex-grow-1"
                        style={{ minWidth: '12rem' }}
                        value={fid}
                        onChange={(e) => {
                          const v = e.target.value;
                          setS((prev) => {
                            if (!prev) return prev;
                            const next = [...prev.agent_llm[agentKey].fallback_profile_ids];
                            next[idx] = v;
                            return {
                              ...prev,
                              agent_llm: {
                                ...prev.agent_llm,
                                [agentKey]: { ...prev.agent_llm[agentKey], fallback_profile_ids: next },
                              },
                            };
                          });
                        }}
                      >
                        <option value="">Select profile…</option>
                        {s.saved_profiles.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.name}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-danger"
                        aria-label="Remove fallback"
                        onClick={() =>
                          setS((prev) => {
                            if (!prev) return prev;
                            const next = prev.agent_llm[agentKey].fallback_profile_ids.filter((_, j) => j !== idx);
                            return {
                              ...prev,
                              agent_llm: {
                                ...prev.agent_llm,
                                [agentKey]: { ...prev.agent_llm[agentKey], fallback_profile_ids: next },
                              },
                            };
                          })
                        }
                      >
                        ×
                      </button>
                    </div>
                  ))}
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary mt-1"
                    onClick={() =>
                      setS((prev) => {
                        if (!prev) return prev;
                        return {
                          ...prev,
                          agent_llm: {
                            ...prev.agent_llm,
                            [agentKey]: {
                              ...prev.agent_llm[agentKey],
                              fallback_profile_ids: [...prev.agent_llm[agentKey].fallback_profile_ids, ''],
                            },
                          },
                        };
                      })
                    }
                  >
                    + Add fallback
                  </button>
                </div>
              </div>
            </div>
          ))}
          <button type="button" className="btn btn-sm btn-primary" onClick={saveAgentRouting}>
            Save agent routing
          </button>
        </div>
      </div>

      <div className="row g-4">
        <div className="col-lg-7">
          <div className="portico-card h-100">
            <div className="portico-card-body">
              <div className="portico-border-accent border-primary mb-4" style={{ borderLeftColor: '#6366f1' }}>
                <p className="portico-section-title mb-2">Model</p>
                <div className="row g-2">
                  <div className="col-sm-5">
                    <label className="form-label small text-secondary mb-1">Provider</label>
                    <select
                      className="form-select"
                      value={s.provider}
                      onChange={(e) => {
                        const p = e.target.value;
                        setS((prev) => {
                          if (!prev) return prev;
                          let n = { ...prev, provider: p };
                          if (p === 'openrouter') {
                            if (!(prev.base_url || '').trim()) {
                              n = { ...n, base_url: 'https://openrouter.ai/api/v1', api_format: 'openai' };
                            }
                            if (!(prev.model || '').trim()) {
                              n = { ...n, model: 'openai/gpt-4o-mini' };
                            }
                          }
                          return n;
                        });
                      }}
                    >
                      {providers.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="col-sm-7">
                    <label className="form-label small text-secondary mb-1">Model</label>
                    <div className="input-group input-group">
                      <input
                        className="form-control font-monospace"
                        value={s.model}
                        onChange={(e) => setS({ ...s, model: e.target.value })}
                        placeholder="e.g. gpt-4o-mini"
                      />
                      <button
                        type="button"
                        className="btn btn-outline-secondary"
                        onClick={() =>
                          j<{ models?: string[]; message?: string }>('/api/settings/ai/models').then((d) => {
                            if (d.models && d.models[0]) setS((prev) => (prev ? { ...prev, model: d.models![0] } : prev));
                            else if (d.message) setErr(d.message);
                          })
                        }
                      >
                        List
                      </button>
                    </div>
                  </div>
                </div>
                {showPathHelp && (
                  <div className="mt-3">
                    <label className="form-label small text-secondary mb-1">API path / wire format</label>
                    <select
                      className="form-select"
                      value={s.api_format}
                      onChange={(e) => setS({ ...s, api_format: e.target.value as AI['api_format'] })}
                    >
                      {apiFormatOptions.map((o) => (
                        <option key={o.v} value={o.v}>
                          {o.label}
                        </option>
                      ))}
                    </select>
                    <p className="small text-secondary mt-1 mb-0">
                      {apiFormatOptions.find((o) => o.v === s.api_format)?.hint}
                    </p>
                  </div>
                )}
              </div>

              <div className="portico-border-accent border-info" style={{ borderLeftColor: '#0ea5e9' }}>
                <p className="portico-section-title mb-2">Endpoint</p>
                {s.provider === 'openai_compatible' && useOpenPath && (
                  <div className="alert alert-info py-2 small mb-2">
                    Set <strong>Base URL</strong> to your internal gateway. This app will <strong>not</strong> use
                    api.openai.com for this provider. If your proxy has no <code>/v1</code> in the path, turn the switch off
                    below and paste the URL up to the segment before <code>/chat/completions</code>.
                  </div>
                )}
                {s.provider === 'openrouter' && useOpenPath && (
                  <div className="alert alert-info py-2 small mb-2">
                    <strong>OpenRouter</strong> — leave Base URL empty for{' '}
                    <code className="small">https://openrouter.ai/api/v1</code>, or override. Use an API key from{' '}
                    <a href="https://openrouter.ai/" target="_blank" rel="noreferrer">
                      openrouter.ai
                    </a>
                    . Model ids look like <code className="small">openai/gpt-4o-mini</code> or{' '}
                    <code className="small">anthropic/claude-3.5-sonnet</code>. JobsHunt sends default{' '}
                    <code className="small">HTTP-Referer</code> and <code className="small">X-Title</code> unless you override them
                    in the headers table (OpenRouter recommends these; missing values sometimes cause 429). If you see 429, check
                    credits and rate limits on your OpenRouter account — the activity log may not show rejected edge requests. Models ending in `:free` share upstream quotas (Google, etc.); 429 can happen with credits still available — use a paid route or BYOK under Integrations.
                  </div>
                )}
                {showPathHelp && pathMode && (
                  <div className="alert alert-secondary py-2 small mb-2">
                    Use a <strong>base prefix</strong> that ends at your model or route (e.g. <code>https://host/…/model-name</code>).
                    The client calls <code>…/responses</code> or <code>…/chat_completions</code> on that prefix, or use a full
                    URL that already ends with one of those segments. Add routing headers in the table on the right.
                    Run <strong>Test connection</strong> once: <em>auto</em> will save a concrete mode when it finds one.
                  </div>
                )}
                <label className="form-label small text-secondary mb-1">Base URL (OpenAI API / company proxy / LiteLLM)</label>
                <input
                  className="form-control font-monospace mb-2"
                  value={s.base_url}
                  onChange={(e) => setS({ ...s, base_url: e.target.value })}
                  placeholder={
                    ollama
                      ? 'http://127.0.0.1:11434'
                      : s.provider === 'openrouter'
                        ? 'https://openrouter.ai/api/v1 (default if empty)'
                        : 'https://api.openai.com or your internal gateway URL'
                  }
                />
                {showV1 && (
                  <div className="mb-3 p-3 rounded bg-light border">
                    <div className="d-flex flex-wrap align-items-center justify-content-between gap-2">
                      <div>
                        <div className="form-check form-switch m-0">
                          <input
                            className="form-check-input"
                            type="checkbox"
                            id="v1sw"
                            checked={s.openai_use_v1_prefix}
                            onChange={(e) => setS({ ...s, openai_use_v1_prefix: e.target.checked })}
                          />
                          <label className="form-check-label" htmlFor="v1sw">
                            Use <code>/v1</code> in the API path
                          </label>
                        </div>
                        <p className="small text-secondary mb-0 mt-1">
                          <strong>On (default):</strong> base <code>https://proxy.internal/llm</code> → calls{' '}
                          <code>…/llm/v1/chat/completions</code>. <br />
                          <strong>Off (custom proxy):</strong> if your gateway serves OpenAI-style routes with no <code>/v1</code>{' '}
                          segment, turn this off.
                        </p>
                      </div>
                    </div>
                  </div>
                )}
                <label className="form-label small text-secondary mb-1">API key</label>
                <input
                  className="form-control"
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder={s.has_api_key ? '••• leave blank to keep' : ollama ? 'Usually not needed' : 'optional for some proxies'}
                  autoComplete="off"
                />
                {s.has_api_key && <div className="form-text">A key is already stored.</div>}
              </div>
            </div>
          </div>
        </div>

        <div className="col-lg-5">
          <div className="portico-card h-100">
            <div className="portico-card-body d-flex flex-column">
              <div className="portico-border-accent border-warning mb-3" style={{ borderLeftColor: '#f59e0b' }}>
                <p className="portico-section-title mb-2">Proxy headers</p>
                <p className="small text-secondary">Extra headers (auth, routing) sent with every request.</p>
                {s.headers.map((h, i) => (
                  <div className="row g-1 mb-1" key={i}>
                    <div className="col-5">
                      <input
                        className="form-control form-control-sm font-monospace"
                        placeholder="Name"
                        value={h.name}
                        onChange={(e) => {
                          const n = [...s.headers];
                          n[i] = { ...h, name: e.target.value };
                          setS({ ...s, headers: n });
                        }}
                      />
                    </div>
                    <div className="col-6">
                      <input
                        className="form-control form-control-sm font-monospace"
                        placeholder="Value"
                        value={h.value}
                        onChange={(e) => {
                          const n = [...s.headers];
                          n[i] = { ...h, value: e.target.value };
                          setS({ ...s, headers: n });
                        }}
                      />
                    </div>
                    <div className="col-1 p-0">
                      <button
                        type="button"
                        className="btn btn-sm btn-link text-danger p-0"
                        onClick={() => setS({ ...s, headers: s.headers.filter((_, j) => j !== i) })}
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))}
                <button
                  type="button"
                  className="btn btn-sm btn-outline-secondary"
                  onClick={() => setS({ ...s, headers: [...s.headers, { name: '', value: '' }] })}
                >
                  + Header
                </button>
              </div>

              <div className="portico-border-accent border-secondary mt-auto" style={{ borderLeftColor: '#94a3b8' }}>
                <p className="portico-section-title mb-2">Parameters</p>
                <div className="row g-2">
                  <div className="col-6">
                    <label className="form-label small">Temperature</label>
                    <input
                      className="form-control"
                      type="number"
                      step="0.1"
                      value={s.temperature}
                      onChange={(e) => setS({ ...s, temperature: +e.target.value })}
                    />
                  </div>
                  <div className="col-6">
                    <label className="form-label small">Max tokens</label>
                    <input
                      className="form-control"
                      type="number"
                      value={s.max_tokens}
                      onChange={(e) => setS({ ...s, max_tokens: +e.target.value })}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="portico-card mt-4">
        <div className="portico-card-body d-flex flex-wrap align-items-end gap-3">
        <div>
          <label className="form-label small text-secondary mb-0">Profile name (My models)</label>
          <input
            className="form-control font-monospace"
            style={{ minWidth: '14rem' }}
            value={profileSaveName}
            onChange={(e) => setProfileSaveName(e.target.value)}
            placeholder="e.g. work-gateway-gpt-5"
          />
          <div className="form-text">
            Click a saved profile row above to fill this name and the form. Saving with the same name updates that
            profile; a new name creates another entry.
          </div>
        </div>
        <div className="d-flex flex-wrap gap-2 align-items-center">
          <button type="button" className="btn btn-primary px-4" onClick={save}>
            Save
          </button>
          <button type="button" className="btn btn-outline-primary" onClick={test}>
            Test connection
          </button>
          <span className="text-secondary small">Test saves the form first, then checks the live endpoint (without adding a profile).</span>
        </div>
      </div>
      </div>
    </div>
  );
}
