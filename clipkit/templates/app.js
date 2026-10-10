const IMG_CHIPS = __CHIPS__;
const SUB_CHIPS = __SUBCHIPS__;
const CATS = __CATS__;
const RECENT = __RECENT__;
const $ = id => document.getElementById(id);
const qEl = $("q"), grid = $("grid"), metaEl = $("meta"), emptyEl = $("empty"),
      topSel = $("top"), chipsBox = $("chips"), catsBox = $("cats"),
      histRow = $("histRow"), tipBox = $("tipBox"), rawBtn = $("raw");
let mode = "img", dedup = true, busy = false, sel = -1, seq = 0,
    catSel = new Set(), lastData = null;

const TOP_OPTS = {
  img: [["12","12 条"],["20","20 条"],["30","30 条"],["40","40 条"]],
  sub: [["10","10 条"],["20","20 条"],["40","40 条"],["60","60 条"]],
  tl:  [["12","近 12 条素材"],["20","近 20 条"],["40","近 40 条"]]
};
const PLACEHOLDER = {
  img: "用中文描述你想要的画面，例如：手部特写 缠绷带",
  sub: "搜台词关键词，例如：奉陪到底 / 不服输 / 代代相传",
  tl:  "先搜画面，再切到时间线看整条时间轴（或直接在这里搜索）"
};
const HELP = [
  "<b>怎么用最快：</b>直接打中文，回车即出结果。",
  "· 点卡片可以展开 <b>VLM 画面描述</b>（主体 / 动作 / 场景 / 画面）和该素材的全部台词。",
  "· 卡片上「<b>≈4.0s</b>」是时间定位提示，点 clip 名右边的 <b>复制</b> 可以一键复制素材名，在 Premiere 里直接找。",
  "· 「<b>同素材多帧</b>」打开后，同一素材会显示 20% / 50% / 80% 三帧，能看清动作走向。",
  "· 黄色分数条是 <b>相对最高分</b> 的视觉相似度；文案里出现 <b>命中描述关键词</b> 说明 VLM 描述里真的提到了这个词。",
  "· 画面检索是模糊的语义排序，<b>不要把排序当成结论</b>，务必自己核对画面。"
].join("<br>");

/* ---------- 渲染头部小控件 ---------- */
function renderChips(){
  chipsBox.innerHTML = "";
  const lb = document.createElement("span");
  lb.className = "lb"; lb.textContent = "试试：";
  chipsBox.appendChild(lb);
  (mode === "img" ? IMG_CHIPS : SUB_CHIPS).forEach(c => {
    const b = document.createElement("span");
    b.className = "chip"; b.textContent = c;
    b.onclick = () => { qEl.value = c; run(); };
    chipsBox.appendChild(b);
  });
  catsBox.style.display = mode === "sub" ? "none" : "flex";
}
function renderCats(){
  catsBox.innerHTML = "";
  const lb = document.createElement("span");
  lb.className = "lb"; lb.textContent = "分类筛选：";
  catsBox.appendChild(lb);
  CATS.forEach(c => {
    const b = document.createElement("span");
    b.className = "chip"; b.textContent = c;
    b.onclick = () => {
      if (catSel.has(c)) catSel.delete(c); else catSel.add(c);
      b.classList.toggle("on", catSel.has(c));
      if (qEl.value.trim()) run();
    };
    catsBox.appendChild(b);
  });
  const clr = document.createElement("span");
  clr.className = "chip hist"; clr.textContent = "清除";
  clr.onclick = () => {
    catSel.clear();
    Array.from(catsBox.querySelectorAll(".chip")).forEach(x => x.classList.remove("on"));
    clr.classList.add("on");
    if (qEl.value.trim()) run();
    setTimeout(() => clr.classList.remove("on"), 700);
  };
  catsBox.appendChild(clr);
}
function renderHist(){
  histRow.innerHTML = "";
  if (!RECENT.length) return;
  const lb = document.createElement("span");
  lb.className = "lb"; lb.textContent = "最近搜过：";
  histRow.appendChild(lb);
  RECENT.slice(0, 8).forEach(t => {
    const b = document.createElement("span");
    b.className = "chip hist"; b.textContent = t;
    b.onclick = () => { qEl.value = t; run(); };
    histRow.appendChild(b);
  });
}
function renderTop(){
  topSel.innerHTML = "";
  TOP_OPTS[mode].forEach(o => {
    const op = document.createElement("option");
    op.value = o[0]; op.textContent = o[1];
    topSel.appendChild(op);
  });
  topSel.value = TOP_OPTS[mode][0][0];
}

