// Search. Ranking is BM25 (k1 1.2, b 0.75) over text blocks, with a field boost for headings and captions,
// a bonus when the query words appear as an exact phrase, and a smaller bonus when they appear close together.
// Hebrew: niqqud is ignored, and the one-letter prefixes ו ה ב ל מ ש כ may stand before a query word.
// Every query word must match (AND). The index loads on first use.
const PREFIX_LETTERS = "והבלמשכ";
// A two-letter word like "ים" hides inside many words as prefix + word ("מים" is water, not "from the sea"),
// so short words take only the article and the commonest prepositions. Limit: "מהים" ("from the sea") is missed.
const SHORT_PREFIXES = new Set(["ה", "ב", "ל", "ו", "וה", "וב", "ול"]);
const BOOST = { heading: 2.5, figure: 1.1, text: 1 }; // A caption ranks just above text with the same words.
const RECENT_KEY = "eli-raz:recent-searches";

// Token: a run of letters, digits and marks, with geresh and gershayim inside words (צה"ל, ג'ורג').
const TOKEN = /[\p{L}\p{N}\p{M}'"׳״]+/gu;
function normalizeWord(word) {
  let out = "";
  for (const c of word.normalize("NFC")) {
    const cp = c.codePointAt(0);
    if ((cp >= 0x0591 && cp <= 0x05c7) || "'\"׳״".includes(c)) continue;
    out += c;
  }
  return out.toLowerCase();
}
function tokenize(text) {
  const tokens = [];
  for (const m of text.matchAll(TOKEN)) {
    const word = normalizeWord(m[0]);
    if (word) tokens.push({ word, start: m.index, end: m.index + m[0].length });
  }
  return tokens;
}
// How well a word in the book matches a query word: 1 exact, 0.8 after allowed prefixes, 0.5 as the start of a
// longer word (only for the last query word, which may still be typed), 0 no match.
function wordMatch(word, term, last) {
  if (word === term) return 1;
  for (let cut = 1; cut <= 3 && cut < word.length; cut++) {
    const prefix = word.slice(0, cut);
    if (![...prefix].every((c) => PREFIX_LETTERS.includes(c))) break;
    if (word.slice(cut) === term && (term.length > 2 || SHORT_PREFIXES.has(prefix))) return 0.8;
    if (last && term.length >= 3 && word.slice(cut).startsWith(term)) return 0.4;
  }
  if (last && term.length >= 3 && word.startsWith(term)) return 0.5;
  return 0;
}

let searchIndex = null;
async function loadIndex() {
  if (searchIndex) return searchIndex;
  const response = await fetch("search.json");
  if (!response.ok) throw new Error(`search.json: HTTP ${response.status}`);
  const { pages, entries, variants = [] } = await response.json();
  const vocabulary = new Map(); // word -> [entry index, ...] (repeats count as term frequency)
  let totalLength = 0;
  entries.forEach((e, i) => { e.loc = i + 1; });
  // Variants: another text of a block, such as the printed form of a corrected block. Found by search,
  // shown and located as that block.
  const block = new Map(entries.map((e) => [e.id, e]));
  const all = [...entries, ...variants.map((v) => ({ ...block.get(v.id), text: v.text }))];
  all.forEach((e, i) => {
    e.tokens = tokenize(e.text);
    totalLength += e.tokens.length;
    for (const t of e.tokens) {
      if (!vocabulary.has(t.word)) vocabulary.set(t.word, []);
      vocabulary.get(t.word).push(i);
    }
  });
  searchIndex = { pages, entries, all, vocabulary, avgLength: totalLength / all.length };
  return searchIndex;
}

function rank(index, terms) {
  const { all: entries, vocabulary, avgLength } = index;
  const N = entries.length;
  // For each query word: entry index -> summed match weight, and the matching vocabulary words.
  const perTerm = terms.map((term, ti) => {
    const weights = new Map(), words = new Map();
    for (const [word, postings] of vocabulary) {
      const w = wordMatch(word, term, ti === terms.length - 1);
      if (!w) continue;
      words.set(word, w);
      for (const i of postings) weights.set(i, (weights.get(i) ?? 0) + w);
    }
    return { weights, words };
  });
  if (perTerm.some((t) => t.weights.size === 0)) return [];
  const [first, ...rest] = perTerm;
  const hits = [];
  for (const [i] of first.weights) {
    if (!rest.every((t) => t.weights.has(i))) continue;
    const e = entries[i];
    let score = 0;
    for (const t of perTerm) {
      const tf = t.weights.get(i), df = t.weights.size;
      const idf = Math.log(1 + (N - df + 0.5) / (df + 0.5));
      score += idf * (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * e.tokens.length / avgLength));
    }
    score *= BOOST[e.kind];
    // Positions of each query word in this entry, for the phrase and proximity bonus and for highlights.
    const positions = perTerm.map((t) => e.tokens.flatMap((tok, p) => (t.words.has(tok.word) ? [p] : [])));
    let phrase = false, span = Infinity;
    if (terms.length > 1) {
      phrase = positions[0].some((p) => positions.every((list, k) => list.includes(p + k)));
      // Smallest window that holds every query word: walk the first word's positions.
      for (const p of positions[0]) {
        let lo = p, hi = p;
        for (const list of positions.slice(1)) {
          const near = list.reduce((best, q) => (Math.abs(q - p) < Math.abs(best - p) ? q : best), list[0]);
          lo = Math.min(lo, near); hi = Math.max(hi, near);
        }
        span = Math.min(span, hi - lo + 1);
      }
      score *= phrase ? 3 : 1 + 1 / Math.max(1, span - terms.length + 1);
    }
    hits.push({ e, score, phrase, marks: positions.flat().map((p) => e.tokens[p]) });
  }
  // Exact phrase hits first, then by score.
  return hits.sort((a, b) => (b.phrase - a.phrase) || (b.score - a.score));
}

