/* ChemMate V1 UI — stateful workbench interaction */
"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  runId: null,
  task: "",
  status: "ready",
  pollTimer: null,
  startedAt: null,
  lastLogCount: 0,
  stepKeys: [],
  figurePath: null,
  reportPath: null,
  answerShown: null,
  stopRequested: false,
};

const QUICK_TASKS = [
  "检查 10万吨环己烷.bkp 全流程有无报错，如有则生成带图的 Word 报告",
  "分析 B8 精馏塔的进出物料衡算并出图",
  "追踪环己烷组分沿流程的分布并生成 PPT 报告",
];

const STATUS_TEXT = {
  ready: "就绪", running: "运行中", stopping: "停止中", completed: "已完成", error: "异常", stopped: "已停止",
};
const STATUS_CLASS = {
  ready: "st-ready", running: "st-running", stopping: "st-stopping", completed: "st-success", error: "st-error", stopped: "st-stopped",
};
const PHASE_TEXT = {
  ready: "尚未开始", running: "Agent 正在执行", stopping: "正在收尾", completed: "分析完成", error: "执行异常", stopped: "已停止",
};

function setSysBadge(status) {
  const badge = $("sys-badge");
  badge.className = "status-pill " + (STATUS_CLASS[status] || STATUS_CLASS.ready);
  $("sys-badge-text").textContent = STATUS_TEXT[status] || status;
}

function setTaskMeta(text, tone) {
  const meta = $("task-meta");
  meta.innerHTML = '<span class="meta-dot"></span>' + esc(text);
  const dot = meta.querySelector(".meta-dot");
  if (tone === "active") dot.style.background = "var(--teal)";
  if (tone === "error") dot.style.background = "var(--red)";
  if (tone === "warn") dot.style.background = "var(--amber)";
}

function setRunControls(status) {
  const active = status === "running" || status === "stopping";
  $("btn-start").disabled = active;
  $("btn-stop").disabled = status !== "running";
  $("btn-clear").disabled = active;
  $("run-phase").textContent = PHASE_TEXT[status] || status;
  setSysBadge(status);
}

function formatElapsed(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const minutes = Math.floor(total / 60).toString().padStart(2, "0");
  const secs = (total % 60).toString().padStart(2, "0");
  return minutes + ":" + secs;
}

function currentElapsed(snap) {
  if (snap && snap.elapsed != null) return snap.elapsed;
  if (state.startedAt) return (Date.now() - state.startedAt) / 1000;
  return 0;
}

function renderRunSummary(snap) {
  $("run-task").textContent = snap.task || state.task || "提交任务后，Agent 的执行步骤会在这里展开";
  $("run-elapsed").textContent = formatElapsed(currentElapsed(snap));
  const roundKeys = (snap.steps || []).map((s) => String(s.key)).filter((key) => /^round_\d+$/.test(key));
  const round = roundKeys.length ? Math.max(...roundKeys.map((key) => Number(key.slice(6)))) : 0;
  $("run-round").textContent = round || "—";
  $("run-updated").textContent = snap.status === "running" ? "实时更新" : (snap.status === "stopping" ? "等待收尾" : "运行结束");
  setRunControls(snap.status || "ready");
}

/* ---------------- Workflow ---------------- */
let stepEls = null;

function sameKeys(a, b) {
  return a.length === b.length && a.every((key, index) => key === b[index]);
}

function monoAbbr(name) {
  const map = { "User Task": "TASK", Completed: "DONE", "Agent 推理与工具调用": "AGT" };
  if (map[name]) return map[name];
  const parts = String(name).split("_");
  return (parts.length > 1 ? parts.map((part) => part[0]).join("") : String(name).slice(0, 3)).toUpperCase();
}

function buildWorkflow(steps) {
  const box = $("workflow");
  box.innerHTML = "";
  stepEls = {};
  if (!steps.length) {
    box.innerHTML = '<div class="empty-state compact"><span class="empty-line"></span><span>Agent 启动后，这里会显示每个分析阶段</span></div>';
    return;
  }
  steps.forEach((step, index) => {
    if (index > 0) {
      const connector = document.createElement("div");
      connector.className = "connector";
      box.appendChild(connector);
    }
    const card = document.createElement("div");
    card.className = "step-card st-waiting";
    card.innerHTML =
      '<div class="step-mono">' + esc(monoAbbr(step.name)) + "</div>" +
      '<div class="step-main"><div class="step-name">' + esc(step.name) + "</div>" +
      '<div class="step-cn">' + esc(step.cn) + '</div><div class="step-result"></div></div>' +
      '<div class="step-side"><span class="step-badge st-waiting">WAITING</span><span class="step-dur"></span></div>';
    box.appendChild(card);
    stepEls[step.key] = card;
  });
}