/* ---------- 工具 ---------- */
function esc(s){
  return String(s == null ? "" : s).replace(/[&<>"]/g, c =>
    ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));
}
function fmt(s){
  s = Number(s) || 0;
  const m = Math.floor(s / 60), x = s - m * 60;
  return m + ":" + (x < 10 ? "0" : "") + x.toFixed(1);
}
function hi(s, qq){
  let out = esc(s);
  const keys = String(qq || "").split(/[\s，,、;；/|]+/).filter(k => k.length >= 1);
  keys.sort((a, b) => b.length - a.length);
  keys.forEach(k => {
    const safe = esc(k).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    try { out = out.replace(new RegExp(safe, "g"), m => "<mark>" + m + "</mark>"); } catch (e) {}
  });
  return out;
}
function skeletons(n){
  let h = "";
  for (let i = 0; i < n; i++)
    h += '<div class="sk"><div class="sh"></div>' +
         '<div class="sl" style="width:62%"></div>' +
         '<div class="sl" style="width:40%"></div></div>';
  return h;
}
function copyText(btn, text){
  const done = () => { const o = btn.textContent; btn.textContent = "✓复制";
    setTimeout(() => { btn.textContent = o; }, 900); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, done);
  } else {
    const ta = document.createElement("textarea");
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) {}
    document.body.removeChild(ta); done();
  }
}
function setMode(m){
  mode = m;
  $("tabImg").classList.toggle("on", m === "img");
  $("tabSub").classList.toggle("on", m === "sub");
  $("tabTl").classList.toggle("on", m === "tl");
  qEl.placeholder = PLACEHOLDER[m];
  renderChips(); renderTop();
  grid.innerHTML = ""; metaEl.textContent = ""; sel = -1;
  emptyEl.style.display = "block";
  emptyEl.textContent = m === "img"
    ? "输入中文描述后回车，结果即时返回（无需重跑脚本）"
    : (m === "sub" ? "输入台词关键词后回车，会列出含该词的素材与精确时间码"
                   : "先做一次画面检索，再切到时间线即可看到「画面帧 + 台词」合并的时间轴");
}
function hint(txt){
  if (!txt) return "";
  return '<span class="hint">' + txt + "</span>";
}

/* ---------- 渲染：画面结果 ---------- */
function renderCards(data, qtext){
  const rs = data.results || [];
  const mx = rs.length ? Math.max.apply(null, rs.map(r => Number(r.sim) || 0)) : 1;
  grid.innerHTML = rs.map((r, i) => {
    const pct = mx > 0 ? Math.max(6, Math.round((Number(r.sim) / mx) * 100)) : 0;
    const kw = (r.keywords || []).slice(0, 5).map(k => "<span>" + esc(k) + "</span>").join("");
    const hit = (r.hits && r.hits.length)
      ? '<div class="why">命中描述关键词：' + r.hits.map(esc).join(" / ") + "</div>" : "";
    const desc = r.desc ? "<div class=\"desc\">" + hi(r.desc, qtext) + "</div>" : "";
    const subs = (r.subs && r.subs.length)
      ? '<div class="subs">' + r.subs.slice(0, 12).map(s =>
          "<div><span class='st'>" + fmt(s.s) + "</span>" + esc(s.t) + "</div>").join("") +
        (r.subs.length > 12 ? "<div>…共 " + r.subs.length + " 句</div>" : "") + "</div>" : "";
    return '<figure class="card" data-i="' + i + '" style="animation-delay:' + Math.min(i * 22, 400) + 'ms">' +
      '<div class="thumb"><span class="rk">#' + r.rank + "</span>" +
      '<img loading="lazy" data-src="frames/' + encodeURIComponent(r.img) + '" alt=""></div>' +
      "<figcaption>" +
        '<div class="fname">' + esc(r.clip) +
          '<span class="cp" data-copy="' + esc(r.clip) + '">复制</span></div>' +
        '<div class="m">' + esc(r.group) + " · 全长 " + esc(r.dur) + "s</div>" +
        '<div class="pos">第 ' + esc(r.frame) + " 帧 · 约 " + esc(r.at) + " 处" +
          (r.approx_sec ? "（" + esc(r.approx_sec) + "）" : "") + "</div>" +
        (kw ? '<div class="kw">' + kw + "</div>" : "") +
        hit +
        '<div class="bwrap"><div class="bar2"><i style="width:' + pct + '%"></i></div>' +
          '<span class="sc">' + r.score + "</span></div>" +
        desc + subs +
      "</figcaption></figure>";
  }).join("");
  hydrateImgs();
}

function hydrateImgs(){
  const imgs = grid.querySelectorAll("img[data-src]");
  Array.prototype.forEach.call(imgs, im => {
    const src = im.getAttribute("data-src");
    if (!src) return;
    im.removeAttribute("data-src");
    im.src = src;          /* 图片默认可见，不再靠 JS 加类才显示 */
  });
}

