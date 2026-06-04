"""
Query Input — DataPilot AI
VSCode IntelliSense-style autocomplete injected into Streamlit via components.html.

JavaScript engine features:
  - Real-time suggestions on every keystroke (no Python round-trip)
  - Cursor-position-aware word detection (selectionStart)
  - Prefix + contains + fuzzy matching
  - Keyboard: Arrow Up/Down, Enter, Tab, Escape
  - Mouse click selection
  - Replaces only the current word, preserves rest of query
  - Positioned below the textarea, flips up if near screen bottom
  - No lag, no flicker, no duplicate dropdowns
  - Quick suggestions inject text via React-compatible setter
"""
from __future__ import annotations

import json
from typing import Dict, List, Tuple

import streamlit as st
import streamlit.components.v1 as components
from utils.icons import get_icon

# ─────────────────────────────────────────────────────────────────────────────
# SQL keyword bank
# ─────────────────────────────────────────────────────────────────────────────
_SQL_KEYWORDS = [
    "SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT",
    "OFFSET", "JOIN", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "FULL JOIN",
    "CROSS JOIN", "ON", "AS", "DISTINCT", "AND", "OR", "NOT", "IN",
    "NOT IN", "BETWEEN", "LIKE", "IS NULL", "IS NOT NULL", "CASE", "WHEN",
    "THEN", "ELSE", "END", "UNION", "UNION ALL", "WITH",
    "COUNT", "SUM", "AVG", "MAX", "MIN", "COALESCE", "NULLIF", "IFNULL",
    "CONCAT", "SUBSTRING", "TRIM", "UPPER", "LOWER", "ROUND", "ABS",
    "DATE_FORMAT", "DATE_TRUNC", "YEAR", "MONTH", "DAY", "NOW", "CURDATE",
    "CAST", "CONVERT", "ROW_NUMBER", "RANK", "DENSE_RANK", "OVER",
    "PARTITION BY", "LAG", "LEAD",
]

_BUSINESS_PHRASES = [
    "total revenue", "monthly revenue", "monthly trend", "top 10",
    "year over year", "month over month", "growth rate", "breakdown by",
    "average order value", "customer count", "unique customers",
    "distribution of", "running total", "moving average",
]


# ─────────────────────────────────────────────────────────────────────────────
# Token builder
# ─────────────────────────────────────────────────────────────────────────────
def _build_tokens() -> List[Dict]:
    """Build deduplicated token list for JS from live schema + keywords."""
    items: List[Dict] = []
    seen: set = set()

    schema_raw = st.session_state.get("schema_raw", {})
    for table in schema_raw.get("tables", []):
        tname = table.get("name", "")
        if tname and tname.lower() not in seen:
            seen.add(tname.lower())
            items.append({"d": tname, "t": "tbl", "l": tname.lower()})
        for col in table.get("columns", []):
            cname = col.get("name", "")
            if cname and cname.lower() not in seen:
                seen.add(cname.lower())
                items.append({"d": cname, "t": "col", "l": cname.lower()})

    for kw in _SQL_KEYWORDS:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            items.append({"d": kw, "t": "kw", "l": kw.lower()})

    for ph in _BUSINESS_PHRASES:
        if ph.lower() not in seen:
            seen.add(ph.lower())
            items.append({"d": ph, "t": "nl", "l": ph.lower()})

    return items


