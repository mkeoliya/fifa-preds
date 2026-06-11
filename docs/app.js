/* Chepta Cup frontend: renders leaderboard.json + picks.json + kalshi.json */
const STAGE_LABEL = { GROUP: "Group", R32: "Round of 32", R16: "Round of 16",
  QF: "Quarter-final", SF: "Semi-final", THIRD: "3rd Place", FINAL: "Final" };
const KO_ORDER = ["R32", "R16", "QF", "SF", "FINAL"];
const ROUND_SIZE = { R32: 32, R16: 16, QF: 8, SF: 4, FINAL: 2 };
const COLORS = ["#ffd34d", "#5da9ff", "#3ddc84", "#ff5d73", "#c792ea", "#ffb86c",
  "#7ee8fa", "#f97fd4", "#a3e635", "#94a3ff", "#ff9e9e", "#5ef0c0", "#e6c79c"];

let LB, PICKS, KALSHI;

async function load() {
  const bust = `?t=${Math.floor(Date.now() / 60000)}`;
  [LB, PICKS, KALSHI] = await Promise.all([
    fetch(`data/leaderboard.json${bust}`).then(r => r.json()),
    fetch(`data/picks.json${bust}`).then(r => r.json()),
    fetch(`data/kalshi.json${bust}`).then(r => r.json()).catch(() => null),
  ]);
  document.getElementById("updated").textContent =
    `updated ${new Date(LB.updated_at).toLocaleString()}`;
  renderLeaderboard();
  renderRace();
  renderBrackets();
  renderMatches();
}

function winnerProb(team) {
  if (!KALSHI || !KALSHI.winner) return null;
  const row = KALSHI.winner.find(w => w.team === team);
  return row ? row.prob : null;
}

/* ---------- leaderboard ---------- */
function renderLeaderboard() {
  const el = document.getElementById("leaderboard");
  const rows = LB.players.map(p => {
    const wp = winnerProb(p.champion);
    return `
    <tr class="player top${p.rank}" data-name="${p.name}">
      <td class="rank">${p.rank}</td>
      <td>${p.name}</td>
      <td class="total">${p.total}</td>
      <td class="pts">${p.match_points}</td>
      <td class="pts">${p.bonus_points}</td>
      <td class="pts">${p.award_points}</td>
      <td><span class="champ-badge">${p.champion ?? "—"}${
        wp != null ? `<span class="champ-prob">${(wp * 100).toFixed(0)}%</span>` : ""
      }</span></td>
    </tr>
    <tr class="detail-row" data-for="${p.name}" style="display:none"><td colspan="7">
      ${detailHtml(p)}
    </td></tr>`;
  }).join("");
  el.innerHTML = `<table class="lb">
    <thead><tr><th>#</th><th>Player</th><th>Total</th><th>Match</th>
    <th>Bonus</th><th>Awards</th><th>Champion pick · Kalshi odds</th></tr></thead>
    <tbody>${rows}</tbody></table>
    <p class="note">Click a row for stage bonuses &amp; award picks.
    Match pts: 5 result · +2 exact score · +3 exact pens.</p>`;
  el.querySelectorAll("tr.player").forEach(tr => tr.addEventListener("click", () => {
    const d = el.querySelector(`tr.detail-row[data-for="${tr.dataset.name}"]`);
    d.style.display = d.style.display === "none" ? "" : "none";
  }));
}

function detailHtml(p) {
  const bonusRows = KO_ORDER.map(st => {
    const b = p.bonuses[st];
    const status = b.complete ? `<b class="hit">+${b.points}</b>`
      : `<span class="miss">pending</span>`;
    return `<tr><td>${STAGE_LABEL[st]}</td>
      <td>${b.correct_so_far}/${ROUND_SIZE[st]} teams</td><td>${status}</td></tr>`;
  }).join("");
  const awardRows = Object.entries(p.awards).map(([cat, a]) => {
    const label = cat.replace("_", " ").replace(/\b\w/g, c => c.toUpperCase());
    return `<tr><td>${label}</td><td class="${a.hit ? "hit" : "miss"}">
      ${a.pick ?? "—"}${a.hit ? " ✓" : ""}</td></tr>`;
  }).join("");
  return `<div class="detail-grid">
    <div><h4>Advancement bonuses</h4><table>${bonusRows}</table></div>
    <div><h4>Award picks</h4><table>${awardRows}</table></div>
  </div>`;
}

/* ---------- points race ---------- */
function renderRace() {
  const done = LB.matches.filter(m => m.completed)
    .sort((a, b) => a.date.localeCompare(b.date));
  const labels = done.map(m => `${m.team1} v ${m.team2}`);
  const datasets = LB.players.map((p, i) => ({
    label: p.name,
    data: p.timeline.map(t => t.cum),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length],
    tension: 0.25, pointRadius: 0, borderWidth: 2.2,
  }));
  new Chart(document.getElementById("raceChart"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: "nearest", intersect: false },
      scales: {
        x: { ticks: { color: "#8e97c0", maxTicksLimit: 14, maxRotation: 60 },
             grid: { color: "#1d2444" } },
        y: { ticks: { color: "#8e97c0" }, grid: { color: "#1d2444" },
             title: { display: true, text: "match points", color: "#8e97c0" } },
      },
      plugins: { legend: { labels: { color: "#e8ecff", usePointStyle: true,
        pointStyle: "circle", boxWidth: 8 } } },
    },
  });
  if (!done.length) {
    document.querySelector("#race .chartwrap").insertAdjacentHTML("beforebegin",
      `<p class="note">No completed matches yet — the race starts with the opening game!</p>`);
  }
}

