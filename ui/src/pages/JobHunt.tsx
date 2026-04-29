import { useCallback, useEffect, useRef, useState } from 'react';
import { j } from '../api';

type InsightTagged = { id: string; text: string };

function normalizeInsightList(raw: Array<string | InsightTagged> | undefined): InsightTagged[] {
  if (!raw?.length) return [];
  return raw
    .map((x, i) => {
      if (x && typeof x === 'object' && 'text' in x) {
        const o = x as InsightTagged;
        const text = String(o.text ?? '').trim();
        const id = String(o.id ?? `r${i}`).trim() || `r${i}`;
        return text ? { id, text } : null;
      }
      const s = String(x ?? '').trim();
      return s ? { id: `r${i}`, text: s } : null;
    })
    .filter((x): x is InsightTagged => x != null);
}

const RESUME_SECTIONS = [
  'SUMMARY',
  'CORE COMPETENCIES',
  'EXPERIENCE',
  'EDUCATION',
  'CERTIFICATIONS & TRAINING',
] as const;

type Status = {
  workspace_id?: string;
  workspace_name?: string;
  active_workspace_id?: string;
  workspaces?: { id: string; name: string; resume_vault_path?: string }[];
  global_default_vault_path?: string;
  workspace_resume_vault_path?: string;
  workspace_vault_summary_path?: string;
  resume_vault_path: string;
  resume_vault_path_display?: string;
  vault_exists: boolean;
  vault_kind: 'file' | 'folder' | 'missing';
  output_path: string;
  output_path_display?: string;
  output_path_configured: boolean;
  vault_preview_files: string[];
  vault_source_count?: number;
  apply_helper_configured: boolean;
  allow_apply_subprocess: boolean;
  use_story_bank_in_draft?: boolean;
  scout_enabled?: boolean;
  user_preferences?: string[];
  archetype_hints?: string[];
  evaluation_dimension_weights?: Record<string, number>;
  use_vault_summary_for_context?: boolean;
  vault_summary_path?: string;
  vault_summary_path_display?: string;
  summary_char_count?: number;
  summary_nonempty?: boolean;
  manifest_file_count?: number;
  manifest_updated_at?: string;
  vault_summary_pending?: { path: string; display_name: string; reason: string }[];
  vault_summary_pending_count?: number;
  block_draft_when_vault_summary_stale?: boolean;
  vault_summary_config_path?: string;
  auto_refine_after_draft?: boolean;
};

type AtsFactor = {
  id: string;
  label: string;
  status: string;
  detail: string;
};

type HeuristicAts = {
  score: number;
  tier: string;
  keyword_overlap_percent: number;
  job_terms_sampled: number;
  factors: AtsFactor[];
  disclaimer: string;
};

type LlmInsightBlock = {
  technical_skills: string[];
  highlights: string[];
  gaps: Array<string | InsightTagged>;
  quick_tips: Array<string | InsightTagged>;
};

export type InsightsPayload = {
  heuristic_ats: HeuristicAts;
  llm: LlmInsightBlock | null;
};

type EvalDim = { id: string; label: string; score: number; rationale: string };
type StoryCand = {
  id?: string;
  title?: string;
  situation?: string;
  task?: string;
  action?: string;
  result?: string;
  reflection?: string;
};

export type EvaluationPayload = {
  schema_version?: number;
  overall_score: number;
  dimensions: EvalDim[];
  role_summary: string;
  cv_match: string;
  gaps: string[];
  level_strategy: string;
  comp_notes: string;
  personalization_hooks: string[];
  interview_prep: string[];
  story_candidates: StoryCand[];
  recommendation: string;
  recommendation_rationale: string;
};

type DraftRes = {
  resume_text: string;
  vault_files_used: string[];
  vault_context_source?: string;
  job_spec_preview: string;
  job_spec_used?: string;
  insights?: InsightsPayload | null;
  evaluation?: EvaluationPayload | null;
  refine_meta?: { rounds: unknown[]; stopped_reason: string } | null;
};

type ExportRes = {
  run_id: string;
  workspace_id?: string;
  stem: string;
  paths: Record<string, string | null | undefined>;
  download: Record<string, string>;
};

type PickRes = { cancelled?: boolean; path?: string; path_display?: string };

type ApplicationRow = {
  id: string;
  company: string;
  title: string;
  job_url: string;
  status: string;
  notes: string;
  run_id: string | null;
  overall_score: number | null;
  created_at?: string;
  updated_at?: string;
};

type StoryPinned = {
  id: string;
  title: string;
  situation: string;
  task: string;
  action: string;
  result: string;
  reflection: string;
  pinned_at?: string;
};

type NegTemplate = { id: string; title: string; body: string };

function factorBadgeClass(status: string): string {
  if (status === 'good') return 'text-bg-success';
  if (status === 'bad') return 'text-bg-danger';
  return 'text-bg-warning text-dark';
}

function scoreBarClass(score: number): string {
  if (score >= 82) return 'bg-success';
  if (score >= 68) return 'bg-info';
  if (score >= 52) return 'bg-warning';
  return 'bg-danger';
}

function recBadgeClass(rec: string): string {
  if (rec === 'apply') return 'text-bg-success';
  if (rec === 'skip') return 'text-bg-danger';
  return 'text-bg-warning text-dark';
}

