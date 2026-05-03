"use strict";

const state = {
  records: [],
  filtered: [],
  index: 0,
  filter: { source: "", status: "unlabelled", script: "", verdict: "" },
  evidenceExpanded: false,
  lastAction: null,
};

const els = {
  card: document.getElementById("card"),
  position: document.getElementById("position"),
  labelledCount: document.getElementById("labelled-count"),
  distribution: document.getElementById("distribution"),
  filterSource: document.getElementById("filter-source"),
  filterStatus: document.getElementById("filter-status"),
  filterScript: document.getElementById("filter-script"),
  filterVerdict: document.getElementById("filter-verdict"),
  reload: document.getElementById("btn-reload"),
  verdicts: document.getElementById("verdicts"),
  notesRow: document.getElementById("notes-row"),
  notes: document.getElementById("notes"),
  hints: document.getElementById("hints"),
};

const KEY_TO_VERDICT = {
  1: "false",
  2: "misleading",
  3: "partly_false",
  4: "true",
  5: "unverified",
  6: "satire",
  7: "needs_review",
  8: "not_fact_check",
  0: "__delete__",
  f: "false",
  m: "misleading",
  p: "partly_false",
  t: "true",
  v: "unverified",
  s: "satire",
  r: "needs_review",
  x: "not_fact_check",
};

const REAL_AUTO_VERDICTS = new Set([
  "false",
  "misleading",
  "partly_false",
  "true",
  "unverified",
  "satire",
]);

const VERDICT_SEG_CLASS = {
  false: "seg-false",
  misleading: "seg-misleading",
  partly_false: "seg-partly",
  true: "seg-true",
  unverified: "seg-unverified",
  satire: "seg-satire",
  needs_review: "seg-review",
  not_fact_check: "seg-not-fc",
};

const EVIDENCE_COLLAPSE_CHARS = 1500;

async function fetchRecords() {
  const res = await fetch("/api/records");
  if (!res.ok) throw new Error(`/api/records: ${res.status}`);
  const data = await res.json();
  return data.records;
}

function applyFilters() {
  const { source, status, script, verdict } = state.filter;
  state.filtered = state.records.filter((r) => {
    if (source && r.source_id !== source) return false;
    if (script && r.claim_text_script !== script) return false;
    if (status === "unlabelled" && r.manual_label) return false;
    if (status === "labelled" && !r.manual_label) return false;
    if (status === "unknown" && r.verdict_canonical !== "unknown") return false;
    if (verdict) {
      if (!r.manual_label || r.manual_label.verdict !== verdict) return false;
    }
    return true;
  });
  if (state.index >= state.filtered.length) state.index = 0;
}

function populateSourceFilter() {
  const sources = [...new Set(state.records.map((r) => r.source_id))].sort();
  const current = state.filter.source;
  const totalLabelled = state.records.filter((r) => r.manual_label).length;
  els.filterSource.innerHTML =
    `<option value="">all (${totalLabelled}/${state.records.length})</option>` +
    sources
      .map((s) => {
        const recs = state.records.filter((r) => r.source_id === s);
        const labelled = recs.filter((r) => r.manual_label).length;
        const sel = s === current ? " selected" : "";
        return `<option value="${s}"${sel}>${s} (${labelled}/${recs.length})</option>`;
      })
      .join("");
}

function renderDistribution() {
  const labelled = state.records.filter((r) => r.manual_label);
  const total = labelled.length;
  if (!total) {
    els.distribution.innerHTML = `<span class="muted">no labels yet</span>`;
    return;
  }
  const counts = {};
  for (const r of labelled) {
    const v = r.manual_label.verdict;
    counts[v] = (counts[v] || 0) + 1;
  }
  const order = [
    "false",
    "misleading",
    "partly_false",
    "true",
    "unverified",
    "satire",
    "needs_review",
    "not_fact_check",
  ];
  const segments = order
    .filter((v) => counts[v])
    .map((v) => {
      const pct = ((counts[v] / total) * 100).toFixed(2);
      const cls = VERDICT_SEG_CLASS[v];
      return `<span class="${cls}" style="width:${pct}%" title="${v}: ${counts[v]}"></span>`;
    })
    .join("");
  const top = order
    .filter((v) => counts[v])
    .slice(0, 3)
    .map((v) => `${v.replace(/_/g, " ")[0]}${counts[v]}`)
    .join(" ");
  els.distribution.innerHTML = `
    <div class="bar">${segments}</div>
    <span class="legend">${top}</span>
  `;
}

