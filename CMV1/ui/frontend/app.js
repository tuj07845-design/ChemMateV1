/* ChemMate V1 UI — 前端交互（真实 Agent 模式）
   数据流：轮询 /api/run/state 快照 → 动态 workflow / console / result
   workflow 步骤由后端 RealAgent 按真实运行轮次实时推送 */

"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  runId: null,
  running: false,
  pollTimer: null,
  figurePath: null,
  reportPath: null,
  lastLogCount: 0,
  stepKeys: [],
};

const QUICK_TASKS = [
  "检查10万吨环己烷.bkp全流程有无报错，如有则生成带图的Word报告",
  "分析B8精馏塔的进出物料衡算并出图",
  "追踪环己烷组分沿流程的分布并生成PPT报告",
];

/* ---------------- 状态徽章 ---------------- */
const STATUS_TEXT = {
  ready: "Ready", running: "Running", completed: "Completed", error: "Error", stopped: "Stopped",
};
const badgeClass = { ready: "st-waiting", running: "st-running", completed: "st-success", error: "st-error", stopped: "st-error" };

function setSysBadge(status) {
  const b = $("sys-badge");
  b.className = "badge " + (badgeClass[status] || "st-waiting");
  $("sys-badge-text").textContent = STATUS_TEXT[status] || status;
}

/* ---------------- Workflow（动态重建） ---------------- */
let stepEls = null;

function stepKeyList(steps) { return steps.map((s) => s.key); }

function sameKeys(a, b) {
  if (a.length !== b.length) return false;
  for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
  return true;
}

function buildWorkflow(steps) {
  const box = $("workflow");
  box.innerHTML = "";
  stepEls = {};
  steps.forEach((s, i) => {
    if (i > 0) {
      const c = document.createElement("div");
      c.className = "connector";
      box.appendChild(c);
    }
    const card = document.createElement("div");
    card.className = "step-card st-waiting";
    card.innerHTML =
      '<div class="step-mono">' + monoAbbr(s.name) + "</div>" +
      '<div class="step-main">' +
        '<div class="step-name">' + esc(s.name) + "</div>" +
        '<div class="step-cn">' + esc(s.cn) + "</div>" +
        '<div class="step-result"></div>' +
      "</div>" +
      '<div class="step-side">' +
        '<span class="step-badge st-waiting">WAITING</span>' +
        '<span class="step-dur"></span>' +
      "</div>";
    box.appendChild(card);
    stepEls[s.key] = card;
  });
}

function monoAbbr(name) {
  const map = { "User Task": "TASK", Completed: "DONE", "Agent 推理与工具调用": "AGT" };
  if (map[name]) return map[name];
  const parts = String(name).split("_");
  return (parts.length > 1 ? parts.map((p) => p[0]).join("") : String(name).slice(0, 3)).toUpperCase();
}

function renderSteps(steps) {
  const badgeText = { waiting: "WAITING", running: "RUNNING", success: "SUCCESS", error: "ERROR" };
  steps.forEach((s) => {
    const el = stepEls && stepEls[s.key];
    if (!el) return;
    el.className = "step-card st-" + s.status;
    el.querySelector(".step-badge").className = "step-badge st-" + s.status;
    el.querySelector(".step-badge").textContent = badgeText[s.status] || String(s.status).toUpperCase();
    el.querySelector(".step-dur").textContent = s.duration != null ? Number(s.duration).toFixed(1) + " s" : "";
    if (s.result) el.querySelector(".step-result").textContent = s.result;
  });
}

function refreshWorkflow(snap) {
  const keys = stepKeyList(snap.steps);
  if (!sameKeys(state.stepKeys, keys)) {
    state.stepKeys = keys;
    buildWorkflow(snap.steps);
  }
  renderSteps(snap.steps);
}

/* ---------------- Console ---------------- */
function renderLogs(logs) {
  if (logs.length <= state.lastLogCount) {
    if (logs.length < state.lastLogCount) { $("console").innerHTML = ""; state.lastLogCount = 0; }
    else return;
  }
  const box = $("console");
  for (let i = state.lastLogCount; i < logs.length; i++) {
    const l = logs[i];
    const line = document.createElement("div");
    line.className = "log-line";
    const isAgent = l.source === "Agent";
    const isSystem = l.source === "System";
    const tagCls = isAgent ? "agent" : isSystem ? "system" : "tool";
    const tag = isAgent ? "[Agent]" : isSystem ? "[System]" : "[" + l.source + "]";
    const txtCls = l.ok === true ? "log-ok" : l.ok === false ? "log-err" : "log-text";
    line.innerHTML =
      '<span class="log-ts">' + esc(l.ts) + "</span>" +
      '<span class="log-tag ' + tagCls + '">' + esc(tag) + "</span>" +
      '<span class="' + txtCls + '">' + esc(l.text) + "</span>";
    box.appendChild(line);
  }
  state.lastLogCount = logs.length;
  box.scrollTop = box.scrollHeight;
}

/* ---------------- Result ---------------- */
function fileOf(p) { return String(p).split(/[\\/]/).pop(); }