function renderSteps(steps) {
  const badgeText = { waiting: "WAITING", running: "RUNNING", success: "DONE", error: "ERROR" };
  (steps || []).forEach((step) => {
    const element = stepEls && stepEls[step.key];
    if (!element) return;
    element.className = "step-card st-" + step.status;
    const badge = element.querySelector(".step-badge");
    badge.className = "step-badge st-" + step.status;
    badge.textContent = badgeText[step.status] || String(step.status).toUpperCase();
    element.querySelector(".step-dur").textContent = step.duration != null ? Number(step.duration).toFixed(1) + " s" : "";
    element.querySelector(".step-result").textContent = step.result || "";
  });
}

function refreshWorkflow(snap) {
  const steps = snap.steps || [];
  const keys = steps.map((step) => step.key);
  if (!sameKeys(state.stepKeys, keys)) {
    state.stepKeys = keys;
    buildWorkflow(steps);
  }
  renderSteps(steps);
}

/* ---------------- Console ---------------- */
function renderLogs(logs) {
  const entries = logs || [];
  $("log-count").textContent = entries.length + " 条";
  if (entries.length <= state.lastLogCount) {
    if (entries.length < state.lastLogCount) {
      $("console").innerHTML = "";
      state.lastLogCount = 0;
    } else return;
  }
  const box = $("console");
  for (let index = state.lastLogCount; index < entries.length; index += 1) {
    const entry = entries[index];
    const line = document.createElement("div");
    line.className = "log-line";
    const isAgent = entry.source === "Agent";
    const isSystem = entry.source === "System";
    const tagClass = isAgent ? "agent" : isSystem ? "system" : "tool";
    const tag = isAgent ? "[Agent]" : isSystem ? "[System]" : "[" + entry.source + "]";
    const textClass = entry.ok === true ? "log-ok" : entry.ok === false ? "log-err" : "log-text";
    line.innerHTML = '<span class="log-ts">' + esc(entry.ts) + "</span>" +
      '<span class="log-tag ' + tagClass + '">' + esc(tag) + "</span>" +
      '<span class="' + textClass + '">' + esc(entry.text) + "</span>";
    box.appendChild(line);
  }
  state.lastLogCount = entries.length;
  box.scrollTop = box.scrollHeight;
}

/* ---------------- Results ---------------- */
function fileOf(path) { return String(path || "").split(/[\\/]/).pop(); }

function renderResult(snap) {
  const hasOutput = Boolean(snap.result || snap.figure || (snap.reports && Object.keys(snap.reports).length));
  if (!hasOutput && snap.status === "running") return;
  $("result-empty").classList.add("hidden");
  $("result-body").classList.remove("hidden");
  $("answer-status").textContent = STATUS_TEXT[snap.status] || "RESULT";

  if (snap.result && snap.result !== state.answerShown) {
    state.answerShown = snap.result;
    $("answer-text").textContent = snap.result;
  } else if (!snap.result && snap.status !== "completed" && !$("answer-text").textContent) {
    $("answer-text").textContent = snap.status === "stopped" ? "任务已停止，未生成最终结论。" : "任务未生成最终结论，请展开调试日志查看原因。";
  }

  if (snap.figure && snap.figure !== state.figurePath) {
    state.figurePath = snap.figure;
    $("figure-img").src = "/api/runs/" + encodeURIComponent(snap.run_id) + "/" + encodeURIComponent(fileOf(snap.figure)) + "?t=" + Date.now();
    $("figure-img").classList.remove("hidden");
    $("figure-empty").classList.add("hidden");
    $("btn-open-img").disabled = false;
  }

  const docs = snap.reports || {};
  if (docs.docx || docs.pptx) {
    const parts = [];
    if (docs.docx) parts.push('<span class="ok">✓ Word</span> ' + esc(fileOf(docs.docx)));
    if (docs.pptx) parts.push('<span class="ok">✓ PPT</span> ' + esc(fileOf(docs.pptx)));
    state.reportPath = docs.docx || docs.pptx;
    $("report-status").innerHTML = parts.join("<br>");
    $("btn-open-report").disabled = false;
  }
}

function resetResult() {
  $("result-empty").classList.remove("hidden");
  $("result-body").classList.add("hidden");
  $("answer-text").textContent = "";
  $("answer-status").textContent = "WAITING";
  $("figure-img").src = "";
  $("figure-img").classList.add("hidden");
  $("figure-empty").classList.remove("hidden");
  $("report-status").textContent = "任务完成后显示可用文件";
  $("btn-open-img").disabled = true;
  $("btn-open-report").disabled = true;
  state.figurePath = null;
  state.reportPath = null;
  state.answerShown = null;
}

