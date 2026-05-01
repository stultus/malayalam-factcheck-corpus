"use strict";

const state = {
  records: [],
  filtered: [],
  index: 0,
  filter: { source: "", status: "unknown", script: "" },
};

const els = {
  card: document.getElementById("card"),
  position: document.getElementById("position"),
  labelledCount: document.getElementById("labelled-count"),
  filterSource: document.getElementById("filter-source"),
  filterStatus: document.getElementById("filter-status"),
  filterScript: document.getElementById("filter-script"),
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
};

async function fetchRecords() {
  const res = await fetch("/api/records");
  if (!res.ok) throw new Error(`/api/records: ${res.status}`);
  const data = await res.json();
  return data.records;
}

function applyFilters() {
  const { source, status, script } = state.filter;
  state.filtered = state.records.filter((r) => {
    if (source && r.source_id !== source) return false;
    if (script && r.claim_text_script !== script) return false;
    if (status === "unlabelled" && r.manual_label) return false;
    if (status === "labelled" && !r.manual_label) return false;
    if (status === "unknown" && r.verdict_canonical !== "unknown") return false;
    return true;
  });
  if (state.index >= state.filtered.length) state.index = 0;
}

function populateSourceFilter() {
  const sources = [...new Set(state.records.map((r) => r.source_id))].sort();
  const current = state.filter.source;
  els.filterSource.innerHTML =
    `<option value="">all (${state.records.length})</option>` +
    sources
      .map((s) => {
        const n = state.records.filter((r) => r.source_id === s).length;
        return `<option value="${s}"${s === current ? " selected" : ""}>${s} (${n})</option>`;
      })
      .join("");
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
  const publishedShort = r.published_date
    ? r.published_date.slice(0, 10)
    : "?";
  const evidence = r.evidence_text || "";
  const evidenceShort =
    evidence.length > 4000 ? evidence.slice(0, 4000) + "\n\n[…truncated]" : evidence;

  els.card.innerHTML = `
    <h1 lang="ml">${escapeHtml(r.title)}</h1>
    <div class="meta">
      <span class="pill">${escapeHtml(r.source_id)}</span>
      <span class="pill">${escapeHtml(r.language)} / ${escapeHtml(r.claim_text_script)}</span>
      <span class="pill">extractor: ${escapeHtml(r.extractor_used)}</span>
      <span class="pill current">auto: ${escapeHtml(r.verdict_canonical)} (${escapeHtml(r.verdict_raw || "—")})</span>
      ${manual ? `<span class="pill manual">manual: ${escapeHtml(manual.verdict)}</span>` : ""}
      <span>${escapeHtml(publishedShort)}</span>
      <a href="${escapeHtml(r.url)}" target="_blank" rel="noopener">open article ↗</a>
    </div>
    <section class="block">
      <div class="label">claim</div>
      <div class="body" lang="ml">${escapeHtml(r.claim_text)}</div>
    </section>
    <section class="block">
      <div class="label">evidence (${evidence.length.toLocaleString()} chars)</div>
      <div class="body evidence" lang="ml">${escapeHtml(evidenceShort)}</div>
    </section>
  `;

  els.verdicts.hidden = false;
  els.notesRow.hidden = false;
  els.hints.hidden = false;
  els.notes.value = manual && manual.notes ? manual.notes : "";

  for (const btn of els.verdicts.querySelectorAll("button")) {
    btn.classList.toggle(
      "active",
      manual && btn.dataset.verdict === manual.verdict,
    );
  }
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
  showToast._timer = setTimeout(() => t.classList.remove("show"), 1200);
}

async function applyVerdict(verdict) {
  if (state.filtered.length === 0) return;
  const r = state.filtered[state.index];
  if (verdict === "__delete__") {
    if (!r.manual_label) return;
    const res = await fetch(`/api/labels/${encodeURIComponent(r.record_id)}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      showToast(`delete failed: ${res.status}`);
      return;
    }
    r.manual_label = null;
    showToast("cleared");
    render();
    return;
  }
  const notes = els.notes.value.trim() || null;
  const res = await fetch("/api/labels", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ record_id: r.record_id, verdict, notes }),
  });
  if (!res.ok) {
    showToast(`save failed: ${res.status}`);
    return;
  }
  const data = await res.json();
  r.manual_label = data.label;
  showToast(`saved: ${verdict}`);
  render();
  advance(1);
}

function advance(delta) {
  if (state.filtered.length === 0) return;
  state.index =
    (state.index + delta + state.filtered.length) % state.filtered.length;
  render();
}

function nextUnlabelled() {
  if (state.filtered.length === 0) return;
  for (let off = 1; off <= state.filtered.length; off++) {
    const i = (state.index + off) % state.filtered.length;
    if (!state.filtered[i].manual_label) {
      state.index = i;
      render();
      return;
    }
  }
  showToast("no unlabelled records left in this filter");
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
    } else if (e.key === "n" || e.key === "N") {
      nextUnlabelled();
      e.preventDefault();
    } else if (e.key === "o" || e.key === "O") {
      const r = state.filtered[state.index];
      if (r) window.open(r.url, "_blank", "noopener");
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
  applyFilters();
  render();
}

bind();
init();