/* ---------- brackets ---------- */
function actualRoundTeams(stage) {
  const teams = new Set();
  LB.matches.filter(m => m.stage === stage).forEach(m => {
    if (m.team1) teams.add(m.team1);
    if (m.team2) teams.add(m.team2);
  });
  return { teams, complete: teams.size === ROUND_SIZE[stage] };
}

function renderBrackets() {
  const el = document.getElementById("brackets");
  const names = LB.players.map(p => p.name);
  el.innerHTML = `<div class="bracket-picker">${names.map((n, i) =>
    `<button data-name="${n}" class="${i === 0 ? "active" : ""}">${n}</button>`
  ).join("")}</div><div id="bracketview"></div>`;
  el.querySelectorAll(".bracket-picker button").forEach(b =>
    b.addEventListener("click", () => {
      el.querySelectorAll(".bracket-picker button").forEach(x =>
        x.classList.remove("active"));
      b.classList.add("active");
      drawBracket(b.dataset.name);
    }));
  drawBracket(names[0]);
}

function drawBracket(name) {
  const pred = PICKS[name];
  const actual = {};
  KO_ORDER.forEach(st => actual[st] = actualRoundTeams(st));
  const cols = KO_ORDER.map(st => {
    const ms = pred.matches.filter(m => m.stage === st)
      .sort((a, b) => a.match_no - b.match_no);
    const cards = ms.map(m => bteamRows(m, actual[st])).join("");
    return `<div class="round"><h3>${STAGE_LABEL[st]}</h3>${cards}</div>`;
  }).join("");
  const wp = winnerProb(pred.champion);
  document.getElementById("bracketview").innerHTML =
    `<div class="bracket">${cols}</div>
     <p class="champ-line">Predicted champion:
       <b>🏆 ${pred.champion}</b>${wp != null ?
       ` <span class="champ-prob">Kalshi ${(wp * 100).toFixed(0)}%</span>` : ""}</p>
     <p class="note"><span class="hit">green</span> = team really made this round ·
     <span style="color:var(--red)">red</span> = field set, team missed it</p>`;
}

function bteamRows(m, act) {
  const row = (team, sc, pen) => {
    let cls = "";
    if (act.teams.has(team)) cls = "right";
    else if (act.complete) cls = "wrong";
    return `<div class="bteam ${cls}"><span class="nm">${team}</span>
      <span class="sc">${sc ?? ""}${pen != null ? ` (${pen})` : ""}</span></div>`;
  };
  return `<div class="bmatch">${row(m.team1, m.score1, m.pen1)}
    ${row(m.team2, m.score2, m.pen2)}</div>`;
}

/* ---------- matches ---------- */
function kalshiFor(m) {
  if (!KALSHI || !m.team1 || !m.team2) return null;
  return KALSHI.matches[[m.team1, m.team2].sort().join("|")] ?? null;
}

function renderMatches() {
  const el = document.getElementById("matches");
  const byDay = {};
  LB.matches.forEach(m => {
    const day = m.date.slice(0, 10);
    (byDay[day] ??= []).push(m);
  });
  const today = new Date().toISOString().slice(0, 10);
  const days = Object.keys(byDay).sort();
  el.innerHTML = days.map(day => {
    const dayLabel = new Date(day + "T12:00Z").toLocaleDateString(undefined,
      { weekday: "long", month: "long", day: "numeric" });
    const cards = byDay[day]
      .sort((a, b) => a.date.localeCompare(b.date))
      .map(matchCard).join("");
    return `<div class="daygroup" id="day-${day}">
      <h2>${dayLabel}${day === today ?
        '<span class="todaytag"> · TODAY</span>' : ""}</h2>${cards}</div>`;
  }).join("");
  el.querySelectorAll(".togglepicks").forEach(btn =>
    btn.addEventListener("click", () => {
      const t = document.getElementById(btn.dataset.target);
      const open = t.style.display === "none";
      t.style.display = open ? "" : "none";
      btn.textContent = open ? "Hide picks ▴" : "Show picks ▾";
    }));
  const anchor = document.getElementById(`day-${today}`);
  // jump to today when the tab is opened
  document.querySelector('[data-tab="matches"]').addEventListener("click",
    () => anchor && anchor.scrollIntoView({ block: "start" }));
}

