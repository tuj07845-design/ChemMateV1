/* ChemMate V1 UI — 前端交互（Mock 模式）
   数据流：轮询 /api/run/state 快照 → 重绘 workflow 卡片 / console / result */

"use strict";

const $ = (id) => document.getElementById(id);

const state = {
  runId: null,
  running: false,
  pollTimer: null,
  figurePath: null,
  reportPath: null,
  lastLogCount: 0,
};

const QUICK_TASKS = [
  "分析10万吨环己烷模型的S10物流，绘制物流组成图并生成报告",
  "读取S10的T/P/流量并出Word报告",
];

/* ---------------- 状态徽章文案 ---------------- */
const STATUS_TEXT = {
  ready: "Ready",
  running: "Running",
  completed: "Completed",
  error: "Error",
  stopped: "Stopped",
};
const badgeClass = { ready: "st-waiting", running: "st-running", completed: "st-success", error: "st-error", stopped: "st-error" };

function setSysBadge(status) {
  const b = $("sys-badge");
  b.className = "badge " + (badgeClass[status] || "st-waiting");
  $("sys-badge-text").textContent = STATUS_TEXT[status] || status;
}

/* ---------------- Workflow 渲染 ---------------- */
let stepEls = null;

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
  const map = { "User Task": "TASK", Agent: "AGT", "Agent Analysis": "ANL", Completed: "DONE" };
  if (map[name]) return map[name];
  const parts = name.split("_");
  return (parts.length > 1 ? parts.map((p) => p[0]).join("") : name.slice(0, 3)).toUpperCase();
}

function renderSteps(steps) {
  const badgeText = { waiting: "WAITING", running: "RUNNING", success: "SUCCESS", error: "ERROR" };
  steps.forEach((s) => {
    const el = stepEls && stepEls[s.key];
    if (!el) return;
    el.className = "step-card st-" + s.status;
    el.querySelector(".step-badge").className = "step-badge st-" + s.status;
    el.querySelector(".step-badge").textContent = badgeText[s.status] || s.status.toUpperCase();
    el.querySelector(".step-dur").textContent = s.duration != null ? s.duration.toFixed(1) + " s" : "";
    const res = el.querySelector(".step-result");
    if (s.result) res.textContent = s.result;
  });
}