function escapeHtml(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function suggestedVerdict(r) {
  if (r.manual_label) return r.manual_label.verdict;
  if (REAL_AUTO_VERDICTS.has(r.verdict_canonical)) return r.verdict_canonical;
  return null;
}

function render() {
  els.position.textContent = `${state.filtered.length === 0 ? 0 : state.index + 1} / ${state.filtered.length}`;
  const labelled = state.records.filter((r) => r.manual_label).length;
  els.labelledCount.textContent = `${labelled} labelled`;

  if (state.filtered.length === 0) {
    els.card.innerHTML = `<div class="empty">No records match the current filter.</div>`;
    els.verdicts.hidden = true;
    els.notesRow.hidden = true;
    els.hints.hidden = true;
    return;
  }

  const r = state.filtered[state.index];
  const manual = r.manual_label;
  const suggestion = suggestedVerdict(r);
  const publishedShort = r.published_date ? r.published_date.slice(0, 10) : "?";
  const evidence = r.evidence_text || "";
  const isLong = evidence.length > EVIDENCE_COLLAPSE_CHARS;
  const expanded = state.evidenceExpanded;
  const evidenceShown =
    isLong && !expanded ? evidence.slice(0, EVIDENCE_COLLAPSE_CHARS) + "…" : evidence;
  const split = evidence.length > 400;

  const autoSuggestPill =
    !manual && REAL_AUTO_VERDICTS.has(r.verdict_canonical)
      ? `<span class="pill suggest" title="press Enter to accept">↵ ${escapeHtml(r.verdict_canonical)}</span>`
      : "";

  const toggleHtml = isLong
    ? `<button type="button" class="evidence-toggle" id="evidence-toggle">
         ${expanded ? "show less" : `show full (${evidence.length.toLocaleString()} chars)`}
       </button>`
    : "";

  els.card.innerHTML = `
    <h1 lang="ml">${escapeHtml(r.title)}</h1>
    <div class="meta">
      <span class="pill">${escapeHtml(r.source_id)}</span>
      <span class="pill">${escapeHtml(r.language)} / ${escapeHtml(r.claim_text_script)}</span>
      <span class="pill">extractor: ${escapeHtml(r.extractor_used)}</span>
      <span class="pill current">auto: ${escapeHtml(r.verdict_canonical)} (${escapeHtml(r.verdict_raw || "—")})</span>
      ${manual ? `<span class="pill manual">manual: ${escapeHtml(manual.verdict)}</span>` : autoSuggestPill}
      <span>${escapeHtml(publishedShort)}</span>
      <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">open ↗</a>
    </div>
    <div class="card-body${split ? " split" : ""}">
      <section class="block claim">
        <div class="label">claim</div>
        <div class="body" lang="ml">${escapeHtml(r.claim_text)}</div>
      </section>
      <section class="block">
        <div class="label">evidence (${evidence.length.toLocaleString()} chars)</div>
        <div class="body evidence${expanded ? " collapsed" : ""}" lang="ml">${escapeHtml(evidenceShown)}</div>
        ${toggleHtml}
      </section>
    </div>
  `;

  if (isLong) {
    document
      .getElementById("evidence-toggle")
      .addEventListener("click", toggleEvidence);
  }

  els.verdicts.hidden = false;
  els.notesRow.hidden = false;
  els.hints.hidden = false;
  els.notes.value = manual && manual.notes ? manual.notes : "";

  for (const btn of els.verdicts.querySelectorAll("button")) {
    const v = btn.dataset.verdict;
    btn.classList.toggle("active", manual && v === manual.verdict);
    btn.classList.toggle("suggested", !manual && v === suggestion);
  }
}

function toggleEvidence() {
  state.evidenceExpanded = !state.evidenceExpanded;
  render();
}

function showToast(msg) {
  let t = document.querySelector(".toast");
  if (!t) {
    t = document.createElement("div");
    t.className = "toast";
    document.body.appendChild(t);
  }
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(showToast._timer);
  showToast._timer = setTimeout(() => t.classList.remove("show"), 1400);
}

async function applyVerdict(verdict, opts = {}) {
  if (state.filtered.length === 0) return;
  const r = state.filtered[state.index];
  const recordId = r.record_id;
  const prev = r.manual_label ? { ...r.manual_label } : null;

  if (verdict === "__delete__") {
    if (!r.manual_label) return;
    const res = await fetch(`/api/labels/${encodeURIComponent(recordId)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      showToast(`delete failed: ${res.status}`);
      return;
    }
    r.manual_label = null;
    if (!opts.silent) {
      state.lastAction = { recordId, prev, next: null };
      showToast("cleared");
    }
    populateSourceFilter();
    renderDistribution();
    render();
    return;
  }

  const notes = els.notes.value.trim() || null;
  const res = await fetch("/api/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ record_id: recordId, verdict, notes }),
  });
  if (!res.ok) {
    showToast(`save failed: ${res.status}`);
    return;
  }
  const data = await res.json();
  r.manual_label = data.label;
  if (!opts.silent) {
    state.lastAction = { recordId, prev, next: { ...data.label } };
    showToast(`saved: ${verdict}`);
  }
  populateSourceFilter();
  renderDistribution();
  render();
  if (!opts.noAdvance) advance(1);
}

async function undoLastAction() {
  const action = state.lastAction;
  if (!action) {
    showToast("nothing to undo");
    return;
  }
  const target = state.records.find((r) => r.record_id === action.recordId);
  if (!target) {
    showToast("undo target missing");
    state.lastAction = null;
    return;
  }
  const filteredIdx = state.filtered.indexOf(target);
  if (filteredIdx >= 0) {
    state.index = filteredIdx;
  } else {
    state.filter.status = "all";
    els.filterStatus.value = "all";
    applyFilters();
    state.index = state.filtered.indexOf(target);
  }
  if (action.prev) {
    const res = await fetch("/api/labels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        record_id: action.recordId,
        verdict: action.prev.verdict,
        notes: action.prev.notes ?? null,
      }),
    });
    if (!res.ok) {
      showToast(`undo failed: ${res.status}`);
      return;
    }
    const data = await res.json();
    target.manual_label = data.label;
    showToast(`undid -> ${action.prev.verdict}`);
  } else {
    const res = await fetch(
      `/api/labels/${encodeURIComponent(action.recordId)}`,
      { method: "DELETE" },
    );
    if (!res.ok) {
      showToast(`undo failed: ${res.status}`);
      return;
    }
    target.manual_label = null;
    showToast("undid -> unlabelled");
  }
  state.lastAction = null;
  populateSourceFilter();
  renderDistribution();
  render();
}

function advance(delta) {
  if (state.filtered.length === 0) return;
  state.index =
    (state.index + delta + state.filtered.length) % state.filtered.length;
  state.evidenceExpanded = false;
  render();
}

function nextUnlabelled() {
  if (state.filtered.length === 0) return;
  for (let off = 1; off <= state.filtered.length; off++) {
    const i = (state.index + off) % state.filtered.length;
    if (!state.filtered[i].manual_label) {
      state.index = i;
      state.evidenceExpanded = false;
      render();
      return;
    }
  }
  showToast("no unlabelled records left in this filter");
}

function acceptSuggestion() {
  if (state.filtered.length === 0) return;
  const r = state.filtered[state.index];
  const sugg = suggestedVerdict(r);
  if (!sugg) {
    showToast("no suggestion to accept");
    return;
  }
  if (r.manual_label && r.manual_label.verdict === sugg) {
    advance(1);
    return;
  }
  applyVerdict(sugg);
}

function bind() {
  els.filterSource.addEventListener("change", () => {
    state.filter.source = els.filterSource.value;
    state.index = 0;
    applyFilters();
    render();
  });
  els.filterStatus.addEventListener("change", () => {
    state.filter.status = els.filterStatus.value;
    state.index = 0;
    applyFilters();
    render();
  });
  els.filterScript.addEventListener("change", () => {
    state.filter.script = els.filterScript.value;
    state.index = 0;
    applyFilters();
    render();
  });
  els.filterVerdict.addEventListener("change", () => {
    state.filter.verdict = els.filterVerdict.value;
    state.index = 0;
    applyFilters();
    render();
  });
  els.reload.addEventListener("click", () => init());

  els.verdicts.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-verdict]");
    if (!btn) return;
    applyVerdict(btn.dataset.verdict);
  });

  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;

    if (e.key === "ArrowRight") {
      advance(1);
      e.preventDefault();
    } else if (e.key === "ArrowLeft") {
      advance(-1);
      e.preventDefault();
    } else if (e.key === "Enter") {
      acceptSuggestion();
      e.preventDefault();
    } else if (e.key === "n" || e.key === "N") {
      nextUnlabelled();
      e.preventDefault();
    } else if (e.key === "u" || e.key === "U") {
      undoLastAction();
      e.preventDefault();
    } else if (e.key === "o" || e.key === "O") {
      const r = state.filtered[state.index];
      if (r) window.open(r.url, "_blank", "noopener");
      e.preventDefault();
    } else if (e.key === "e" || e.key === "E") {
      toggleEvidence();
      e.preventDefault();
    } else if (e.key in KEY_TO_VERDICT) {
      applyVerdict(KEY_TO_VERDICT[e.key]);
      e.preventDefault();
    }
  });
}

async function init() {
  els.card.innerHTML = `<p class="muted">loading…</p>`;
  try {
    state.records = await fetchRecords();
  } catch (err) {
    els.card.innerHTML = `<div class="empty">Failed to load records: ${escapeHtml(err.message)}</div>`;
    return;
  }
  populateSourceFilter();
  renderDistribution();
  applyFilters();
  render();
}

bind();
init();