/* ---------------- Polling and actions ---------------- */
function poll() {
  if (!state.runId) return;
  fetch("/api/run/state?run_id=" + encodeURIComponent(state.runId))
    .then((response) => { if (!response.ok) throw new Error("state request failed"); return response.json(); })
    .then((snap) => {
      if (snap.run_id !== state.runId) return;
      state.status = snap.status || "ready";
      refreshWorkflow(snap);
      renderLogs(snap.logs);
      renderRunSummary(snap);
      renderResult(snap);
      const terminal = ["completed", "error", "stopped"].includes(state.status);
      if (terminal) {
        state.pollTimer = null;
        setTaskMeta(state.status === "completed" ? "任务完成，结果已就绪" : (state.status === "stopped" ? "任务已停止" : "任务异常结束"), state.status === "error" ? "error" : "");
      } else {
        state.pollTimer = setTimeout(poll, state.status === "stopping" ? 600 : 450);
      }
    })
    .catch(() => {
      if (!state.runId) return;
      setTaskMeta("暂时无法连接，正在重试……", "warn");
      state.pollTimer = setTimeout(poll, 1400);
    });
}

function startRun() {
  const task = $("task-input").value.trim();
  if (!task || state.status === "running" || state.status === "stopping") {
    if (!task) $("task-input").focus();
    return;
  }
  if (state.pollTimer) clearTimeout(state.pollTimer);
  state.runId = null;
  state.task = task;
  state.status = "running";
  state.startedAt = Date.now();
  state.lastLogCount = 0;
  state.stepKeys = [];
  state.stopRequested = false;
  state.figurePath = null;
  stepEls = null;
  $("run-task").textContent = task;
  $("run-round").textContent = "—";
  $("run-elapsed").textContent = "00:00";
  $("run-updated").textContent = "准备连接";
  $("console").innerHTML = "";
  $("workflow").innerHTML = '<div class="empty-state compact"><span class="empty-line"></span><span>正在启动 Agent……</span></div>';
  resetResult();
  setRunControls("running");
  setTaskMeta("正在启动 Agent，请稍候……", "active");

  fetch("/api/run/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  })
    .then((response) => { if (!response.ok) throw new Error("start request failed"); return response.json(); })
    .then((result) => {
      if (!result.run_id) throw new Error("missing run id");
      state.runId = result.run_id;
      poll();
    })
    .catch(() => {
      state.status = "error";
      setRunControls("error");
      setTaskMeta("启动失败：服务不可用", "error");
      $("run-updated").textContent = "无法连接服务";
    });
}

function stopRun() {
  if (!state.runId || state.status !== "running") return;
  state.stopRequested = true;
  state.status = "stopping";
  setRunControls("stopping");
  setTaskMeta("已发送停止请求，等待当前轮结束……", "warn");
  fetch("/api/run/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: state.runId }),
  }).catch(() => setTaskMeta("停止请求未送达，正在等待服务响应……", "warn"));
}

function clearAll() {
  if (state.status === "running" || state.status === "stopping") return;
  if (state.pollTimer) clearTimeout(state.pollTimer);
  state.runId = null;
  state.task = "";
  state.status = "ready";
  state.startedAt = null;
  state.lastLogCount = 0;
  state.stepKeys = [];
  stepEls = null;
  $("task-input").value = "";
  $("run-task").textContent = "提交任务后，Agent 的执行步骤会在这里展开";
  $("run-round").textContent = "—";
  $("run-elapsed").textContent = "00:00";
  $("run-updated").textContent = "等待运行";
  $("workflow").innerHTML = '<div class="empty-state compact"><span class="empty-line"></span><span>提交任务后，这里会显示每个分析阶段</span></div>';
  $("console").innerHTML = '<div class="log-line"><span class="log-ts">--:--:--</span><span class="dim">等待任务……</span></div>';
  $("log-count").textContent = "0 条";
  resetResult();
  setRunControls("ready");
  setTaskMeta("等待输入任务");
}

function openArtifact(path) {
  if (!path) return;
  fetch("/api/open", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path }) }).catch(() => {});
}

function esc(value) {
  return String(value == null ? "" : value).replace(/[&<>"']/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[character]));
}

/* ---------------- Bindings ---------------- */
$("btn-start").addEventListener("click", startRun);
$("btn-stop").addEventListener("click", stopRun);
$("btn-clear").addEventListener("click", clearAll);
$("btn-open-img").addEventListener("click", () => openArtifact(state.figurePath));
$("btn-open-report").addEventListener("click", () => openArtifact(state.reportPath));
$("btn-console-toggle").addEventListener("click", () => {
  const toggle = $("btn-console-toggle");
  const open = toggle.getAttribute("aria-expanded") === "true";
  toggle.setAttribute("aria-expanded", String(!open));
  $("console").classList.toggle("hidden", open);
});
$("task-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    startRun();
  }
});

QUICK_TASKS.forEach((task) => {
  const button = document.createElement("button");
  button.className = "quick-task";
  button.type = "button";
  button.textContent = task;
  button.title = task;
  button.addEventListener("click", () => { $("task-input").value = task; $("task-input").focus(); });
  $("quick-tasks").appendChild(button);
});

resetResult();
setRunControls("ready");