function snippet(e, marks) {
  const frag = document.createDocumentFragment();
  const text = e.text;
  const sorted = marks.toSorted((a, b) => a.start - b.start);
  const from = Math.max(0, (sorted[0]?.start ?? 0) - 50);
  const to = Math.min(text.length, from + 220);
  if (from > 0) frag.append("…");
  let at = from;
  for (const m of sorted) {
    if (m.start < at || m.end > to) continue;
    frag.append(text.slice(at, m.start));
    const mark = document.createElement("mark");
    mark.textContent = text.slice(m.start, m.end);
    frag.append(mark);
    at = m.end;
  }
  frag.append(text.slice(at, to) + (to < text.length ? "…" : ""));
  return frag;
}

// "Go to": a number, "עמ' 123" or "עמוד 123" goes to that printed page; "מיקום 123" goes to that location.
function goToTargets(query, index) {
  const q = query.trim();
  const digits = (s) => (/^\d{1,5}$/.test(s) ? Number(s) : null);
  const out = [];
  let page = digits(q), loc = digits(q);
  const pageWord = ["עמוד", "עמ'", "עמ׳", "עמ"].find((w) => q.startsWith(w));
  const locWord = ["מיקום", "loc"].find((w) => q.startsWith(w));
  if (pageWord) { page = digits(q.slice(pageWord.length).trim()); loc = null; }
  if (locWord) { loc = digits(q.slice(locWord.length).trim()); page = null; }
  if (page !== null && index.pages[String(page)]) out.push({ id: index.pages[String(page)], label: `מעבר לעמוד ${page} בספר המודפס` });
  if (loc !== null && loc >= 1 && loc <= index.entries.length) out.push({ id: index.entries[loc - 1].id, label: `מעבר למיקום ${loc}` });
  return out;
}

function readRecent() {
  try { return JSON.parse(localStorage.getItem(RECENT_KEY) ?? "[]").filter((q) => typeof q === "string"); }
  catch { return []; }
}
function saveRecent(query) {
  const q = query.trim();
  if (!q) return;
  try { localStorage.setItem(RECENT_KEY, JSON.stringify([q, ...readRecent().filter((x) => x !== q)].slice(0, 6))); }
  catch { /* Private mode or blocked storage: recent searches are a convenience only. */ }
}