# ─────────────────────────────────────────────────────────────────────────────
# JS IntelliSense engine injected into parent DOM
# ─────────────────────────────────────────────────────────────────────────────
_JS_ENGINE = r"""
(function() {
  'use strict';

  var TOKENS = __TOKENS__;
  var doc = window.parent.document;
  var win = window.parent;

  var DROPDOWN_ID = 'dp-intellisense';
  var STYLE_ID    = 'dp-intellisense-style';
  var MAX         = 10;
  var DELIMITERS  = /[\s,();=<>!+\-*\/\[\]{}'"]/;

  var dd = null, items = [], activeIdx = -1, attachedTA = null;

  // ── CSS injected once into parent head ──────────────────────────────
  function injectStyles() {
    if (doc.getElementById(STYLE_ID)) return;
    var s = doc.createElement('style');
    s.id = STYLE_ID;
    s.textContent = [
      '#'+DROPDOWN_ID+'{position:fixed;z-index:2147483647;display:none;',
        'background:rgba(10,14,28,0.98);border:1px solid rgba(99,102,241,.42);',
        'border-radius:10px;box-shadow:0 16px 48px rgba(0,0,0,.7),0 0 0 1px rgba(99,102,241,.1);',
        'max-height:280px;overflow-y:auto;min-width:240px;max-width:400px;',
        'padding:4px 0;font-family:Inter,-apple-system,sans-serif;}',
      '#'+DROPDOWN_ID+'::-webkit-scrollbar{width:4px}',
      '#'+DROPDOWN_ID+'::-webkit-scrollbar-thumb{background:rgba(99,102,241,.4);border-radius:2px}',
      '.dp-hdr{padding:4px 14px 2px;font-size:10px;color:#475569;letter-spacing:.8px;',
        'text-transform:uppercase;font-weight:700;border-bottom:1px solid rgba(99,102,241,.12);margin-bottom:3px}',
      '.dp-row{display:flex;align-items:center;gap:8px;padding:6px 10px;cursor:pointer;',
        'border-radius:7px;margin:1px 4px;transition:background .08s}',
      '.dp-row:hover,.dp-row.dp-active{background:rgba(99,102,241,.18)}',
      '.dp-badge{font-size:9px;font-weight:700;padding:1px 5px;border-radius:4px;',
        'text-transform:uppercase;letter-spacing:.5px;flex-shrink:0;min-width:27px;text-align:center}',
      '.dp-col{background:rgba(99,102,241,.18);color:#818CF8;border:1px solid rgba(99,102,241,.3)}',
      '.dp-tbl{background:rgba(20,184,166,.14);color:#2DD4BF;border:1px solid rgba(20,184,166,.25)}',
      '.dp-kw{background:rgba(245,158,11,.12);color:#FBBF24;border:1px solid rgba(245,158,11,.2)}',
      '.dp-nl{background:rgba(236,72,153,.12);color:#F472B6;border:1px solid rgba(236,72,153,.2)}',
      '.dp-txt{font-size:13px;color:#CBD5E1;flex:1;',
        "font-family:'JetBrains Mono','Fira Code',monospace;",
        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.dp-hi{color:#A78BFA;font-weight:700}',
    ].join('');
    doc.head.appendChild(s);
  }

  // ── Create dropdown div once ─────────────────────────────────────────
  function ensureDropdown() {
    if (doc.getElementById(DROPDOWN_ID)) {
      dd = doc.getElementById(DROPDOWN_ID);
      return;
    }
    dd = doc.createElement('div');
    dd.id = DROPDOWN_ID;
    doc.body.appendChild(dd);
    dd.addEventListener('mousedown', function(e){ e.preventDefault(); }); // prevent blur
  }

  // ── Find Streamlit textarea ──────────────────────────────────────────
  function findTA() {
    var sels = [
      'textarea[aria-label="Ask anything"]',
      '.stTextArea textarea',
      'section[data-testid="stMain"] textarea',
      'textarea'
    ];
    for (var i = 0; i < sels.length; i++) {
      var el = doc.querySelector(sels[i]);
      if (el) return el;
    }
    return null;
  }

  // ── Get word at cursor ───────────────────────────────────────────────
  function wordAtCursor(ta) {
    var val = ta.value, pos = ta.selectionStart, start = pos;
    while (start > 0 && !DELIMITERS.test(val[start - 1])) start--;
    return { word: val.substring(start, pos), start: start, end: pos };
  }

  // ── Match tokens ─────────────────────────────────────────────────────
  function match(word) {
    if (!word) return [];
    var l = word.toLowerCase(), prefix = [], contains = [];
    for (var i = 0; i < TOKENS.length; i++) {
      var t = TOKENS[i];
      if (t.l === l) continue;                    // skip exact (already typed)
      if (t.l.startsWith(l)) prefix.push(t);
      else if (t.l.indexOf(l) !== -1) contains.push(t);
    }
    return prefix.concat(contains).slice(0, MAX);
  }

  // ── Highlight matched portion ────────────────────────────────────────
  function highlight(display, word) {
    var idx = display.toLowerCase().indexOf(word.toLowerCase());
    if (idx === -1) return escHtml(display);
    return escHtml(display.slice(0, idx))
         + "<span class='dp-hi'>" + escHtml(display.slice(idx, idx + word.length)) + "</span>"
         + escHtml(display.slice(idx + word.length));
  }

  function escHtml(s) {
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }

  // ── Render dropdown ──────────────────────────────────────────────────
  function renderDD(word) {
    if (!dd || items.length === 0) { hide(); return; }
    var html = "<div class='dp-hdr'>\u{1F4A1} " + items.length + " schema suggestions</div>";
    for (var i = 0; i < items.length; i++) {
      var t = items[i], bc = 'dp-' + t.t;
      var lbl = t.t === 'col' ? 'COL' : t.t === 'tbl' ? 'TBL' : t.t === 'kw' ? 'SQL' : 'NL';
      html += "<div class='dp-row" + (i === activeIdx ? ' dp-active' : '')
            + "' data-idx='" + i + "'>"
            + "<span class='dp-badge " + bc + "'>" + lbl + "</span>"
            + "<span class='dp-txt'>" + highlight(t.d, word) + "</span>"
            + "</div>";
    }
    dd.innerHTML = html;
    dd.querySelectorAll('.dp-row').forEach(function(row) {
      row.addEventListener('mousedown', function(e) {
        e.preventDefault();
        selectItem(parseInt(this.getAttribute('data-idx')));
      });
    });
    show();
  }

  // ── Position below textarea ──────────────────────────────────────────
  function position() {
    if (!attachedTA || !dd) return;
    var r = attachedTA.getBoundingClientRect();
    var vh = win.innerHeight, vw = win.innerWidth;
    var dropH = Math.min(280, items.length * 34 + 30);
    var top = r.bottom + 4;
    if (top + dropH > vh - 8) top = r.top - dropH - 4;
    var left = r.left;
    if (left + 400 > vw - 8) left = vw - 408;
    dd.style.top  = top  + 'px';
    dd.style.left = left + 'px';
    dd.style.width = Math.min(r.width, 400) + 'px';
  }

  function show() { dd.style.display = 'flex'; dd.style.flexDirection = 'column'; position(); }
  function hide() { if (dd) dd.style.display = 'none'; activeIdx = -1; items = []; }

  // ── Set active row ───────────────────────────────────────────────────
  function setActive(idx) {
    var rows = dd.querySelectorAll('.dp-row');
    rows.forEach(function(r){ r.classList.remove('dp-active'); });
    if (idx >= 0 && idx < rows.length) {
      rows[idx].classList.add('dp-active');
      rows[idx].scrollIntoView({ block: 'nearest' });
    }
    activeIdx = idx;
  }

  // ── React-compatible value setter ────────────────────────────────────
  function setReactValue(ta, value) {
    var proto = Object.getOwnPropertyDescriptor(win.HTMLTextAreaElement.prototype, 'value');
    if (proto && proto.set) {
      proto.set.call(ta, value);
    } else {
      ta.value = value;
    }
    ta.dispatchEvent(new Event('input',  { bubbles: true }));
    ta.dispatchEvent(new Event('change', { bubbles: true }));
  }

  // ── Select a suggestion ──────────────────────────────────────────────────────
  function selectItem(idx) {
    if (idx < 0 || idx >= items.length || !attachedTA) return;
    var token = items[idx];
    var info  = wordAtCursor(attachedTA);
    var val   = attachedTA.value;
    // Always append a space after the selected token so cursor continues naturally
    var newVal = val.slice(0, info.start) + token.d + ' ' + val.slice(info.end);
    setReactValue(attachedTA, newVal);
    // Move cursor right after the inserted token + space
    var newPos = info.start + token.d.length + 1;
    attachedTA.setSelectionRange(newPos, newPos);
    attachedTA.focus();
    hide();
  }

  // ── Event handlers ───────────────────────────────────────────────────
  function onInput() {
    var info = wordAtCursor(attachedTA);
    items = match(info.word);
    activeIdx = -1;
    if (items.length > 0 && info.word.length >= 1) {
      renderDD(info.word);
    } else {
      hide();
    }
  }

  function onKeydown(e) {
    if (dd && dd.style.display !== 'none') {
      if (e.key === 'ArrowDown') {
        e.preventDefault(); e.stopPropagation();
        setActive(Math.min(activeIdx + 1, items.length - 1));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault(); e.stopPropagation();
        setActive(Math.max(activeIdx - 1, 0));
        return;
      }
      if ((e.key === 'Enter' || e.key === 'Tab') && activeIdx >= 0) {
        e.preventDefault(); e.stopPropagation();
        selectItem(activeIdx);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        hide();
        return;
      }
    }
  }

  function onBlur()  { setTimeout(hide, 150); }
  function onScroll(){ position(); }

  function onDocMousedown(e) {
    if (dd && !dd.contains(e.target) && e.target !== attachedTA) hide();
  }

  // ── React-compatible quick-suggestion fill (called from suggestion JS) ──
  win.__dpFillQuery = function(text) {
    var ta = findTA();
    if (!ta) return;
    setReactValue(ta, text);
    var end = text.length;
    ta.setSelectionRange(end, end);
    ta.focus();
    hide();
  };

  // ── Attach to textarea ───────────────────────────────────────────────
  function attach() {
    var ta = findTA();
    if (!ta) { setTimeout(attach, 400); return; }
    if (ta === attachedTA) return;
    if (attachedTA) {
      attachedTA.removeEventListener('input',   onInput);
      attachedTA.removeEventListener('keydown', onKeydown, true);
      attachedTA.removeEventListener('blur',    onBlur);
      attachedTA.removeEventListener('scroll',  onScroll);
    }
    attachedTA = ta;
    ta.addEventListener('input',   onInput);
    ta.addEventListener('keydown', onKeydown, true);
    ta.addEventListener('blur',    onBlur);
    ta.addEventListener('scroll',  onScroll);
    doc.addEventListener('mousedown', onDocMousedown);
  }

  // ── Boot ─────────────────────────────────────────────────────────────
  injectStyles();
  ensureDropdown();

  // Re-attach on DOM changes (handles Streamlit re-renders)
  var obs = new MutationObserver(function() {
    var ta = findTA();
    if (ta && ta !== attachedTA) attach();
  });
  obs.observe(doc.body, { childList: true, subtree: true });

  attach();
  __FOCUS_JS__
})();
"""