function InsightsDashboard({
  data,
  onRefresh,
  busy,
  onQueueApplyItems,
}: {
  data: InsightsPayload;
  onRefresh: (useLlm: boolean) => void;
  busy: boolean;
  onQueueApplyItems: (items: InsightTagged[]) => void;
}) {
  const h = data.heuristic_ats;
  const llm = data.llm;
  const gaps = normalizeInsightList(llm?.gaps);
  const tips = normalizeInsightList(llm?.quick_tips);
  return (
    <div className="portico-card portico-card--lift mb-4 border border-secondary border-opacity-25">
      <div className="portico-card-header portico-card-header--accent d-flex flex-wrap align-items-center justify-content-between gap-2">
        <span>Match insights</span>
        <div className="d-flex flex-wrap gap-1">
          <button
            type="button"
            className="btn btn-outline-light btn-sm"
            disabled={busy}
            onClick={() => onRefresh(true)}
            title="Re-run heuristics + LLM"
          >
            Refresh all
          </button>
          <button
            type="button"
            className="btn btn-outline-secondary btn-sm"
            disabled={busy}
            onClick={() => onRefresh(false)}
            title="Fast heuristic-only (no extra LLM call)"
          >
            Heuristics only
          </button>
        </div>
      </div>
      <div className="portico-card-body">
        <div className="row g-4">
          <div className="col-lg-4">
            <div className="p-3 rounded h-100" style={{ background: 'rgba(99, 102, 241, 0.07)' }}>
              <div className="d-flex justify-content-between align-items-baseline mb-1">
                <span className="small text-white-50 text-uppercase" style={{ letterSpacing: '0.06em' }}>
                  ATS-style score
                </span>
                <span className="h4 mb-0 tabular-nums">{h.score}</span>
              </div>
              <div className="progress mb-2" style={{ height: 10 }}>
                <div
                  className={`progress-bar ${scoreBarClass(h.score)}`}
                  role="progressbar"
                  style={{ width: `${h.score}%` }}
                  aria-valuenow={h.score}
                  aria-valuemin={0}
                  aria-valuemax={100}
                />
              </div>
              <p className="small mb-2">
                <span className="badge bg-secondary">{h.tier}</span>{' '}
                <span className="text-secondary">Keyword signal ~{h.keyword_overlap_percent}%</span>
              </p>
              <p className="small text-secondary mb-0">{h.disclaimer}</p>
            </div>
          </div>
          <div className="col-lg-8">
            <p className="small text-white-50 mb-2">Signals checked</p>
            <ul className="list-unstyled small mb-0" style={{ lineHeight: 1.55 }}>
              {h.factors.map((f) => (
                <li key={f.id} className="mb-2 d-flex gap-2 align-items-start">
                  <span className={`badge ${factorBadgeClass(f.status)} shrink-0`}>{f.status}</span>
                  <span>
                    <strong className="text-light">{f.label}.</strong> {f.detail}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {llm ? (
          <div className="row g-4 mt-1">
            <div className="col-md-6">
              <p className="portico-section-title small mb-2">From the job — technical skills</p>
              <div className="d-flex flex-wrap gap-1">
                {llm.technical_skills.map((s) => (
                  <span key={s} className="badge rounded-pill bg-dark border border-secondary font-monospace">
                    {s}
                  </span>
                ))}
              </div>
            </div>
            <div className="col-md-6">
              <p className="portico-section-title small mb-2">Highlights vs role</p>
              <ol className="small text-secondary ps-3 mb-0" style={{ lineHeight: 1.55 }}>
                {llm.highlights.map((x, i) => (
                  <li key={i} className="mb-1">
                    {x}
                  </li>
                ))}
              </ol>
            </div>
            <div className="col-md-6">
              <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <p className="portico-section-title small mb-0 text-warning">Gaps to consider</p>
                {gaps.length ? (
                  <button
                    type="button"
                    className="btn btn-outline-success btn-sm"
                    disabled={busy}
                    onClick={() => onQueueApplyItems(gaps)}
                  >
                    Batch +
                  </button>
                ) : null}
              </div>
              <ul className="list-unstyled small text-secondary mb-0" style={{ lineHeight: 1.55 }}>
                {gaps.map((item) => (
                  <li key={item.id} className="mb-2 d-flex gap-2 align-items-start">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-success shrink-0"
                      title="Add to résumé via LLM"
                      disabled={busy}
                      onClick={() => onQueueApplyItems([item])}
                    >
                      +
                    </button>
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="col-md-6">
              <div className="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <p className="portico-section-title small mb-0 text-info">Quick wins</p>
                {tips.length ? (
                  <button
                    type="button"
                    className="btn btn-outline-success btn-sm"
                    disabled={busy}
                    onClick={() => onQueueApplyItems(tips)}
                  >
                    Batch +
                  </button>
                ) : null}
              </div>
              <ul className="list-unstyled small text-secondary mb-0" style={{ lineHeight: 1.55 }}>
                {tips.map((item) => (
                  <li key={item.id} className="mb-2 d-flex gap-2 align-items-start">
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-success shrink-0"
                      title="Add to résumé via LLM"
                      disabled={busy}
                      onClick={() => onQueueApplyItems([item])}
                    >
                      +
                    </button>
                    <span>{item.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <p className="small text-secondary mt-3 mb-0">
            AI narrative (skills / highlights / gaps) was skipped or unavailable. Use <strong>Refresh all</strong> or
            enable <strong>Include match insights</strong> when drafting.
          </p>
        )}
      </div>
    </div>
  );
}

function EvaluationPanel({
  ev,
  onPinStory,
  busy,
}: {
  ev: EvaluationPayload;
  onPinStory: (s: StoryCand) => void;
  busy: boolean;
}) {
  const [open, setOpen] = useState<Record<string, boolean>>({
    role: true,
    cv: true,
    gaps: true,
    level: false,
    comp: false,
    hooks: false,
    interview: false,
    rationale: true,
  });
  const toggle = (key: string) => setOpen((o) => ({ ...o, [key]: !o[key] }));

  return (
    <div className="portico-card portico-card--lift mb-4 border border-info border-opacity-25">
      <div className="portico-card-header portico-card-header--accent d-flex flex-wrap align-items-center justify-content-between gap-2">
        <span>Offer evaluation (structured)</span>
        <div className="d-flex align-items-center gap-2 flex-wrap">
          <span className="badge bg-dark fs-6">{ev.overall_score.toFixed(1)} / 5</span>
          <span className={`badge ${recBadgeClass(ev.recommendation)}`}>{ev.recommendation}</span>
        </div>
      </div>
      <div className="portico-card-body small">
        {ev.dimensions?.length ? (
          <div className="mb-3">
            <p className="text-white-50 mb-2">Dimensions</p>
            <div className="row g-2">
              {ev.dimensions.map((d) => (
                <div key={d.id} className="col-md-6">
                  <div className="p-2 rounded bg-dark border border-secondary border-opacity-50">
                    <div className="d-flex justify-content-between">
                      <span>{d.label}</span>
                      <span className="font-monospace">{d.score}/5</span>
                    </div>
                    <p className="text-secondary mb-0 mt-1">{d.rationale}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {(
          [
            ['role', 'Role summary', ev.role_summary],
            ['cv', 'CV match', ev.cv_match],
            ['gaps', 'Gaps & risks', (ev.gaps || []).map((x) => `• ${x}`).join('\n')],
            ['level', 'Level strategy', ev.level_strategy],
            ['comp', 'Compensation notes', ev.comp_notes],
            ['hooks', 'Personalization hooks', (ev.personalization_hooks || []).map((x) => `• ${x}`).join('\n')],
            ['interview', 'Interview prep (STAR)', (ev.interview_prep || []).map((x) => `• ${x}`).join('\n')],
            ['rationale', 'Recommendation rationale', ev.recommendation_rationale],
          ] as const
        ).map(([key, label, text]) => {
          const body = (text || '').trim();
          if (!body) return null;
          const k = key as string;
          return (
            <div key={k} className="mb-2">
              <button
                type="button"
                className="btn btn-link btn-sm text-info text-decoration-none p-0"
                onClick={() => toggle(k)}
              >
                {open[k] ? '▼' : '▶'} {label}
              </button>
              {open[k] ? (
                <pre
                  className="text-secondary mt-1 mb-0 p-2 rounded bg-black bg-opacity-25"
                  style={{ whiteSpace: 'pre-wrap' }}
                >
                  {body}
                </pre>
              ) : null}
            </div>
          );
        })}

        {ev.story_candidates?.length ? (
          <div className="mt-3">
            <p className="text-white-50 mb-2">Story candidates (pin to bank)</p>
            <ul className="list-unstyled mb-0">
              {ev.story_candidates.map((s, i) => (
                <li key={s.id || i} className="mb-2 d-flex flex-wrap gap-2 align-items-start">
                  <span className="text-secondary flex-grow-1">
                    {s.title || 'Story'} — {(s.situation || '').slice(0, 120)}
                    {(s.situation || '').length > 120 ? '…' : ''}
                  </span>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-info shrink-0"
                    disabled={busy}
                    onClick={() => onPinStory(s)}
                  >
                    Pin
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}

type TabKey = 'workspace' | 'pipeline' | 'fit' | 'stories' | 'batch' | 'scout';

export default function JobHunt() {
  const [tab, setTab] = useState<TabKey>('workspace');
  const [st, setSt] = useState<Status | null>(null);
  const [vaultInput, setVaultInput] = useState('');
  const [outputInput, setOutputInput] = useState('');
  const [prefsInput, setPrefsInput] = useState('');
  const [archetypeInput, setArchetypeInput] = useState('');
  const [jobUrl, setJobUrl] = useState('');
  const [jobPaste, setJobPaste] = useState('');
  const [resumeText, setResumeText] = useState('');
  const [basename, setBasename] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [exports, setExports] = useState<ExportRes | null>(null);
  const [insights, setInsights] = useState<InsightsPayload | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationPayload | null>(null);
  const [jobSpecUsed, setJobSpecUsed] = useState('');
  const [includeInsights, setIncludeInsights] = useState(true);
  const [includeEvaluation, setIncludeEvaluation] = useState(true);
  const [applications, setApplications] = useState<ApplicationRow[]>([]);
  const [newAppCompany, setNewAppCompany] = useState('');
  const [newAppTitle, setNewAppTitle] = useState('');
  const [newAppUrl, setNewAppUrl] = useState('');
  const [stories, setStories] = useState<StoryPinned[]>([]);
  const [batchLines, setBatchLines] = useState('');
  const [batchJobId, setBatchJobId] = useState<string | null>(null);
  const [batchDoc, setBatchDoc] = useState<Record<string, unknown> | null>(null);
  const [scoutYaml, setScoutYaml] = useState(
    'portals:\n  - https://example.com/careers\n',
  );
  const [scoutHits, setScoutHits] = useState<Array<Record<string, string>>>([]);
  const [negTemplates, setNegTemplates] = useState<NegTemplate[]>([]);
  const [negTemplateId, setNegTemplateId] = useState('');
  const [negContext, setNegContext] = useState(
    '{\n  "your_name": "",\n  "company": "",\n  "role_title": "",\n  "hiring_manager_name": ""\n}',
  );
  const [negOut, setNegOut] = useState('');
  const [vaultSummaryPathInput, setVaultSummaryPathInput] = useState('');
  const [summaryPreview, setSummaryPreview] = useState<string | null>(null);
  const [activeWsId, setActiveWsId] = useState<string | null>(null);
  const [newWsName, setNewWsName] = useState('');
  const [applyModal, setApplyModal] = useState<{
    items: InsightTagged[];
    selectedIds: Record<string, boolean>;
    mode: 'same_section' | 'per_item';
    section: string;
    polishAfter: boolean;
  } | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<{ role: string; content: string }[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatBusy, setChatBusy] = useState(false);
  const [chatAutoApply, setChatAutoApply] = useState(false);
  const [chatPendingResume, setChatPendingResume] = useState<string | null>(null);
  const prevWsRef = useRef<string | null>(null);

  const apiWs = useCallback(
    (path: string) =>
      activeWsId
        ? `${path}${path.includes('?') ? '&' : '?'}workspace_id=${encodeURIComponent(activeWsId)}`
        : path,
    [activeWsId],
  );

  const loadStatus = useCallback(() => {
    j<Status>(apiWs('/api/agents/jobshunt/status'))
      .then((s) => {
        setSt(s);
        setActiveWsId(s.workspace_id ?? null);
        setVaultInput(s.resume_vault_path);
        setOutputInput(s.output_path_configured ? s.output_path : '');
        setPrefsInput((s.user_preferences ?? []).join('\n'));
        setArchetypeInput((s.archetype_hints ?? []).join('\n'));
        setVaultSummaryPathInput(s.vault_summary_config_path ?? '');
      })
      .catch(() => setSt(null));
  }, [apiWs]);

  const loadApplications = useCallback(() => {
    j<ApplicationRow[]>(apiWs('/api/agents/jobshunt/applications'))
      .then(setApplications)
      .catch(() => setApplications([]));
  }, [apiWs]);

  const loadStories = useCallback(() => {
    j<{ pinned: StoryPinned[] }>(apiWs('/api/agents/jobshunt/story-bank'))
      .then((r) => setStories(r.pinned || []))
      .catch(() => setStories([]));
  }, [apiWs]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    const prev = prevWsRef.current;
    if (prev !== null && prev !== activeWsId) {
      setResumeText('');
      setPreview(null);
      setExports(null);
      setInsights(null);
      setEvaluation(null);
      setJobSpecUsed('');
      setBasename('');
    }
    prevWsRef.current = activeWsId;
  }, [activeWsId]);

  useEffect(() => {
    if (tab === 'pipeline') loadApplications();
  }, [tab, loadApplications]);

  useEffect(() => {
    if (tab === 'stories') {
      loadStories();
      j<{ templates: NegTemplate[] }>('/api/agents/jobshunt/negotiate/templates')
        .then((r) => {
          setNegTemplates(r.templates || []);
          if (r.templates?.[0]) setNegTemplateId(r.templates[0].id);
        })
        .catch(() => {});
    }
  }, [tab, loadStories]);

  const refreshInsights = useCallback(
    async (useLlm: boolean) => {
      const spec =
        jobSpecUsed.trim() ||
        preview ||
        jobPaste.trim() ||
        '(job spec not captured — re-run draft from URL or paste posting text)';
      if (!resumeText.trim()) return;
      setErr(null);
      setBusy('insights');
      try {
        const r = await j<InsightsPayload>(apiWs('/api/agents/jobshunt/insights'), {
          method: 'POST',
          body: JSON.stringify({
            job_spec: spec,
            resume_text: resumeText,
            use_llm: useLlm,
          }),
        });
        setInsights(r);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(null);
      }
    },
    [apiWs, jobSpecUsed, preview, jobPaste, resumeText],
  );

  const refreshEvaluation = useCallback(async () => {
    const spec =
      jobSpecUsed.trim() ||
      preview ||
        jobPaste.trim() ||
        '';
    if (!resumeText.trim() || !spec.trim()) return;
    setErr(null);
    setBusy('evaluation');
    try {
      const r = await j<EvaluationPayload>(apiWs('/api/agents/jobshunt/evaluation'), {
        method: 'POST',
        body: JSON.stringify({ job_spec: spec, resume_text: resumeText }),
      });
      setEvaluation(r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }, [apiWs, jobSpecUsed, preview, jobPaste, resumeText]);

  function openApplyModal(items: InsightTagged[]) {
    if (!items.length) return;
    const sel: Record<string, boolean> = {};
    for (const it of items) sel[it.id] = true;
    setApplyModal({
      items,
      selectedIds: sel,
      mode: 'same_section',
      section: 'SUMMARY',
      polishAfter: false,
    });
  }

  async function runRefineAts() {
    const spec = jobSpecUsed.trim() || preview || jobPaste.trim() || '';
    if (!resumeText.trim()) {
      setErr('Need résumé text to refine.');
      return;
    }
    setErr(null);
    setBusy('refine');
    try {
      const r = await j<{ resume_text: string; insights: InsightsPayload }>(
        apiWs('/api/agents/jobshunt/refine-resume'),
        {
          method: 'POST',
          body: JSON.stringify({
            job_spec: spec.slice(0, 50000),
            resume_text: resumeText,
            max_rounds: 3,
          }),
        },
      );
      setResumeText(r.resume_text);
      setInsights(r.insights);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function submitApplyModal() {
    if (!applyModal) return;
    const polish = applyModal.polishAfter;
    const items = applyModal.items.filter((it) => applyModal.selectedIds[it.id]);
    if (!items.length) {
      setErr('Select at least one item.');
      return;
    }
    const spec = jobSpecUsed.trim() || preview || jobPaste.trim() || '';
    setErr(null);
    setBusy('apply-insights');
    try {
      const r = await j<{ resume_text: string }>(apiWs('/api/agents/jobshunt/apply-insight-items'), {
        method: 'POST',
        body: JSON.stringify({
          job_spec: spec.slice(0, 50000),
          resume_text: resumeText,
          items,
          mode: applyModal.mode,
          section: applyModal.mode === 'same_section' ? applyModal.section : null,
        }),
      });
      let nextText = r.resume_text;
      if (polish) {
        const ref = await j<{ resume_text: string; insights: InsightsPayload }>(
          apiWs('/api/agents/jobshunt/refine-resume'),
          {
            method: 'POST',
            body: JSON.stringify({
              job_spec: spec.slice(0, 50000),
              resume_text: nextText,
              max_rounds: 3,
            }),
          },
        );
        nextText = ref.resume_text;
        setInsights(ref.insights);
      } else {
        try {
          const ins = await j<InsightsPayload>(apiWs('/api/agents/jobshunt/insights'), {
            method: 'POST',
            body: JSON.stringify({
              job_spec: spec.slice(0, 50000),
              resume_text: nextText,
              use_llm: includeInsights,
            }),
          });
          setInsights(ins);
        } catch {
          /* keep prior insights */
        }
      }
      setResumeText(nextText);
      setApplyModal(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function saveAutoRefineToggle(v: boolean) {
    setErr(null);
    try {
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({ auto_refine_after_draft: v }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function sendChatMessage() {
    const text = chatInput.trim();
    if (!text || chatBusy) return;
    const nextMsgs = [...chatMessages, { role: 'user', content: text }];
    setChatMessages(nextMsgs);
    setChatInput('');
    setChatBusy(true);
    setChatPendingResume(null);
    setErr(null);
    try {
      type ChatRes = {
        assistant_markdown: string;
        client_actions: Array<{ type?: string; resume_text?: string; job_text?: string; tab?: string }>;
        suggested_resume_text?: string | null;
        parse_error?: boolean;
      };
      const spec = jobSpecUsed.trim() || preview || jobPaste.trim() || '';
      const r = await j<ChatRes>(apiWs('/api/agents/jobshunt/chat'), {
        method: 'POST',
        body: JSON.stringify({
          messages: nextMsgs,
          resume_text: resumeText,
          job_spec: spec,
          last_insights: insights,
          last_evaluation: evaluation,
        }),
      });
      setChatMessages((m) => [...m, { role: 'assistant', content: r.assistant_markdown }]);
      let newResume = resumeText;
      for (const a of r.client_actions || []) {
        if (a.type === 'set_job_paste' && typeof a.job_text === 'string') setJobPaste(a.job_text);
        if (a.type === 'navigate_tab' && typeof a.tab === 'string') {
          const t = a.tab;
          if (['workspace', 'pipeline', 'fit', 'stories', 'batch', 'scout'].includes(t)) setTab(t as TabKey);
        }
        if (a.type === 'set_resume_text' && typeof a.resume_text === 'string') {
          newResume = a.resume_text;
        }
      }
      if (r.suggested_resume_text?.trim()) {
        newResume = r.suggested_resume_text;
      }
      if (newResume !== resumeText) {
        if (chatAutoApply) setResumeText(newResume);
        else setChatPendingResume(newResume);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setChatBusy(false);
    }
  }
  
  async function switchWorkspace(id: string) {
    if (!id || id === st?.active_workspace_id) return;
    setErr(null);
    setBusy('ws-switch');
    try {
      await j('/api/agents/jobshunt/workspaces/active', {
        method: 'PUT',
        body: JSON.stringify({ workspace_id: id }),
      });
      setActiveWsId(id);
      await loadStatus();
      loadApplications();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function createWorkspace() {
    setErr(null);
    setBusy('ws-create');
    try {
      const reg = await j<{ active_id: string }>('/api/agents/jobshunt/workspaces', {
        method: 'POST',
        body: JSON.stringify({ name: newWsName.trim() || 'New workspace' }),
      });
      setNewWsName('');
      setActiveWsId(reg.active_id);
      await loadStatus();
      loadApplications();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function deleteWorkspace(id: string) {
    const list = st?.workspaces ?? [];
    if (list.length <= 1) {
      setErr('Cannot delete the last workspace.');
      return;
    }
    if (id === st?.active_workspace_id) {
      setErr('Switch to another workspace before deleting this one.');
      return;
    }
    if (!confirm('Delete this workspace and all of its pipeline, batch, and story-bank data?')) return;
    setErr(null);
    setBusy('ws-delete');
    try {
      await j(`/api/agents/jobshunt/workspaces/${encodeURIComponent(id)}`, { method: 'DELETE' });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function generateFromVaultSummary() {
    const wid = activeWsId ?? st?.workspace_id;
    if (!wid) return;
    setErr(null);
    setBusy('gen-prefs');
    try {
      const r = await j<{ user_preferences: string[]; archetype_hints: string[] }>(
        `/api/agents/jobshunt/workspaces/${encodeURIComponent(wid)}/generate-preferences`,
        { method: 'POST' },
      );
      setPrefsInput((r.user_preferences ?? []).join('\n'));
      setArchetypeInput((r.archetype_hints ?? []).join('\n'));
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function savePathsFromInputs() {
    setErr(null);
    setBusy('save');
    try {
      const prefs = prefsInput
        .split('\n')
        .map((x) => x.trim())
        .filter(Boolean);
      const arch = archetypeInput
        .split('\n')
        .map((x) => x.trim())
        .filter(Boolean);
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({
          resume_vault_path: vaultInput.trim() || '~/Documents/resumes',
          output_path: outputInput.trim(),
          user_preferences: prefs,
          archetype_hints: arch,
          use_story_bank_in_draft: st?.use_story_bank_in_draft ?? false,
          scout_enabled: st?.scout_enabled ?? false,
          vault_summary_path: vaultSummaryPathInput.trim(),
          use_vault_summary_for_context: st?.use_vault_summary_for_context ?? false,
          block_draft_when_vault_summary_stale: st?.block_draft_when_vault_summary_stale ?? true,
        }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function saveCareerToggles(useBank: boolean, scout: boolean) {
    setErr(null);
    try {
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({
          use_story_bank_in_draft: useBank,
          scout_enabled: scout,
        }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function saveVaultSummaryToggles(useSummary: boolean, blockStale: boolean) {
    setErr(null);
    try {
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({
          use_vault_summary_for_context: useSummary,
          block_draft_when_vault_summary_stale: blockStale,
        }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function rescanVaultSummary(onlyPending: boolean) {
    setErr(null);
    setBusy('vault-rescan');
    try {
      await j(apiWs('/api/agents/jobshunt/vault-summary/rescan'), {
        method: 'POST',
        body: JSON.stringify({ only_pending: onlyPending }),
      });
      await loadStatus();
      setSummaryPreview(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function rebuildVaultSummary() {
    if (!confirm('Rebuild replaces the summary with one LLM condensation of the vault. Continue?')) return;
    setErr(null);
    setBusy('vault-rebuild');
    try {
      await j(apiWs('/api/agents/jobshunt/vault-summary/rebuild'), { method: 'POST' });
      await loadStatus();
      setSummaryPreview(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function loadSummaryPreview() {
    setErr(null);
    setBusy('summary-preview');
    try {
      const r = await j<{ text: string; truncated: boolean; total_chars: number }>(
        apiWs('/api/agents/jobshunt/vault-summary/preview'),
      );
      setSummaryPreview(r.text + (r.truncated ? `\n\n… (${r.total_chars} chars total, preview truncated)` : ''));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function pickVaultFolder() {
    setErr(null);
    try {
      const r = await j<PickRes>('/api/agents/jobshunt/pick-vault-folder');
      if (r.cancelled || !r.path) return;
      setVaultInput(r.path);
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({ resume_vault_path: r.path }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function pickVaultFile() {
    setErr(null);
    try {
      const r = await j<PickRes>('/api/agents/jobshunt/pick-vault-file');
      if (r.cancelled || !r.path) return;
      setVaultInput(r.path);
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({ resume_vault_path: r.path }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function pickOutputFolder() {
    setErr(null);
    try {
      const r = await j<PickRes>('/api/agents/jobshunt/pick-output-folder');
      if (r.cancelled || !r.path) return;
      setOutputInput(r.path);
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({ output_path: r.path }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function clearOutputFolder() {
    setOutputInput('');
    setErr(null);
    setBusy('save');
    try {
      await j<Status>(apiWs('/api/agents/jobshunt/settings'), {
        method: 'PUT',
        body: JSON.stringify({ output_path: '' }),
      });
      await loadStatus();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onDraft() {
    setErr(null);
    setPreview(null);
    setExports(null);
    setInsights(null);
    setEvaluation(null);
    setJobSpecUsed('');
    setBusy('draft');
    try {
      const url = jobUrl.trim();
      const paste = jobPaste.trim();
      if (url && paste) {
        setErr('Use either a job URL or pasted text, not both.');
        return;
      }
      const base =
        url
          ? { job_url: url, include_insights: includeInsights, include_evaluation: includeEvaluation }
          : paste
            ? { job_text: paste, include_insights: includeInsights, include_evaluation: includeEvaluation }
            : null;
      if (!base) {
        setErr('Enter a job URL or paste the job description.');
        return;
      }
      const r = await j<DraftRes>(apiWs('/api/agents/jobshunt/draft'), {
        method: 'POST',
        body: JSON.stringify(base),
      });
      setResumeText(r.resume_text);
      setPreview(r.job_spec_preview);
      if (r.job_spec_used) setJobSpecUsed(r.job_spec_used);
      else if (paste) setJobSpecUsed(paste);
      if (r.insights) setInsights(r.insights);
      if (r.evaluation) setEvaluation(r.evaluation);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function onExport() {
    setErr(null);
    setExports(null);
    setBusy('export');
    try {
      const r = await j<ExportRes>(apiWs('/api/agents/jobshunt/export'), {
        method: 'POST',
        body: JSON.stringify({
          resume_text: resumeText,
          basename: basename.trim() || undefined,
          write_reserialized_pdf: true,
        }),
      });
      setExports(r);
      if (evaluation?.overall_score != null && (jobUrl.trim() || jobPaste.trim())) {
        const head = (preview || jobPaste).slice(0, 800);
        const company = head.split('\n').find((x) => x.trim()) || '';
        try {
          await j<ApplicationRow>(apiWs('/api/agents/jobshunt/applications'), {
            method: 'POST',
            body: JSON.stringify({
              company: company.slice(0, 120),
              title: basename.trim() || 'Draft export',
              job_url: jobUrl.trim() || '',
              status: 'exported',
              run_id: r.run_id,
              overall_score: evaluation.overall_score,
            }),
          });
          loadApplications();
        } catch {
          /* optional link */
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function addApplication() {
    setErr(null);
    setBusy('app');
    try {
      await j(apiWs('/api/agents/jobshunt/applications'), {
        method: 'POST',
        body: JSON.stringify({
          company: newAppCompany,
          title: newAppTitle,
          job_url: newAppUrl,
          status: 'new',
        }),
      });
      setNewAppCompany('');
      setNewAppTitle('');
      setNewAppUrl('');
      loadApplications();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function pinFromEval(s: StoryCand) {
    setBusy('pin');
    try {
      await j(apiWs('/api/agents/jobshunt/story-bank/pin'), {
        method: 'POST',
        body: JSON.stringify({
          title: s.title || 'Story',
          situation: s.situation || '',
          task: s.task || '',
          action: s.action || '',
          result: s.result || '',
          reflection: s.reflection || '',
        }),
      });
      loadStories();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function runBatch() {
    const lines = batchLines.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 15);
    if (!lines.length) return;
    setErr(null);
    setBusy('batch');
    try {
      const items = lines.map((line) =>
        line.startsWith('http') ? { job_url: line } : { job_text: line },
      );
      const r = await j<{ batch_id: string }>(apiWs('/api/agents/jobshunt/batch/draft'), {
        method: 'POST',
        body: JSON.stringify({ items, include_insights: false, include_evaluation: false }),
      });
      setBatchJobId(r.batch_id);
      setBatchDoc(null);
      const poll = setInterval(async () => {
        try {
          const d = await j<Record<string, unknown>>(apiWs(`/api/agents/jobshunt/batch/${r.batch_id}`));
          setBatchDoc(d);
          if (d.status === 'done' || d.status === 'failed') {
            clearInterval(poll);
            setBusy(null);
          }
        } catch {
          clearInterval(poll);
          setBusy(null);
        }
      }, 1200);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(null);
    }
  }

  async function runScout() {
    setErr(null);
    setBusy('scout');
    setScoutHits([]);
    try {
      const r = await j<{ hits: Array<Record<string, string>> }>('/api/agents/jobshunt/scout', {
        method: 'POST',
        body: JSON.stringify({ portals_yaml: scoutYaml }),
      });
      setScoutHits(r.hits || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function personalizeNeg() {
    setErr(null);
    setBusy('neg');
    setNegOut('');
    try {
      let ctx: Record<string, unknown> = {};
      try {
        ctx = JSON.parse(negContext || '{}') as Record<string, unknown>;
      } catch {
        ctx = {};
      }
      const r = await j<{ subject?: string; body: string }>('/api/agents/jobshunt/negotiate/personalize', {
        method: 'POST',
        body: JSON.stringify({ template_id: negTemplateId, context: ctx }),
      });
      setNegOut((r.subject ? `Subject: ${r.subject}\n\n` : '') + r.body);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const vaultHint = () => {
    if (!st) return '';
    if (st.vault_kind === 'file') return 'Using a single résumé file.';
    if (st.vault_kind === 'folder') return `Folder: scanning ${st.vault_source_count ?? 0} résumé file(s).`;
    return 'Path missing or not a supported file/folder.';
  };

  const tabs: { id: TabKey; label: string }[] = [
    { id: 'workspace', label: 'Workspace' },
    { id: 'pipeline', label: 'Pipeline' },
    { id: 'fit', label: 'Fit & ATS' },
    { id: 'stories', label: 'Stories & outreach' },
    { id: 'batch', label: 'Batch' },
    { id: 'scout', label: 'Scout' },
  ];

  return (
    <>
      <header className="portico-page-header">
        <p className="portico-section-title mb-2" style={{ letterSpacing: '0.14em' }}>
          Local
        </p>
        <h1 className="portico-page-title">JobShunt</h1>
        <p className="portico-page-lead">
          Structured <strong>offer evaluation</strong>, pipeline tracking, optional story bank and batch — uses your
          configured LLM (OpenAI, Anthropic, OpenRouter, etc.).
        </p>
      </header>

      <ul className="nav nav-pills flex-wrap gap-2 mb-4">
        {tabs.map((t) => (
          <li key={t.id} className="nav-item">
            <button
              type="button"
              className={`nav-link py-1 px-3 ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          </li>
        ))}
      </ul>

      <div className="d-flex flex-wrap align-items-center gap-2 mb-4">
        <button
          type="button"
          className={`btn btn-sm ${chatOpen ? 'btn-info' : 'btn-outline-info'}`}
          onClick={() => setChatOpen((v) => !v)}
        >
          {chatOpen ? 'Hide copilot' : 'JobShunt copilot'}
        </button>
        {chatOpen ? (
          <label className="small text-secondary mb-0 d-flex align-items-center gap-2">
            <input
              type="checkbox"
              className="form-check-input mt-0"
              checked={chatAutoApply}
              onChange={(e) => setChatAutoApply(e.target.checked)}
            />
            Auto-apply résumé text from copilot
          </label>
        ) : null}
      </div>

      {tab === 'workspace' ? (
        <>
      <div className="portico-card portico-card--lift mb-4 border border-secondary border-opacity-25">
        <div className="portico-card-header portico-card-header--readable">
          <span>Workspaces</span>
        </div>
        <div className="portico-card-body">
          <p className="small text-secondary mb-3">
            Each workspace keeps its own <strong>pipeline</strong>, <strong>Fit &amp; ATS</strong> state, story bank,
            batch jobs, and <strong>vault summary</strong>. Use the same résumé vault or a different path per
            workspace — leave the vault field empty here to use the global default from config.
          </p>
          <div className="row g-2 align-items-end mb-3">
            <div className="col-md-5">
              <label className="form-label small text-white-50 mb-0">Active workspace</label>
              <select
                className="form-select form-select-sm bg-dark text-white border-secondary"
                value={st?.active_workspace_id ?? activeWsId ?? ''}
                disabled={busy !== null || !st?.workspaces?.length}
                onChange={(e) => switchWorkspace(e.target.value)}
              >
                {(st?.workspaces ?? []).map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="col-md-5">
              <label className="form-label small text-white-50 mb-0">New workspace name</label>
              <input
                className="form-control form-control-sm bg-dark text-white border-secondary"
                value={newWsName}
                onChange={(e) => setNewWsName(e.target.value)}
                placeholder="e.g. Staff eng search"
                spellCheck={false}
              />
            </div>
            <div className="col-md-2">
              <button
                type="button"
                className="btn btn-outline-primary btn-sm w-100"
                disabled={busy !== null}
                onClick={createWorkspace}
              >
                {busy === 'ws-create' ? '…' : 'Create'}
              </button>
            </div>
          </div>
          {(st?.workspaces?.length ?? 0) > 1 ? (
            <div className="mb-0">
              <p className="small text-white-50 mb-1">Other workspaces (switch away before deleting)</p>
              <ul className="list-unstyled small mb-0">
                {(st?.workspaces ?? [])
                  .filter((w) => w.id !== st?.active_workspace_id)
                  .map((w) => (
                    <li key={w.id} className="d-flex flex-wrap justify-content-between gap-2 mb-1">
                      <span className="text-secondary">
                        <strong className="text-light">{w.name}</strong>{' '}
                        <span className="font-monospace text-white-50">({w.id})</span>
                      </span>
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-danger shrink-0"
                        disabled={busy !== null}
                        onClick={() => deleteWorkspace(w.id)}
                      >
                        Delete
                      </button>
                    </li>
                  ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>
      {(st?.vault_summary_pending_count ?? 0) > 0 ? (
        <div className="alert alert-warning py-2 mb-3 small">
          <strong>Vault summary:</strong> {st?.vault_summary_pending_count} résumé file(s) are new or changed since
          the last merge. Update the summary so drafts stay accurate
          {st?.use_vault_summary_for_context ? ' (required before draft when blocking is on)' : ''}.{' '}
          <button
            type="button"
            className="btn btn-sm btn-warning ms-1 me-1"
            disabled={busy !== null}
            onClick={() => rescanVaultSummary(true)}
          >
            Update pending
          </button>
        </div>
      ) : null}
      <div className="portico-card portico-card--lift mb-4">
        <div className="portico-card-header portico-card-header--accent">
          <span>Résumé vault & export location</span>
        </div>
        <div className="portico-card-body">
          <p className="small text-secondary mb-3">
            On macOS, use Finder to pick a <strong>folder</strong> (all .txt, .md, .docx, .pdf inside are
            scanned) or a <strong>single résumé file</strong>. Paths are saved to your JobShunt config.
          </p>
          <label className="form-label small text-white-50 mb-0">Résumé vault path (folder or file)</label>
          <input
            className="form-control form-control-sm bg-dark text-white border-secondary mb-2"
            value={vaultInput}
            onChange={(e) => setVaultInput(e.target.value)}
            spellCheck={false}
            placeholder="~/Documents/resumes"
          />
          <div className="d-flex flex-wrap gap-2 mb-3">
            <button
              type="button"
              className="btn btn-outline-primary btn-sm"
              disabled={busy !== null}
              onClick={pickVaultFolder}
            >
              Choose folder…
            </button>
            <button
              type="button"
              className="btn btn-outline-primary btn-sm"
              disabled={busy !== null}
              onClick={pickVaultFile}
            >
              Choose résumé file…
            </button>
          </div>
          <label className="form-label small text-white-50 mb-0">
            Export / metadata hint folder (optional)
          </label>
          <p className="small text-secondary mb-1">
            Run artifacts still go under local JobShunt data. This path is stored for your reference and run
            metadata; leave empty for the default exports location.
          </p>
          <input
            className="form-control form-control-sm bg-dark text-white border-secondary mb-2"
            value={outputInput}
            onChange={(e) => setOutputInput(e.target.value)}
            spellCheck={false}
            placeholder="Default if empty"
          />
          <div className="d-flex flex-wrap gap-2 mb-3">
            <button
              type="button"
              className="btn btn-outline-secondary btn-sm"
              disabled={busy !== null}
              onClick={pickOutputFolder}
            >
              Choose export folder…
            </button>
            <button
              type="button"
              className="btn btn-outline-secondary btn-sm"
              disabled={busy !== null || !st?.output_path_configured}
              onClick={clearOutputFolder}
            >
              Use default location
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={busy !== null}
              onClick={savePathsFromInputs}
            >
              {busy === 'save' ? 'Saving…' : 'Save paths & career hints'}
            </button>
          </div>
          <label className="form-label small text-white-50">Career preferences (one per line)</label>
          <textarea
            className="form-control form-control-sm bg-dark text-white border-secondary mb-2"
            rows={3}
            value={prefsInput}
            onChange={(e) => setPrefsInput(e.target.value)}
            placeholder="e.g. Remote-first, no crypto, staff+ IC…"
          />
          <label className="form-label small text-white-50">Archetype / focus hints (one per line)</label>
          <textarea
            className="form-control form-control-sm bg-dark text-white border-secondary mb-2"
            rows={2}
            value={archetypeInput}
            onChange={(e) => setArchetypeInput(e.target.value)}
            placeholder="e.g. LLM platform, backend, product…"
          />
          <div className="d-flex flex-wrap align-items-center gap-2 mb-3">
            <button
              type="button"
              className="btn btn-outline-info btn-sm"
              disabled={busy !== null || !st?.summary_nonempty}
              title={
                st?.summary_nonempty
                  ? 'Overwrite both text areas using the LLM and this workspace vault summary'
                  : 'Build or rebuild the vault summary first'
              }
              onClick={generateFromVaultSummary}
            >
              {busy === 'gen-prefs' ? 'Generating…' : 'Generate from vault summary'}
            </button>
            <span className="small text-secondary">
              Fills both lists from this workspace&apos;s summary (requires a non-empty summary).
            </span>
          </div>
          <div className="form-check mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="storyBankToggle"
              checked={!!st?.use_story_bank_in_draft}
              onChange={(e) => saveCareerToggles(e.target.checked, !!st?.scout_enabled)}
            />
            <label className="form-check-label small text-secondary" htmlFor="storyBankToggle">
              Inject pinned <strong>story bank</strong> into résumé draft (bounded size).
            </label>
          </div>
          <div className="form-check mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="scoutToggle"
              checked={!!st?.scout_enabled}
              onChange={(e) => saveCareerToggles(!!st?.use_story_bank_in_draft, e.target.checked)}
            />
            <label className="form-check-label small text-secondary" htmlFor="scoutToggle">
              Allow <strong>Scout</strong> (Playwright). You must comply with site ToS — off by default.
            </label>
          </div>
          <div className="form-check mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="autoRefineToggle"
              checked={!!st?.auto_refine_after_draft}
              onChange={(e) => saveAutoRefineToggle(e.target.checked)}
            />
            <label className="form-check-label small text-secondary" htmlFor="autoRefineToggle">
              After <strong>draft</strong>, run ATS refine loop automatically (extra LLM; fixes line length, sections,
              etc.).
            </label>
          </div>
          {st ? (
            <ul className="small text-secondary mb-0" style={{ lineHeight: 1.6 }}>
              {!(st.workspace_resume_vault_path || '').trim() ? (
                <li className="text-white-50">
                  Résumé vault path for this workspace is empty — using global default:{' '}
                  <code className="text-light">{st.global_default_vault_path ?? '—'}</code>
                </li>
              ) : null}
              <li className={st.vault_exists ? '' : 'text-warning'}>
                Vault: <code className="text-light">{st.resume_vault_path_display ?? st.resume_vault_path}</code>{' '}
                — {vaultHint()}
              </li>
              <li>
                Effective export base:{' '}
                <code className="text-light">{st.output_path_display ?? st.output_path}</code>
              </li>
              <li>
                {st.vault_preview_files.length ? (
                  <>Included files (sample): {st.vault_preview_files.join(', ')}</>
                ) : (
                  <>No matching résumé files at this path (.txt, .md, .docx, .pdf).</>
                )}
              </li>
            </ul>
          ) : (
            <p className="small text-secondary mb-0">Loading…</p>
          )}
        </div>
      </div>

      <div className="portico-card portico-card--lift mb-4 border border-secondary border-opacity-25">
        <div className="portico-card-header portico-card-header--readable">
          <span>Vault summary (condensed LLM context)</span>
        </div>
        <div className="portico-card-body">
          <p className="small text-secondary mb-3">
            Build a single text summary of your vault so drafting sends <strong>less</strong> context to the model.
            A log on disk records which files were merged. When you add or edit a résumé, update the summary before
            drafting (or turn off blocking below).
          </p>
          <div className="form-check mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="vaultSummaryToggle"
              checked={!!st?.use_vault_summary_for_context}
              onChange={(e) =>
                saveVaultSummaryToggles(
                  e.target.checked,
                  !!st?.block_draft_when_vault_summary_stale,
                )
              }
            />
            <label className="form-check-label small text-secondary" htmlFor="vaultSummaryToggle">
              Use vault summary for JobShunt drafting (instead of sending all résumé files).
            </label>
          </div>
          <div className="form-check mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="vaultSummaryBlockStale"
              checked={!!st?.block_draft_when_vault_summary_stale}
              onChange={(e) =>
                saveVaultSummaryToggles(!!st?.use_vault_summary_for_context, e.target.checked)
              }
            />
            <label className="form-check-label small text-secondary" htmlFor="vaultSummaryBlockStale">
              Block draft if the vault has new/changed files not yet merged into the summary.
            </label>
          </div>
          <label className="form-label small text-white-50 mb-0">
            Custom summary file path (optional — default is under local data/jobshunt)
          </label>
          <input
            className="form-control form-control-sm bg-dark text-white border-secondary mb-2"
            value={vaultSummaryPathInput}
            onChange={(e) => setVaultSummaryPathInput(e.target.value)}
            spellCheck={false}
            placeholder="Leave empty for default"
          />
          {st ? (
            <ul className="small text-secondary mb-3" style={{ lineHeight: 1.6 }}>
              <li>
                Active file:{' '}
                <code className="text-light">{st.vault_summary_path_display ?? st.vault_summary_path}</code> —{' '}
                {st.summary_nonempty ? (
                  <>
                    {st.summary_char_count ?? 0} chars, manifest {st.manifest_file_count ?? 0} file(s)
                    {st.manifest_updated_at ? ` · updated ${st.manifest_updated_at}` : ''}
                  </>
                ) : (
                  <span className="text-warning">empty — run Rebuild or Update pending</span>
                )}
              </li>
            </ul>
          ) : null}
          <div className="d-flex flex-wrap gap-2 mb-2">
            <button
              type="button"
              className="btn btn-outline-primary btn-sm"
              disabled={busy !== null}
              onClick={() => rescanVaultSummary(true)}
            >
              {busy === 'vault-rescan' ? 'Updating…' : 'Update pending'}
            </button>
            <button
              type="button"
              className="btn btn-outline-secondary btn-sm"
              disabled={busy !== null}
              onClick={() => rescanVaultSummary(false)}
              title="Clear manifest steps and merge every vault file in order (multiple LLM calls)"
            >
              Remerge all files
            </button>
            <button
              type="button"
              className="btn btn-outline-secondary btn-sm"
              disabled={busy !== null}
              onClick={() => rebuildVaultSummary()}
            >
              {busy === 'vault-rebuild' ? 'Rebuilding…' : 'Rebuild (one-shot)'}
            </button>
            <button
              type="button"
              className="btn btn-outline-info btn-sm"
              disabled={busy !== null || !st?.summary_nonempty}
              onClick={() => loadSummaryPreview()}
            >
              {busy === 'summary-preview' ? 'Loading…' : 'Preview summary'}
            </button>
          </div>
          {summaryPreview ? (
            <pre
              className="small text-secondary mb-0 p-2 rounded bg-black bg-opacity-25"
              style={{ whiteSpace: 'pre-wrap', maxHeight: 240, overflow: 'auto' }}
            >
              {summaryPreview}
            </pre>
          ) : null}
        </div>
      </div>

      <div className="portico-card portico-card--lift mb-4">
        <div className="portico-card-header portico-card-header--accent">
          <span>Job source</span>
        </div>
        <div className="portico-card-body">
          <label className="form-label small text-white-50">Job posting URL</label>
          <input
            className="form-control form-control-sm bg-dark text-white border-secondary mb-3"
            placeholder="https://example.com/careers/…"
            value={jobUrl}
            onChange={(e) => {
              setJobUrl(e.target.value);
              if (e.target.value.trim()) setJobPaste('');
            }}
          />
          <label className="form-label small text-white-50">Or paste job text</label>
          <textarea
            className="form-control bg-dark text-white border-secondary font-monospace small"
            rows={6}
            placeholder="Paste title, company, requirements…"
            value={jobPaste}
            onChange={(e) => {
              setJobPaste(e.target.value);
              if (e.target.value.trim()) setJobUrl('');
            }}
          />
          <div className="form-check mt-2 mb-1">
            <input
              className="form-check-input"
              type="checkbox"
              id="insightToggle"
              checked={includeInsights}
              onChange={(e) => setIncludeInsights(e.target.checked)}
            />
            <label className="form-check-label small text-secondary" htmlFor="insightToggle">
              Include AI narrative match insights (skills / highlights / gaps) — extra LLM call.
            </label>
          </div>
          <div className="form-check mb-2">
            <input
              className="form-check-input"
              type="checkbox"
              id="evalToggle"
              checked={includeEvaluation}
              onChange={(e) => setIncludeEvaluation(e.target.checked)}
            />
            <label className="form-check-label small text-secondary" htmlFor="evalToggle">
              Include structured <strong>offer evaluation</strong> (1–5 + recommendation) — extra LLM call.
            </label>
          </div>
          <button
            type="button"
            className="btn btn-primary btn-sm mt-1"
            disabled={busy !== null}
            onClick={onDraft}
          >
            {busy === 'draft' ? 'Drafting…' : 'Draft résumé (LLM)'}
          </button>
        </div>
      </div>

      {preview ? (
        <div className="portico-card portico-card--lift mb-4">
          <div className="portico-card-header">
            <span>Job spec preview (ingested)</span>
          </div>
          <div className="portico-card-body">
            <pre
              className="small text-secondary mb-0"
              style={{ whiteSpace: 'pre-wrap', maxHeight: 220, overflow: 'auto' }}
            >
              {preview}
            </pre>
          </div>
        </div>
      ) : null}

      <div className="portico-card portico-card--lift mb-4">
        <div className="portico-card-header portico-card-header--accent">
          <span>Edit résumé</span>
        </div>
        <div className="portico-card-body">
          <textarea
            className="form-control bg-dark text-white border-secondary font-monospace small"
            rows={22}
            value={resumeText}
            onChange={(e) => setResumeText(e.target.value)}
            spellCheck={false}
          />
          <div className="row g-2 mt-2 align-items-end">
            <div className="col-md-6">
              <label className="form-label small text-white-50 mb-0">Optional file base name</label>
              <input
                className="form-control form-control-sm bg-dark text-white border-secondary"
                placeholder="Auto from first line if empty"
                value={basename}
                onChange={(e) => setBasename(e.target.value)}
              />
            </div>
            <div className="col-md-6 d-flex justify-content-md-end gap-2 flex-wrap">
              <button
                type="button"
                className="btn btn-outline-warning btn-sm"
                disabled={busy !== null || !resumeText.trim()}
                title="LLM + heuristic loop to improve ATS signals"
                onClick={() => runRefineAts()}
              >
                {busy === 'refine' ? 'Refining…' : 'Refine for ATS'}
              </button>
              <button
                type="button"
                className="btn btn-success btn-sm"
                disabled={busy !== null || !resumeText.trim()}
                onClick={onExport}
              >
                {busy === 'export' ? 'Exporting…' : 'Export TXT / PDF / DOCX'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {exports ? (
        <div className="portico-card portico-card--lift mb-4">
          <div className="portico-card-header">
            <span>Downloads</span>
          </div>
          <div className="portico-card-body d-flex flex-wrap gap-2">
            <a className="btn btn-outline-light btn-sm" href={exports.download.txt}>
              TXT
            </a>
            <a className="btn btn-outline-light btn-sm" href={exports.download.pdf}>
              PDF
            </a>
            <a className="btn btn-outline-light btn-sm" href={exports.download.docx}>
              DOCX
            </a>
            {exports.download.reserialized_pdf ? (
              <a className="btn btn-outline-secondary btn-sm" href={exports.download.reserialized_pdf}>
                PDF (reserialized)
              </a>
            ) : null}
          </div>
          <p className="small text-secondary px-3 pb-3 mb-0">
            Run <code>{exports.run_id}</code> — files also on disk under your JobShunt data directory.
          </p>
        </div>
      ) : null}
        </>
      ) : null}

      {tab === 'pipeline' ? (
        <div className="portico-card portico-card--lift mb-4">
          <div className="portico-card-header portico-card-header--accent">
            <span>Application pipeline</span>
          </div>
          <div className="portico-card-body">
            <div className="row g-2 mb-3">
              <div className="col-md-4">
                <input
                  className="form-control form-control-sm bg-dark text-white border-secondary"
                  placeholder="Company"
                  value={newAppCompany}
                  onChange={(e) => setNewAppCompany(e.target.value)}
                />
              </div>
              <div className="col-md-4">
                <input
                  className="form-control form-control-sm bg-dark text-white border-secondary"
                  placeholder="Title"
                  value={newAppTitle}
                  onChange={(e) => setNewAppTitle(e.target.value)}
                />
              </div>
              <div className="col-md-3">
                <input
                  className="form-control form-control-sm bg-dark text-white border-secondary"
                  placeholder="Job URL"
                  value={newAppUrl}
                  onChange={(e) => setNewAppUrl(e.target.value)}
                />
              </div>
              <div className="col-md-1">
                <button type="button" className="btn btn-primary btn-sm w-100" disabled={busy !== null} onClick={addApplication}>
                  Add
                </button>
              </div>
            </div>
            <div className="table-responsive">
              <table className="table table-sm table-dark small mb-0">
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Title</th>
                    <th>Status</th>
                    <th>Score</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {applications.map((a) => (
                    <tr key={a.id}>
                      <td>{a.company}</td>
                      <td>{a.title}</td>
                      <td>
                        <select
                          className="form-select form-select-sm bg-dark text-white border-secondary"
                          value={a.status}
                          onChange={async (e) => {
                            await j(apiWs(`/api/agents/jobshunt/applications/${a.id}/status`), {
                              method: 'PATCH',
                              body: JSON.stringify({ status: e.target.value }),
                            });
                            loadApplications();
                          }}
                        >
                          {['new', 'evaluated', 'drafted', 'exported', 'applied', 'rejected', 'archived'].map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td>{a.overall_score ?? '—'}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-link btn-sm text-danger p-0"
                          onClick={async () => {
                            await j(apiWs(`/api/agents/jobshunt/applications/${a.id}`), { method: 'DELETE' });
                            loadApplications();
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
      ) : null}

      {tab === 'fit' ? (
        <>
          <div className="d-flex flex-wrap gap-2 mb-3">
            <button
              type="button"
              className="btn btn-outline-info btn-sm"
              disabled={busy !== null || !resumeText.trim()}
              onClick={refreshEvaluation}
            >
              {busy === 'evaluation' ? 'Evaluating…' : 'Re-run offer evaluation'}
            </button>
          </div>
          {evaluation ? (
            <EvaluationPanel ev={evaluation} onPinStory={pinFromEval} busy={busy === 'pin'} />
          ) : (
            <p className="text-secondary small">Draft a résumé with evaluation enabled, or open Workspace and draft first.</p>
          )}
          {insights ? (
            <InsightsDashboard
              data={insights}
              onRefresh={refreshInsights}
              busy={busy === 'insights'}
              onQueueApplyItems={openApplyModal}
            />
          ) : (
            <p className="text-secondary small">Insights appear after draft or use Workspace to refresh from the editor.</p>
          )}
        </>
      ) : null}

      {tab === 'stories' ? (
        <>
          <div className="portico-card portico-card--lift mb-4">
            <div className="portico-card-header">Pinned stories</div>
            <div className="portico-card-body">
              <ul className="list-unstyled small mb-0">
                {stories.map((s) => (
                  <li key={s.id} className="mb-2 d-flex justify-content-between gap-2">
                    <span>
                      <strong>{s.title}</strong> — {s.situation.slice(0, 160)}
                      {s.situation.length > 160 ? '…' : ''}
                    </span>
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-danger shrink-0"
                      onClick={async () => {
                        await j(apiWs(`/api/agents/jobshunt/story-bank/${s.id}`), { method: 'DELETE' });
                        loadStories();
                      }}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ul>
              {!stories.length ? <p className="text-secondary small mb-0">No pinned stories yet — pin from Offer evaluation.</p> : null}
            </div>
          </div>
          <div className="portico-card portico-card--lift mb-4">
            <div className="portico-card-header">Outreach templates (LLM personalize — copy only)</div>
            <div className="portico-card-body small">
              <div className="row g-2">
                <div className="col-md-4">
                  <label className="form-label text-white-50">Template</label>
                  <select
                    className="form-select form-select-sm bg-dark text-white border-secondary"
                    value={negTemplateId}
                    onChange={(e) => setNegTemplateId(e.target.value)}
                  >
                    {negTemplates.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="col-md-8">
                  <label className="form-label text-white-50">Context (JSON)</label>
                  <textarea
                    className="form-control form-control-sm bg-dark text-white border-secondary font-monospace"
                    rows={5}
                    value={negContext}
                    onChange={(e) => setNegContext(e.target.value)}
                  />
                </div>
              </div>
              <button type="button" className="btn btn-primary btn-sm mt-2" disabled={busy !== null} onClick={personalizeNeg}>
                {busy === 'neg' ? '…' : 'Personalize'}
              </button>
              {negOut ? (
                <pre className="mt-3 p-2 rounded bg-black bg-opacity-50 text-secondary mb-0" style={{ whiteSpace: 'pre-wrap' }}>
                  {negOut}
                </pre>
              ) : null}
            </div>
          </div>
        </>
      ) : null}

      {tab === 'batch' ? (
        <div className="portico-card portico-card--lift mb-4">
          <div className="portico-card-header">Batch draft (max 15)</div>
          <div className="portico-card-body small">
            <p className="text-secondary">One job URL or pasted job text per line. Runs sequentially in the background.</p>
            <textarea
              className="form-control bg-dark text-white border-secondary font-monospace small"
              rows={8}
              value={batchLines}
              onChange={(e) => setBatchLines(e.target.value)}
              placeholder={'https://…\nhttps://…'}
            />
            <button type="button" className="btn btn-primary btn-sm mt-2" disabled={busy === 'batch' || busy === 'draft'} onClick={runBatch}>
              Start batch
            </button>
            {batchJobId ? (
              <p className="mt-2 mb-1">
                Job <code>{batchJobId}</code> — status:{' '}
                <strong>{(batchDoc?.status as string) || 'queued'}</strong>
              </p>
            ) : null}
            {batchDoc && Array.isArray(batchDoc.results) ? (
              <ul className="small text-secondary mb-0">
                {(batchDoc.results as Array<Record<string, unknown>>).map((r, i) => (
                  <li key={i}>
                    {(r.ok as boolean) ? 'OK — preview: ' : 'Error: '}
                    {String(r.error || r.preview || '').slice(0, 200)}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      ) : null}

      {tab === 'scout' ? (
        <div className="portico-card portico-card--lift mb-4">
          <div className="portico-card-header">Portal scout (Playwright)</div>
          <div className="portico-card-body small">
            {!st?.scout_enabled ? (
              <p className="text-warning">Enable Scout in Workspace (career settings). Requires optional `playwright` install.</p>
            ) : (
              <p className="text-secondary">
                Experimental link discovery. You are responsible for complying with each site&apos;s terms. Uses headless Chromium.
              </p>
            )}
            <textarea
              className="form-control bg-dark text-white border-secondary font-monospace small"
              rows={10}
              value={scoutYaml}
              onChange={(e) => setScoutYaml(e.target.value)}
            />
            <button type="button" className="btn btn-primary btn-sm mt-2" disabled={busy !== null} onClick={runScout}>
              {busy === 'scout' ? 'Scanning…' : 'Run scout'}
            </button>
            {scoutHits.length ? (
              <ul className="mt-3 mb-0">
                {scoutHits.map((h, i) => (
                  <li key={i}>
                    {h.url ? (
                      <a href={h.url} target="_blank" rel="noreferrer">
                        {h.label || h.url}
                      </a>
                    ) : (
                      <span className="text-warning">{h.error || 'error'}</span>
                    )}
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        </div>
      ) : null}

      {chatOpen ? (
        <div
          className="portico-card border border-info shadow-lg bg-dark"
          style={{
            position: 'fixed',
            bottom: 16,
            right: 16,
            width: 'min(420px, calc(100vw - 32px))',
            maxHeight: 'min(560px, 70vh)',
            zIndex: 1040,
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <div className="portico-card-header portico-card-header--readable py-2 d-flex justify-content-between align-items-center">
            <span className="small">Copilot</span>
            <button
              type="button"
              className="btn btn-sm btn-outline-secondary"
              aria-label="Close"
              onClick={() => setChatOpen(false)}
            >
              ×
            </button>
          </div>
          <div className="portico-card-body small flex-grow-1 overflow-auto" style={{ minHeight: 180 }}>
            {chatMessages.length === 0 ? (
              <p className="text-secondary mb-0">
                Ask about this job, résumé, or workspace. The copilot can suggest tab changes or run ATS refine when
                you ask.
              </p>
            ) : (
              chatMessages.map((m, i) => (
                <div key={i} className={`mb-3 ${m.role === 'user' ? '' : ''}`}>
                  <strong className={m.role === 'user' ? 'text-info' : 'text-white-50'}>
                    {m.role === 'user' ? 'You' : 'Copilot'}
                  </strong>
                  <pre
                    className="small mb-0 mt-1 text-secondary text-wrap font-sans"
                    style={{ whiteSpace: 'pre-wrap' }}
                  >
                    {m.content}
                  </pre>
                </div>
              ))
            )}
          </div>
          {chatPendingResume ? (
            <div className="px-3 pb-2">
              <button
                type="button"
                className="btn btn-sm btn-warning w-100"
                onClick={() => {
                  setResumeText(chatPendingResume);
                  setChatPendingResume(null);
                }}
              >
                Apply suggested résumé to editor
              </button>
            </div>
          ) : null}
          <div className="p-2 border-top border-secondary">
            <textarea
              className="form-control form-control-sm bg-dark text-white border-secondary mb-2"
              rows={2}
              placeholder="Message… (Ctrl/Cmd+Enter to send)"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={chatBusy}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  sendChatMessage();
                }
              }}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={chatBusy || !chatInput.trim()}
              onClick={() => sendChatMessage()}
            >
              {chatBusy ? '…' : 'Send'}
            </button>
          </div>
        </div>
      ) : null}

      {applyModal ? (
        <div className="modal d-block" tabIndex={-1} style={{ background: 'rgba(0,0,0,0.5)' }}>
          <div className="modal-dialog modal-dialog-centered">
            <div className="modal-content bg-dark text-white border-secondary">
              <div className="modal-header border-secondary">
                <h5 className="modal-title">Add to résumé</h5>
                <button type="button" className="btn-close btn-close-white" onClick={() => setApplyModal(null)} />
              </div>
              <div className="modal-body small">
                <p className="text-secondary">Select items, placement mode, then apply (LLM merges into your draft).</p>
                <ul className="list-unstyled mb-3">
                  {applyModal.items.map((it) => (
                    <li key={it.id} className="mb-2">
                      <label className="d-flex gap-2 align-items-start">
                        <input
                          type="checkbox"
                          className="form-check-input mt-1"
                          checked={!!applyModal.selectedIds[it.id]}
                          onChange={(e) =>
                            setApplyModal((m) =>
                              m
                                ? {
                                    ...m,
                                    selectedIds: { ...m.selectedIds, [it.id]: e.target.checked },
                                  }
                                : m,
                            )
                          }
                        />
                        <span>{it.text}</span>
                      </label>
                    </li>
                  ))}
                </ul>
                <label className="form-label text-white-50">Mode</label>
                <select
                  className="form-select form-select-sm bg-dark text-white border-secondary mb-2"
                  value={applyModal.mode}
                  onChange={(e) =>
                    setApplyModal((m) =>
                      m
                        ? {
                            ...m,
                            mode: e.target.value as 'same_section' | 'per_item',
                          }
                        : m,
                    )
                  }
                >
                  <option value="same_section">All selected → one section</option>
                  <option value="per_item">Each item → best section (LLM picks)</option>
                </select>
                {applyModal.mode === 'same_section' ? (
                  <>
                    <label className="form-label text-white-50">Section</label>
                    <select
                      className="form-select form-select-sm bg-dark text-white border-secondary mb-2"
                      value={applyModal.section}
                      onChange={(e) =>
                        setApplyModal((m) => (m ? { ...m, section: e.target.value } : m))
                      }
                    >
                      {RESUME_SECTIONS.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                    </select>
                  </>
                ) : null}
                <div className="form-check mb-2">
                  <input
                    type="checkbox"
                    className="form-check-input"
                    id="polishAfterApply"
                    checked={applyModal.polishAfter}
                    onChange={(e) =>
                      setApplyModal((m) => (m ? { ...m, polishAfter: e.target.checked } : m))
                    }
                  />
                  <label className="form-check-label text-secondary" htmlFor="polishAfterApply">
                    Polish formatting after apply (ATS refine loop)
                  </label>
                </div>
              </div>
              <div className="modal-footer border-secondary">
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => setApplyModal(null)}>
                  Cancel
                </button>
                <button
                  type="button"
                  className="btn btn-primary btn-sm"
                  disabled={busy !== null}
                  onClick={() => submitApplyModal()}
                >
                  {busy === 'apply-insights' ? 'Applying…' : 'Apply'}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {err ? (
        <div className="alert alert-danger small" role="alert" style={{ whiteSpace: 'pre-wrap' }}>
          {err}
        </div>
      ) : null}
    </>
  );
}