/* ---------------- Console 渲染 ---------------- */
function renderLogs(logs) {
  if (logs.length <= state.lastLogCount) {
    if (logs.length < state.lastLogCount) {
      $("console").innerHTML = "";
      state.lastLogCount = 0;
    } else return;
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

/* ---------------- Result 渲染 ---------------- */
function fmt(v, d) { return Number(v).toFixed(d); }

function renderResult(snap) {
  $("result-empty").classList.add("hidden");
  $("result-body").classList.remove("hidden");

  const r = snap.result;
  if (r && !$("tables-wrap").dataset.filled) {
    $("stream-name").textContent = r.stream || "S10";

    $("prop-chips").innerHTML = r.properties
      .map((p) => '<span class="prop-chip">' + esc(p.cn) + "<b>" + fmt(p.value, p.decimals) + " " + esc(p.unit) + "</b></span>")
      .join("");

    const tbl = (title, en, blk) => {
      const rows = blk.rows
        .map((row) => "<tr><td>" + esc(row[0]) + '</td><td class="num">' + fmt(row[1], blk.decimals) + "</td></tr>")
        .join("");
      return (
        '<div><div class="tbl-title">' + esc(title) + "<span>" + esc(en) + " · " + esc(blk.unit) + "</span></div>" +
        '<table class="data-table"><thead><tr><th>组分</th><th class="num">数值</th></tr></thead>' +
        "<tbody>" + rows + '<tr class="total"><td>合计</td><td class="num">' + fmt(blk.total, blk.decimals) + "</td></tr></tbody></table></div>"
      );
    };

    $("tables-wrap").innerHTML =
      tbl("质量流量", "Mass Flow", r.mass_flow) +
      tbl("摩尔流量", "Mole Flow", r.mole_flow) +
      tbl("摩尔分率", "Mole Fraction", r.mole_fraction);
    $("tables-wrap").dataset.filled = "1";
  }

  if (snap.figure && snap.figure !== state.figurePath) {
    state.figurePath = snap.figure;
    $("figure-img").src = "/api/runs/" + snap.run_id + "/" + encodeURIComponent(fileOf(snap.figure)) + "?t=" + Date.now();
  }

  const docs = snap.reports || {};
  if (docs.docx && docs.docx !== state.reportPath) {
    state.reportPath = docs.docx;
    $("report-status").innerHTML = '<span class="ok">✓ Word report generated</span><br>' + esc(fileOf(docs.docx));
  }
}

function fileOf(p) { return p.split(/[\\/]/).pop(); }

function resetResult() {
  $("result-empty").classList.remove("hidden");
  $("result-body").classList.add("hidden");
  $("tables-wrap").innerHTML = "";
  delete $("tables-wrap").dataset.filled;
  $("figure-img").src = "";
  $("report-status").textContent = "word_create 尚未生成报告";
  state.figurePath = null;
  state.reportPath = null;
}

/* ---------------- 轮询 ---------------- */
function poll() {
  if (!state.runId) return;
  fetch("/api/run/state?run_id=" + state.runId)
    .then((r) => r.json())
    .then((snap) => {
      renderSteps(snap.steps);
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
      if (snap.status === "running") {
        state.pollTimer = setTimeout(poll, 400);
      } else {
        state.pollTimer = null;
      }
    })
    .catch(() => { state.pollTimer = setTimeout(poll, 1200); });
}

function setIdle(done) {
  state.running = false;
  $("btn-start").disabled = false;
  $("btn-stop").disabled = true;
  $("btn-word").disabled = !done;
  $("btn-ppt").disabled = !done;
  $("btn-redraw").disabled = !done;
  $("btn-open-img").disabled = !state.figurePath;
  $("btn-open-report").disabled = !state.reportPath;
  $("task-meta").textContent = done
    ? "运行完成，用时见各节点耗时"
    : "运行已结束";
}

/* ---------------- 动作 ---------------- */
function startRun() {
  const task = $("task-input").value.trim();
  if (!task) { $("task-input").focus(); return; }
  if (state.running) return;

  state.running = true;
  state.lastLogCount = 0;
  $("console").innerHTML = "";
  resetResult();
  $("btn-start").disabled = true;
  $("btn-stop").disabled = false;
  $("btn-word").disabled = true;
  $("btn-ppt").disabled = true;
  $("btn-redraw").disabled = true;
  $("btn-open-img").disabled = true;
  $("btn-open-report").disabled = true;
  $("task-meta").textContent = "运行中……";
  setSysBadge("running");

  fetch("/api/run/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ task }),
  })
    .then((r) => r.json())
    .then((res) => {
      state.runId = res.run_id;
      return fetch("/api/run/state?run_id=" + state.runId);
    })
    .then((r) => r.json())
    .then((snap) => {
      buildWorkflow(snap.steps);
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
  $("console").innerHTML = '<div class="log-line"><span class="log-ts">--:--:--</span> <span class="dim">等待任务……</span></div>';
  $("workflow").innerHTML = "";
  stepEls = null;
  resetResult();
  $("task-input").value = "";
  $("task-meta").textContent = "等待输入任务";
  setSysBadge("ready");
  $("btn-start").disabled = false;
  $("btn-stop").disabled = true;
  $("btn-word").disabled = true;
  $("btn-ppt").disabled = true;
  $("btn-redraw").disabled = true;
  $("btn-open-img").disabled = true;
  $("btn-open-report").disabled = true;
}

function postJSON(url, body) {
  return fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
    .then((r) => r.json());
}

function generateReport(reportType) {
  if (!state.runId) return;
  const btn = reportType === "docx" ? $("btn-word") : $("btn-ppt");
  btn.disabled = true;
  btn.textContent = reportType === "docx" ? "生成中…" : "生成中…";
  postJSON("/api/report", { run_id: state.runId, report_type: reportType })
    .then((res) => {
      if (res.success && res.file_path) {
        if (reportType === "docx") {
          state.reportPath = res.file_path;
          $("report-status").innerHTML = '<span class="ok">✓ Word report generated</span><br>' + esc(fileOf(res.file_path));
        } else {
          $("report-status").innerHTML += '<br><span class="ok">✓ PPT report generated</span> ' + esc(fileOf(res.file_path));
        }
      } else {
        $("report-status").textContent = "生成失败：" + (res.message || res.error || "未知错误");
      }
    })
    .finally(() => {
      btn.textContent = reportType === "docx" ? "生成 Word" : "生成 PPT";
      btn.disabled = !state.reportPath && reportType === "docx" ? false : false;
      $("btn-open-report").disabled = !state.reportPath;
    });
}

function openArtifact(path) {
  if (!path) return;
  postJSON("/api/open", { path }).then(() => {});
}

function redraw() {
  if (!state.runId) return;
  $("btn-redraw").disabled = true;
  postJSON("/api/redraw", { run_id: state.runId }).then((res) => {
    if (res.success && res.figure) {
      state.figurePath = res.figure;
      $("figure-img").src = "/api/runs/" + state.runId + "/" + encodeURIComponent(fileOf(res.figure)) + "?t=" + Date.now();
    }
    $("btn-redraw").disabled = false;
    $("btn-open-img").disabled = false;
  });
}

/* ---------------- 工具 ---------------- */
function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------------- 绑定 ---------------- */
$("btn-start").addEventListener("click", startRun);
$("btn-stop").addEventListener("click", stopRun);
$("btn-clear").addEventListener("click", clearAll);
$("btn-word").addEventListener("click", () => generateReport("docx"));
$("btn-ppt").addEventListener("click", () => generateReport("pptx"));
$("btn-redraw").addEventListener("click", redraw);
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