let cardSeq = 0;
function matchCard(m) {
  const id = `picks-${cardSeq++}`;
  const t1 = m.team1 ?? "TBD", t2 = m.team2 ?? "TBD";
  const score = m.state === "pre"
    ? `<span class="mmeta">${new Date(m.date).toLocaleTimeString([],
        { hour: "2-digit", minute: "2-digit" })}</span>`
    : `<span class="mscore">${m.score1 ?? ""}–${m.score2 ?? ""}${
        m.pen1 != null ? ` <small>(${m.pen1}–${m.pen2} pens)</small>` : ""}</span>${
        m.state === "in" ? ` <span class="mlive">● LIVE</span>` : ""}`;
  const k = kalshiFor(m);
  let odds = "";
  if (k && m.state !== "post") {
    const p1 = k.probs[m.team1] ?? 0, p2 = k.probs[m.team2] ?? 0, px = k.tie ?? 0;
    const tot = p1 + p2 + px || 1;
    odds = `<div class="oddsbar">
        <div style="width:${(p1 / tot) * 100}%;background:var(--green)"></div>
        <div style="width:${(px / tot) * 100}%;background:#39406b"></div>
        <div style="width:${(p2 / tot) * 100}%;background:var(--red)"></div>
      </div>
      <div class="oddslabels"><span>${t1} ${(p1 * 100).toFixed(0)}%</span>
      <span>draw ${(px * 100).toFixed(0)}%</span>
      <span>${t2} ${(p2 * 100).toFixed(0)}%</span></div>`;
  }
  const chips = LB.players.map(p => {
    const mid = `${m.stage}|${m.team1}|${m.team2}`;
    const det = p.per_match[mid];
    let scoreStr = "—", pensStr = "", pts = null, cls = "";
    if (det && det.pick) {
      scoreStr = `${det.pick[0] ?? "·"}–${det.pick[1] ?? "·"}`;
      if (det.pick_pens && det.pick_pens[0] != null)
        pensStr = `${det.pick_pens[0]}–${det.pick_pens[1]} pens`;
      pts = det.points;
      cls = det.detail.includes("exact") ? "exact"
        : det.detail.includes("result") ? "result" : "miss";
    } else if (m.team1 && m.team2) {
      const pick = (PICKS[p.name].matches || []).find(x => x.stage === m.stage &&
        ((x.team1 === m.team1 && x.team2 === m.team2) ||
         (x.team1 === m.team2 && x.team2 === m.team1)));
      if (pick) {
        const flip = pick.team1 !== m.team1;
        scoreStr = `${(flip ? pick.score2 : pick.score1) ?? "·"}–${
          (flip ? pick.score1 : pick.score2) ?? "·"}`;
        if (pick.pen1 != null)
          pensStr = `${flip ? pick.pen2 : pick.pen1}–${
            flip ? pick.pen1 : pick.pen2} pens`;
      }
    }
    return { name: p.name, scoreStr, pensStr, pts, cls };
  });

  const isDone = m.state === "post";
  let consensus = "";
  if (isDone) {
    chips.sort((a, b) => (b.pts ?? -1) - (a.pts ?? -1) ||
      a.name.localeCompare(b.name));
  } else {
    // cluster identical scorelines, most popular first
    const freq = {};
    chips.forEach(c => freq[c.scoreStr] = (freq[c.scoreStr] || 0) + 1);
    chips.sort((a, b) => freq[b.scoreStr] - freq[a.scoreStr] ||
      a.scoreStr.localeCompare(b.scoreStr) || a.name.localeCompare(b.name));
    const top = Object.entries(freq).filter(([s]) => s !== "—")
      .sort((a, b) => b[1] - a[1])[0];
    if (top && top[1] > 1)
      consensus = `<p class="consensus">Crowd favourite: <b>${top[0]}</b>
        (${top[1]} of ${chips.length} picks)</p>`;
  }
  const chipHtml = chips.map(c => `
    <div class="pchip ${c.cls}">
      ${c.pts != null && c.pts > 0 ? `<span class="pbadge">+${c.pts}</span>` : ""}
      <div class="who">${c.name}</div>
      <div class="pscore">${c.scoreStr}</div>
      ${c.pensStr ? `<div class="ppens">${c.pensStr}</div>` : ""}
    </div>`).join("");
  const legend = isDone ? `<p class="legend">
      <span class="sw" style="background:var(--mx)"></span>exact score
      <span class="sw" style="background:var(--us)"></span>correct result
      <span class="sw" style="background:#39406b"></span>miss</p>` : "";
  return `<div class="mcard">
    <div class="mhead">
      <span class="stagechip">${STAGE_LABEL[m.stage]}</span>
      <span class="mteams">${t1} vs ${t2}</span>${score}
      <span class="mmeta">${m.venue ?? ""}</span>
    </div>
    ${odds}
    <button class="togglepicks" data-target="${id}">Show picks ▾</button>
    <div id="${id}" style="display:none">${consensus}
      <div class="pickgrid">${chipHtml}</div>${legend}</div>
  </div>`;
}

/* tabs */
document.querySelectorAll(".tab").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach(x => x.classList.remove("active"));
  document.querySelectorAll(".panel").forEach(x => x.classList.remove("active"));
  b.classList.add("active");
  document.getElementById(b.dataset.tab).classList.add("active");
}));

load();