const searchDialog = byId("search-dialog");
const input = byId("search-input");
const results = byId("search-results");
const status = byId("search-status");
function resultItem({ href, where, body, thumb, tile, onPick }) {
  const li = document.createElement("li");
  const a = document.createElement("a");
  a.href = href;
  if (thumb) {
    const img = document.createElement("img");
    Object.assign(img, { src: thumb, alt: "", width: 48, height: 48, loading: "lazy", className: "result-thumb" });
    a.append(img);
  } else if (tile) {
    a.append(tile);
  }
  const text = document.createElement("span");
  text.className = "result-text";
  if (where) {
    const w = document.createElement("span");
    w.className = "where";
    w.textContent = where;
    text.append(w);
  }
  text.append(body);
  a.append(text);
  a.addEventListener("click", (e) => { e.preventDefault(); onPick(); });
  li.append(a);
  return li;
}
function placeTile(chapter) {
  const list = placesByChapter.get(chapter);
  if (!list) return null;
  const tile = document.createElement("span");
  tile.className = "result-tile";
  tile.setAttribute("aria-hidden", "true");
  tile.innerHTML = '<svg viewBox="0 0 24 24"><path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/></svg>';
  tile.style.setProperty("--place", `var(--place-${list[0].n})`);
  return tile;
}
// The empty panel offers the reader's recent searches, a few example queries and the page-jump hint.
const EXAMPLES = ["בולענים", "ים המלח", "עמ' 100"];
function showRecent() {
  results.replaceChildren();
  const recent = readRecent();
  const offer = (q) => resultItem({ href: "#", body: q, onPick: () => { input.value = q; runSearch(); input.focus(); } });
  status.textContent = recent.length ? "חיפושים אחרונים" : "למשל:";
  for (const q of recent.length ? recent : EXAMPLES) results.append(offer(q));
  const hint = document.createElement("li");
  hint.className = "search-hint";
  hint.textContent = "מספר עמוד, כמו 120 או עמ' 120, מוביל לעמוד בספר המודפס.";
  results.append(hint);
}
async function runSearch() {
  const query = input.value;
  const terms = tokenize(query).map((t) => t.word);
  if (!query.trim()) { showRecent(); return; }
  const index = await loadIndex();
  if (input.value !== query) return; // A newer query is on its way.
  results.replaceChildren();
  const pick = (id, marks = []) => { saveRecent(query); goTo(id, { marks }); };
  const jumps = goToTargets(query, index);
  for (const j of jumps) results.append(resultItem({ href: `#${j.id}`, body: j.label, onPick: () => pick(j.id) }));
  const seen = new Set(); // A block and its variant can both match: keep the better hit.
  const hits = (terms.length ? rank(index, terms) : []).filter((h) => !seen.has(h.e.id) && seen.add(h.e.id));
  status.textContent = hits.length === 0 && jumps.length === 0 ? "לא נמצאו תוצאות" : hits.length === 1 ? "תוצאה אחת" : hits.length ? `${hits.length} תוצאות` : "";
  for (const { e, marks } of hits.slice(0, 80)) {
    const where = [e.section, e.page ? `עמ' ${e.page}` : null].filter(Boolean).join(" · ");
    results.append(resultItem({
      href: `#${e.id}`, where, body: snippet(e, marks), thumb: e.thumb,
      tile: e.kind === "heading" ? placeTile(e.chapter) : null, onPick: () => pick(e.id, [...new Set(marks.map((m) => e.text.slice(m.start, m.end)))]),
    }));
  }
}
overlayOpeners["search-dialog"] = () => searchDialog.showModal();
function openSearch() {
  openOverlay(searchDialog, () => searchDialog.showModal());
  input.focus(); // In the same user gesture, so phones raise the keyboard.
  input.select();
  if (!input.value) showRecent();
}
for (const button of document.querySelectorAll("[data-open='search-dialog']")) {
  button.addEventListener("click", openSearch);
  // Fetch and index the book while the reader is about to open search, so the first query answers at once.
  for (const type of ["pointerenter", "focus"]) button.addEventListener(type, () => loadIndex().catch(() => {}), { once: true });
}
let searchTimer = 0;
input.addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(runSearch, 100); });
byId("search-form").addEventListener("submit", (e) => { e.preventDefault(); results.querySelector("a")?.click(); });
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !e.target.closest("input, textarea, dialog")) {
    e.preventDefault();
    openSearch();
  }
});