def _inject_intellisense(tokens: List[Dict], focus: bool = False) -> None:
    """Inject the JS autocomplete engine into the parent Streamlit document."""
    tokens_json = json.dumps(tokens)
    focus_js = (
        "(function(){ var ta=findTA(); if(ta){ ta.focus(); "
        "ta.setSelectionRange(ta.value.length,ta.value.length); } })();"
        if focus else ""
    )
    js = _JS_ENGINE.replace("__TOKENS__", tokens_json).replace("__FOCUS_JS__", focus_js)
    components.html(
        f"<!DOCTYPE html><html><body><script>{js}</script></body></html>",
        height=0,
        scrolling=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """
<style>
.qin-header{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.qin-icon{background:linear-gradient(135deg,#6366F1,#8B5CF6);border-radius:10px;
  width:36px;height:36px;display:flex;align-items:center;justify-content:center;
  color:white;flex-shrink:0;box-shadow:0 4px 12px rgba(99,102,241,.3)}
.qin-title{font-size:1rem;font-weight:700;color:#E2E8F0}
.qin-sub{font-size:.73rem;color:#64748B}

/* Action buttons styling and vertical alignment */
.action-row-anchor + div.element-container div[data-testid="stHorizontalBlock"] {
  align-items: center !important;
}
.action-row-anchor + div.element-container div[data-testid="column"] {
  display: flex !important;
  align-items: center !important;
}
.action-row-anchor + div.element-container div[data-testid="column"] [data-testid="stButton"] {
  width: 100% !important;
  margin: 0 !important;
}
.action-row-anchor + div.element-container div[data-testid="column"] [data-testid="stButton"] button {
  height: 38px !important;
  min-height: 38px !important;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  display: inline-flex !important;
  align-items: center !important;
  justify-content: center !important;
  width: 100% !important;
  box-sizing: border-box !important;
}

/* Quick suggestions horizontal chips styling */
.sug-header{font-size:.70rem;font-weight:700;color:#818CF8;text-transform:uppercase;
  letter-spacing:1px;margin-top:10px;margin-bottom:6px;padding-bottom:3px;
  border-bottom:1px solid rgba(99,102,241,.15)}

div[class^="sug-row-anchor"] + div.element-container div[data-testid="column"] {
  display: flex !important;
  align-items: stretch !important;
}
div[class^="sug-row-anchor"] + div.element-container div[data-testid="column"] [data-testid="stButton"] {
  width: 100% !important;
  height: 100% !important;
}
div[class^="sug-row-anchor"] + div.element-container div[data-testid="column"] [data-testid="stButton"] button {
  background: rgba(99,102,241,0.05) !important;
  border: 1px solid rgba(99,102,241,0.18) !important;
  color: #C084FC !important;
  border-radius: 8px !important;
  font-size: 0.76rem !important;
  padding: 6px 10px !important;
  transition: all 0.2s ease !important;
  white-space: normal !important;
  height: auto !important;
  min-height: 44px !important;
  text-align: center !important;
  line-height: 1.25 !important;
  display: flex !important;
  align-items: center !important;
  justify-content: center !important;
}
div[class^="sug-row-anchor"] + div.element-container div[data-testid="column"] [data-testid="stButton"] button:hover {
  background: rgba(99,102,241,0.12) !important;
  border-color: rgba(99,102,241,0.4) !important;
  box-shadow: 0 4px 12px rgba(99,102,241,0.2) !important;
  color: #E9D5FF !important;
  transform: translateY(-1px);
}

.voice-correction-banner{background:rgba(99,102,241,.07);
  border:1px solid rgba(99,102,241,.22);border-radius:8px;
  padding:8px 12px;margin-top:6px;font-size:.79rem;color:#94A3B8}
.voice-wrong{color:#F87171;text-decoration:line-through}
.voice-right{color:#34D399;font-weight:700;font-family:monospace}

/* ── Voice card shell ── */
.voice-system-card {
    background: linear-gradient(135deg, rgba(30,41,59,0.95), rgba(15,23,42,0.95));
    border: 1px solid rgba(99,102,241,0.22);
    border-radius: 14px;
    padding: 16px 18px 14px 18px;
    margin-top: 10px;
    position: relative;
    box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    transition: all 0.3s ease;
}
.voice-card-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
}
.voice-status-title {
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    text-transform: uppercase;
    display: flex;
    align-items: center;
    gap: 6px;
}
.voice-listening-label { color: #8B5CF6; }
.voice-processing-label { color: #F59E0B; }
.voice-caption {
    font-size: 0.75rem;
    color: #64748B;
    margin-bottom: 4px;
}

/* Live pulse dot */
.voice-live-dot {
    width: 7px; height: 7px;
    background: #8B5CF6;
    border-radius: 50%;
    display: inline-block;
    animation: live-pulse 1.4s infinite ease-in-out;
    box-shadow: 0 0 0 0 rgba(139,92,246,0.5);
}
@keyframes live-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(139,92,246,0.4); }
    70%  { box-shadow: 0 0 0 6px rgba(139,92,246,0); }
    100% { box-shadow: 0 0 0 0 rgba(139,92,246,0); }
}

/* Waveform bars */
.voice-wave-container {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 5px;
    height: 32px;
    margin: 14px 0 8px 0;
}
.voice-wave-bar {
    width: 3px;
    background: linear-gradient(180deg, #6366F1, #8B5CF6);
    border-radius: 2px;
    animation: pulse-wave 1.2s infinite ease-in-out;
}
.voice-wave-bar:nth-child(1) { height: 10px; animation-delay: 0.0s; }
.voice-wave-bar:nth-child(2) { height: 22px; animation-delay: 0.2s; }
.voice-wave-bar:nth-child(3) { height: 14px; animation-delay: 0.4s; }
.voice-wave-bar:nth-child(4) { height: 26px; animation-delay: 0.6s; }
.voice-wave-bar:nth-child(5) { height: 10px; animation-delay: 0.8s; }

@keyframes pulse-wave {
    0%, 100% { transform: scaleY(1); opacity: 0.8; }
    50%      { transform: scaleY(2.0); opacity: 1; }
}

/* Inline stop button wrapper positioning */
.voice-stop-container {
    display: flex;
    justify-content: flex-end;
    margin-top: -43px;
    margin-bottom: 25px;
    position: relative;
    z-index: 999;
}

/* Custom style override for the Stop button */
.voice-stop-container button {
    background: rgba(239, 68, 68, 0.15) !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
    color: #EF4444 !important;
    border-radius: 20px !important;
    font-size: 0.7rem !important;
    font-weight: 600 !important;
    padding: 2px 10px !important;
    width: auto !important;
    min-width: 0 !important;
    height: 22px !important;
    line-height: 1 !important;
    box-shadow: none !important;
    margin: 0 10px 0 0 !important;
    transition: all 0.2s ease !important;
}
.voice-stop-container button:hover {
    background: rgba(239, 68, 68, 0.25) !important;
    border-color: rgba(239, 68, 68, 0.5) !important;
    color: #F87171 !important;
    box-shadow: 0 0 8px rgba(239,68,68,0.3) !important;
}

.spin-loader {
    animation: spin-anim 1s linear infinite;
    display: inline-block;
}
@keyframes spin-anim {
    100% { transform: rotate(360deg); }
}

/* ── Responsive Query Input ── */
@media (max-width: 768px) {
    .qin-header { gap: 8px !important; margin-bottom: 6px !important; }
    .qin-icon { width: 30px !important; height: 30px !important; border-radius: 8px !important; }
    .qin-title { font-size: 0.88rem !important; }
    .qin-sub { font-size: 0.68rem !important; }
    .sug-header { font-size: 0.65rem !important; margin-top: 6px !important; }

    /* Suggestion chips: 2-column on tablet/mobile */
    div[class^="sug-row-anchor"] + div.element-container div[data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
    }
    div[class^="sug-row-anchor"] + div.element-container div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 48% !important;
        max-width: 48% !important;
        min-width: 48% !important;
    }
    div[class^="sug-row-anchor"] + div.element-container div[data-testid="column"] [data-testid="stButton"] button {
        font-size: 0.72rem !important;
        min-height: 40px !important;
        padding: 5px 8px !important;
    }

    /* Voice card compact */
    .voice-system-card { padding: 12px 14px 10px 14px !important; margin-top: 8px !important; }
    .voice-wave-container { height: 26px !important; margin: 10px 0 6px 0 !important; }
}
@media (max-width: 480px) {
    .qin-icon { width: 24px !important; height: 24px !important; border-radius: 6px !important; }
    .qin-title { font-size: 0.78rem !important; }
    .qin-sub { font-size: 0.6rem !important; }

    /* Suggestion chips: 1 column on small mobile, compact button padding and text */
    div[class^="sug-row-anchor"] + div.element-container div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        flex: 1 1 100% !important;
        max-width: 100% !important;
        min-width: 100% !important;
    }
    div[class^="sug-row-anchor"] + div.element-container div[data-testid="column"] [data-testid="stButton"] button {
        font-size: 0.68rem !important;
        min-height: 32px !important;
        padding: 3px 6px !important;
    }

    /* Voice card compact */
    .voice-system-card { padding: 8px 10px 6px 10px !important; margin-top: 6px !important; }
    .voice-wave-container { height: 20px !important; margin: 8px 0 4px 0 !important; }
    .voice-status-title { font-size: 0.7rem !important; }
    .voice-caption { font-size: 0.68rem !important; }
    .voice-live-dot { width: 5px !important; height: 5px !important; }
    .voice-stop-container { margin-top: -33px !important; margin-bottom: 18px !important; }
    .voice-stop-container button {
        height: 18px !important;
        font-size: 0.65rem !important;
        padding: 1px 8px !important;
    }
}
</style>
"""


# Small JS injected after a suggestion is clicked to fill + focus textarea
_FILL_JS = """
<script>
(function(){{
  var text = {text_json};
  var attempts = 0;
  function tryFill() {{
    if (window.parent && window.parent.__dpFillQuery) {{
      window.parent.__dpFillQuery(text);
    }} else if (attempts < 40) {{
      attempts++;
      setTimeout(tryFill, 50);
    }}
  }}
  tryFill();
}})();
</script>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────────────────────────────────────
def render_query_input() -> str | None:
    """Render the AI query input panel. Returns query string when submitted."""

    st.markdown(_CSS, unsafe_allow_html=True)

    cpu_svg = get_icon("cpu", size=18, color="white", stroke_width=2.0)
    st.markdown(f"""
    <div class='qin-header'>
        <div class='qin-icon'>{cpu_svg}</div>
        <div>
            <div class='qin-title'>Ask AI About Your Data</div>
            <div class='qin-sub'>AI-Powered Natural Language Analytics  &middot;  Context-Aware SQL Generation</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────── #
    _ss = st.session_state
    _ss.setdefault("current_query", "")
    _ss.setdefault("voice_corrections", [])
    _ss.setdefault("_focus_after_suggestion", False)

    schema_loaded = _ss.get("schema_loaded", False)
    tokens = _build_tokens() if schema_loaded else [
        {"d": kw, "t": "kw", "l": kw.lower()} for kw in _SQL_KEYWORDS
    ]

    # ── Textarea ──────────────────────────────────────────────────────── #
    query = st.text_area(
        "Ask anything",
        value=_ss["current_query"],
        key="query_input_widget",
        placeholder="Ask anything about your database…",
        height=95,
        label_visibility="collapsed",
    )

    # Voice correction banner
    corrections = _ss.get("voice_corrections", [])
    if corrections:
        items_html = "".join(
            f"<span style='margin-right:10px'>"
            f"<span class='voice-wrong'>{c['original']}</span>"
            f" → <span class='voice-right'>{c['corrected']}</span></span>"
            for c in corrections
        )
        st.markdown(
            f"<div class='voice-correction-banner'>"
            f"🎙️ <strong>Auto-corrected:</strong> {items_html}</div>",
            unsafe_allow_html=True,
        )
        if st.button("✕", key="dismiss_vc", help="Dismiss corrections"):
            _ss["voice_corrections"] = []
            st.rerun()

    # ── Action Buttons side-by-side ───────────────────────────────────── #
    st.markdown("<div class='action-row-anchor'></div>", unsafe_allow_html=True)
    btn_col1, btn_col2 = st.columns([3, 1])
    submitted = False
    
    is_generating = _ss.get("is_generating", False)

    # Animated generating button CSS — pulsing dots + shimmer
    if is_generating:
        st.markdown("""
        <style>
        .action-row-anchor + div.element-container div[data-testid="column"] [data-testid="stButton"] button[disabled] {
            background: linear-gradient(270deg, #3730a3, #4f46e5, #6366F1, #4f46e5, #3730a3) !important;
            background-size: 200% 100% !important;
            animation: gen-shimmer 2s ease infinite !important;
            opacity: 1 !important;
            color: #ffffff !important;
            border: none !important;
            cursor: wait !important;
            box-shadow: 0 4px 15px rgba(99,102,241,0.4) !important;
        }
        @keyframes gen-shimmer {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }
        </style>
        """, unsafe_allow_html=True)

    def on_generate_click():
        q = st.session_state.get("query_input_widget", "").strip()
        if q:
            # ── Bug 2 fix: clear ALL stale result state SYNCHRONOUSLY so the
            #    old table/chart never shows while a new query is generating. ──
            st.session_state["last_result"] = None
            st.session_state["is_generating"] = True
            # ── Bug 1 fix: persist active_query so the stream can be resumed
            #    if the user navigates away and comes back mid-generation. ──────
            st.session_state["active_query"] = q
            st.session_state["pending_query"] = q

    with btn_col1:
        if is_generating:
            # Cycle label for visual feedback
            dot_count = st.session_state.get("_gen_dots", 0)
            st.session_state["_gen_dots"] = (dot_count + 1) % 4
            btn_label = "⏳ Generating" + "." * st.session_state["_gen_dots"]
            st.button(
                btn_label,
                type="primary",
                use_container_width=True,
                key="generate_btn",
                disabled=True,
            )
            submitted = False
        else:
            submitted = st.button(
                "Run Analysis",
                type="primary",
                use_container_width=True,
                key="generate_btn",
                on_click=on_generate_click,
            )

    voice_state = _ss.get("voice_state", "idle")

    with btn_col2:
        from components.voice_input import render_voice_input
        from components.query_input import _voice_fuzzy_correct, _get_display_tokens
        vt = _get_display_tokens() if schema_loaded else {}
        if voice_state == "idle":
            render_voice_input(tokens=vt, voice_fuzzy_fn=_voice_fuzzy_correct)

    if voice_state == "listening":
        from components.voice_input import render_voice_input
        from components.query_input import _voice_fuzzy_correct, _get_display_tokens
        vt = _get_display_tokens() if schema_loaded else {}
        render_voice_input(tokens=vt, voice_fuzzy_fn=_voice_fuzzy_correct)

    # ── Quick Suggestions (Horizontal Strip below buttons) ────────────── #
    suggestions: List[str] = _ss.get("query_suggestions") or []
    if not suggestions and schema_loaded:
        suggestions = ["Show top 10 rows from the first table"]
    if not suggestions:
        suggestions = ["Connect a database to see suggestions"]

    st.markdown("<div class='sug-header'>Quick Suggestions</div>", unsafe_allow_html=True)
    
    max_sugs = 6
    sugs_to_show = suggestions[:max_sugs]
    
    # Chunk suggestions into groups of 3 (maximum of 2 rows)
    chunked_sugs = [sugs_to_show[i:i + 3] for i in range(0, len(sugs_to_show), 3)]
    
    for row_idx, row_sugs in enumerate(chunked_sugs):
        st.markdown(f"<div class='sug-row-anchor-{row_idx}'></div>", unsafe_allow_html=True)
        sug_cols = st.columns(3)
        for col_idx, sug in enumerate(row_sugs):
            with sug_cols[col_idx]:
                label = sug if len(sug) <= 60 else sug[:57] + "..."
                i = row_idx * 3 + col_idx
                if st.button(label, key=f"sug_chip_{i}_{sug[:16]}", use_container_width=True):
                    _ss["current_query"] = sug
                    _ss["_fill_text_after_suggestion"] = sug
                    st.rerun()

    # ── Inject JS IntelliSense engine (always, so it re-attaches on rerun) ── #
    focus = _ss.pop("_focus_after_suggestion", False)
    fill_text = _ss.pop("_fill_text_after_suggestion", None)
    
    _inject_intellisense(tokens, focus=focus)

    if fill_text is not None:
        components.html(
            _FILL_JS.replace("{text_json}", json.dumps(fill_text)),
            height=0,
            scrolling=False,
        )

    # ── Return ────────────────────────────────────────────────────────── #
    # Check if we have a pending query stored from before the rerun
    pending = _ss.pop("pending_query", None)
    if pending:
        _ss["current_query"] = pending
        return pending

    if submitted and query.strip():
        _ss["current_query"] = query.strip()
        return query.strip()

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Helpers re-used by voice_input.py
# ─────────────────────────────────────────────────────────────────────────────
import re
from typing import Tuple

_TYPE_COLUMN  = "col"
_TYPE_TABLE   = "tbl"
_TYPE_KEYWORD = "kw"
_TYPE_PHRASE  = "nl"


def _get_display_tokens() -> Dict[str, Tuple[str, str]]:
    """Return {lower: (display, type)} for voice correction."""
    schema_raw = st.session_state.get("schema_raw", {})
    tokens: Dict[str, Tuple[str, str]] = {}
    for table in schema_raw.get("tables", []):
        tname = table.get("name", "")
        if tname:
            tokens[tname.lower()] = (tname, _TYPE_TABLE)
        for col in table.get("columns", []):
            cname = col.get("name", "")
            if cname:
                tokens[cname.lower()] = (cname, _TYPE_COLUMN)
    for kw in _SQL_KEYWORDS:
        tokens[kw.lower()] = (kw, _TYPE_KEYWORD)
    return tokens


def _bigrams(s: str) -> set:
    return {s[i:i+2] for i in range(len(s) - 1)}


def _dice(a: str, b: str) -> float:
    if a == b: return 1.0
    ba, bb = _bigrams(a), _bigrams(b)
    if not ba or not bb: return 0.0
    return 2.0 * len(ba & bb) / (len(ba) + len(bb))


def _voice_fuzzy_correct(
    text: str, tokens: Dict[str, Tuple[str, str]]
) -> Tuple[str, List[Dict]]:
    """Correct voice-transcribed words against schema tokens."""
    if not text or not tokens:
        return text, []
    words = text.split()
    corrected, corrections = [], []
    for word in words:
        clean = re.sub(r"[^a-zA-Z0-9_]", "", word).lower()
        if len(clean) < 3 or clean in tokens:
            corrected.append(word)
            continue
        best_k, best_s = None, 0.0
        for k in tokens:
            s = _dice(clean, k)
            if s > best_s:
                best_s, best_k = s, k
        if best_k and best_s >= 0.72:
            display, _ = tokens[best_k]
            if display.lower() != clean:
                corrections.append({"original": word, "corrected": display})
                corrected.append(display)
                continue
        corrected.append(word)
    return " ".join(corrected), corrections