function renderResult(snap) {
  $("result-empty").classList.add("hidden");
  $("result-body").classList.remove("hidden");

  if (snap.result && snap.result !== state.answerShown) {
    state.answerShown = snap.result;
    $("answer-text").textContent = snap.result;
  }

  if (snap.figure && snap.figure !== state.figurePath) {
    state.figurePath = snap.figure;
    $("figure-img").src = "/api/runs/" + snap.run_id + "/" + encodeURIComponent(fileOf(snap.figure)) + "?t=" + Date.now();
    $("btn-open-img").disabled = false;
  }

  const docs = snap.reports || {};
  if (docs.docx || docs.pptx) {
    const parts = [];
    if (docs.docx) parts.push('<span class="ok">✓ Word</span> ' + esc(fileOf(docs.docx)));
    if (docs.pptx) parts.push('<span class="ok">✓ PPT</span> ' + esc(fileOf(docs.pptx)));
    state.reportPath = docs.docx || docs.pptx || null;
    $("report-status").innerHTML = parts.join("<br>");
    $("btn-open-report").disabled = false;
  }
}

function resetResult() {
  $("result-empty").classList.remove("hidden");
  $("result-body").classList.add("hidden");
  $("figure-img").src = "";
  $("report-status").textContent = "任务完成后此处显示报告文件";
  state.figurePath = null;
  state.reportPath = null;
  delete state.answerShown;
}

/* ---------------- 轮询 ---------------- */
function poll() {
  if (!state.runId) return;
  fetch("/api/run/state?run_id=" + state.runId)
    .then((r) => r.json())
    .then((snap) => {
      refreshWorkflow(snap);
      renderLogs(snap.logs);
      if (snap.status === "running") {
        setSysBadge("running");
      } else {
        setSysBadge(snap.status);
        setIdle(snap.status === "completed");
        if (snap.status === "completed" || snap.status === "error" || snap.status === "stopped") {
          renderResult(snap);
        }
      }
      state.pollTimer = snap.status === "running" ? setTimeout(poll, 400) : null;
    })
    .catch(() => { state.pollTimer = setTimeout(poll, 1200); });
}

function setIdle(done) {
  state.running = false;
  $("btn-start").disabled = false;
  $("btn-stop").disabled = true;
  $("btn-open-img").disabled = !state.figurePath;
  $("btn-open-report").disabled = !state.reportPath;
  $("task-meta").textContent = done ? "✓ 任务完成，详见下方 Result" : "运行结束";
}

/* ---------------- 动作 ---------------- */
function startRun() {
  const task = $("task-input").value.trim();
  if (!task) { $("task-input").focus(); return; }
  if (state.running) return;

  state.running = true;
  state.lastLogCount = 0;
  state.stepKeys = [];
  stepEls = null;
  $("console").innerHTML = "";
  $("workflow").innerHTML = '<div class="log-line"><span class="dim">Agent 启动中……</span></div>';
  resetResult();
  $("btn-start").disabled = true;
  $("btn-stop").disabled = false;
  $("task-meta").textContent = "运行中……（真实 Aspen / MATLAB，请耐心等待）";
  setSysBadge("running");

  fetch("/api/run/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  })
    .then((r) => r.json())
    .then((res) => {
      state.runId = res.run_id;
      poll();
    })
    .catch(() => {
      setSysBadge("error");
      $("task-meta").textContent = "启动失败：服务不可用";
      setIdle(false);
    });
}

function stopRun() {
  if (!state.runId) return;
  fetch("/api/run/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: state.runId }),
  });
}

function clearAll() {
  if (state.pollTimer) clearTimeout(state.pollTimer);
  state.runId = null;
  state.running = false;
  state.lastLogCount = 0;
  state.stepKeys = [];
  stepEls = null;
  $("console").innerHTML = '<div class="log-line"><span class="log-ts">--:--:--</span> <span class="dim">等待任务……</span></div>';
  $("workflow").innerHTML = '<div class="log-line"><span class="dim">尚未开始 —— 提交任务后这里会实时展示 Agent 的每一轮动作</span></div>';
  resetResult();
  $("task-input").value = "";
  $("task-meta").textContent = "等待输入任务";
  setSysBadge("ready");
  $("btn-start").disabled = false;
  $("btn-stop").disabled = true;
  $("btn-open-img").disabled = true;
  $("btn-open-report").disabled = true;
}

function postJSON(url, body) {
  return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
}

function openArtifact(path) {
  if (!path) return;
  postJSON("/api/open", { path }).then(() => {});
}

/* ---------------- 工具 ---------------- */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------------- 绑定 ---------------- */
$("btn-start").addEventListener("click", startRun);
$("btn-stop").addEventListener("click", stopRun);
$("btn-clear").addEventListener("click", clearAll);
$("btn-open-img").addEventListener("click", () => openArtifact(state.figurePath));
$("btn-open-report").addEventListener("click", () => openArtifact(state.reportPath));
$("task-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) startRun();
});

QUICK_TASKS.forEach((q) => {
  const b = document.createElement("button");
  b.className = "chip";
  b.textContent = q.length > 18 ? q.slice(0, 18) + "…" : q;
  b.title = q;
  b.addEventListener("click", () => { $("task-input").value = q; $("task-input").focus(); });
  $("quick-tasks").appendChild(b);
});

setSysBadge("ready");