/* ---------- 渲染：台词结果 ---------- */
function renderSubs(data, qtext){
  const rs = data.results || [];
  grid.innerHTML = '<div style="grid-column:1/-1">' + rs.map(r => {
    const badge = r.match === "semantic"
      ? '<span class="tagm sem">语义近似</span>' : '<span class="tagm">关键词命中</span>';
    const lines = (r.hits || []).map(h =>
      '<div class="ln"><span class="ts">' + fmt(h.s) + " → " + fmt(h.e) + "</span>" +
      '<span class="tx">' + hi(h.t, qtext) + "</span></div>").join("");
    return '<div class="subcard"><div class="hd"><span class="cid">' + esc(r.clip) + "</span>" +
      badge + '<span class="dur">全长 ' + (Math.round((Number(r.dur) || 0) * 10) / 10) + "s</span>" +
      '<span class="sc2">命中 ' + (r.hits || []).length + " 句</span></div>" + lines + "</div>";
  }).join("") + "</div>";
}

/* ---------- 渲染：时间线 ---------- */
function renderTimeline(data){
  const ev = data.timeline || [];
  let cur = null, rows = [];
  ev.forEach(e => {
    if (e.clip !== cur) { cur = e.clip; rows.push('<tr><td class="cl" colspan="3" style="background:#fafbfc">' + esc(cur) + "</td></tr>"); }
    if (e.kind === "frame") {
      rows.push('<tr><td class="ts">' + (e.sec == null ? "—" : fmt(e.sec)) + "</td>" +
        '<td><img loading="lazy" data-src="frames/' + encodeURIComponent(e.img) + '" alt=""></td>' +
        '<td><span class="tlfr">画面 · ' + esc(e.label) + "</span>" +
        (e.desc ? '<div class="tlsub">' + esc(e.desc).slice(0, 150) + "</div>" : "") + "</td></tr>");
    } else {
      rows.push('<tr><td class="ts">' + fmt(e.sec) + "</td><td></td>" +
        '<td class="tlsub">台词 · ' + esc(e.text) + "</td></tr>");
    }
  });
  grid.innerHTML = '<div style="grid-column:1/-1"><table class="tl">' +
    "<thead><tr><th>时间码</th><th>画面</th><th>内容</th></tr></thead><tbody>" +
    rows.join("") + "</tbody></table></div>";
  hydrateImgs();
}

/* ---------- 空状态 ---------- */
function showEmpty(msg, sugg){
  grid.innerHTML = ""; metaEl.textContent = ""; emptyEl.style.display = "block";
  emptyEl.innerHTML = esc(msg) + (sugg && sugg.length
    ? "<br>要不要试试：" + sugg.map(s => '<code data-s="' + esc(s) + '">' + esc(s) + "</code>").join("　")
    : "");
  Array.prototype.forEach.call(emptyEl.querySelectorAll("code[data-s]"), c => {
    c.style.cursor = "pointer";
    c.onclick = () => { qEl.value = c.getAttribute("data-s"); run(); };
  });
}

/* ---------- 主流程 ---------- */
async function run(){
  const text = qEl.value.trim();
  if (!text || busy) { if (!text) qEl.focus(); return; }
  busy = true;
  const my = ++seq;
  metaEl.innerHTML = '<span class="spin"></span>检索中…';
  emptyEl.style.display = "none";
  grid.innerHTML = mode === "tl" ? "" : skeletons(Math.min(Number(topSel.value) || 12, 8));
  /* 画面 / 时间线 走 /api/search；台词走 /api/subs（要带词，不能带 dedup） */
  const url = (mode === "sub")
    ? "/api/subs?q=" + encodeURIComponent(text) + "&top=" + encodeURIComponent(topSel.value)
    : "/api/search?q=" + encodeURIComponent(text) +
      "&top=" + encodeURIComponent(topSel.value) +
      "&dedup=" + (dedup ? 1 : 0) +
      (catSel.size ? "&cats=" + encodeURIComponent(Array.from(catSel).join("|")) : "") +
      (mode === "tl" ? "&timeline=1" : "");
  const t0 = performance.now();
  try {
    const res = await fetch(url);
    const data = await res.json();
    if (my !== seq) return;
    const dt = Math.round(performance.now() - t0);
    lastData = data;
    const rs = data.results || [];
    const h = data.meta && data.meta.hint ? hint(data.meta.hint) : "";
    if (!rs.length) {
      showEmpty(mode === "img" ? "没有结果（或分类筛选把它们全挡掉了）" : "没有命中",
        mode === "img" ? ["武馆 训练", "手部特写", "抱拳行礼", "夜晚 户外"] : ["武馆", "师父", "训练"]);
      if (catSel.size) metaEl.innerHTML = hint("当前有分类筛选，点「清除」放开试试");
      return;
    }
    if (mode === "sub") {
      metaEl.innerHTML = "台词「" + esc(text) + "」· " + rs.length + " 条素材 · 服务端 " +
        data.ms + "ms · 往返 " + dt + "ms" + h;
      renderSubs(data, text);
    } else if (mode === "tl") {
      metaEl.innerHTML = "时间线「" + esc(text) + "」· " + rs.length + " 条素材 / " +
        ((data.timeline || []).length) + " 个事件 · 服务端 " + data.ms + "ms · 往返 " + dt + "ms" + h;
      renderTimeline(data);
    } else {
      metaEl.innerHTML = "「" + esc(text) + "」· " + rs.length + " 条结果 · 服务端 " +
        data.ms + "ms · 往返 " + dt + "ms" +
        (dedup ? " · 同素材已去重" : " · 含同素材多帧") + h;
      renderCards(data, text);
    }
    sel = -1;
  } catch (err) {
    if (my === seq) showEmpty("请求失败：" + err.message);
  } finally { busy = false; }
}

/* ---------- 交互 ---------- */
function cards(){ return Array.prototype.slice.call(grid.querySelectorAll(".card")); }
function select(i){
  const cs = cards();
  if (!cs.length) return;
  sel = (i + cs.length) % cs.length;
  cs.forEach((c, k) => c.classList.toggle("sel", k === sel));
  cs[sel].scrollIntoView({ block: "nearest", behavior: "smooth" });
}
grid.addEventListener("click", ev => {
  const cp = ev.target.closest(".cp");
  if (cp) { copyText(cp, cp.getAttribute("data-copy")); ev.stopPropagation(); return; }
  const c = ev.target.closest(".card");
  if (c) { c.classList.toggle("open"); select(cards().indexOf(c)); }
});
$("go").onclick = run;
$("tabImg").onclick = () => setMode("img");
$("tabSub").onclick = () => setMode("sub");
$("tabTl").onclick = () => setMode("tl");
rawBtn.onclick = () => {
  dedup = !dedup;
  rawBtn.textContent = dedup ? "同素材多帧" : "去重已关";
  rawBtn.classList.toggle("on", !dedup);
  if (qEl.value.trim()) run();
};
$("help").onclick = () => {
  const on = tipBox.style.display !== "none";
  tipBox.style.display = on ? "none" : "block";
  tipBox.innerHTML = HELP;
  $("help").classList.toggle("on", !on);
};
qEl.addEventListener("keydown", e => { if (e.key === "Enter") run(); });
document.addEventListener("keydown", e => {
  const typing = document.activeElement === qEl;
  if (e.key === "/" && !typing) { e.preventDefault(); qEl.focus(); return; }
  if (e.key === "Escape") { qEl.value = ""; qEl.focus(); return; }
  if (typing) return;
  if (e.key === "ArrowRight" || e.key === "ArrowDown") { e.preventDefault(); select(sel + 1); }
  else if (e.key === "ArrowLeft" || e.key === "ArrowUp") { e.preventDefault(); select(sel - 1); }
  else if (e.key === "Enter") {
    const cs = cards();
    if (cs[sel]) { cs[sel].classList.toggle("open"); e.preventDefault(); }
  }
});

/* ---------- 初始化 ---------- */
setMode("img");
renderCats();
renderHist();

/* URL 参数：?q=抱拳&mode=tl&auto=1 —— 方便把某次检索分享/收藏 */
(function initFromUrl(){
  const sp = new URLSearchParams(location.search);
  const m = sp.get("mode");
  if (m && TOP_OPTS[m]) setMode(m);
  const t0 = sp.get("top");
  if (t0) {
    const has = Array.prototype.some.call(topSel.options, o => o.value === t0);
    if (has) topSel.value = t0;
    else { const op = document.createElement("option");
           op.value = t0; op.textContent = t0 + " 条（来自链接）";
           topSel.appendChild(op); topSel.value = t0; }
  }
  const cc = sp.get("cats");
  if (cc) cc.split("|").forEach(c => { if (CATS.indexOf(c) >= 0) catSel.add(c); });
  if (catSel.size)
    Array.prototype.forEach.call(catsBox.querySelectorAll(".chip"), x => {
      if (catSel.has(x.textContent)) x.classList.add("on");
    });
  const uq = (sp.get("q") || "").trim();
  if (uq) { qEl.value = uq; run(); return; }
  if (RECENT.length) qEl.value = RECENT[0];
})();