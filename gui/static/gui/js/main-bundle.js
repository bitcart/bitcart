/*!
 * jQuery JavaScript Library v3.2.1
 * https://jquery.com/
 *
 * Includes Sizzle.js
 * https://sizzlejs.com/
 *
 * Copyright JS Foundation and other contributors
 * Released under the MIT license
 * https://jquery.org/license
 *
 * Date: 2017-03-20T18:59Z
 */
(function (n, t) {
  "use strict";
  typeof module == "object" && typeof module.exports == "object" ? module.exports = n.document ? t(n, !0) : function (n) {
    if (!n.document) throw new Error("jQuery requires a window with a document");
    return t(n)
  } : t(n)
})(typeof window != "undefined" ? window : this, function (n, t) {
  "use strict";

  function ir(n, t) {
    t = t || u;
    var i = t.createElement("script");
    i.text = n;
    t.head.appendChild(i).parentNode.removeChild(i)
  }

  function fi(n) {
    var t = !!n && "length" in n && n.length,
      r = i.type(n);
    return r === "function" || i.isWindow(n) ? !1 : r === "array" || t === 0 || typeof t == "number" && t > 0 && t - 1 in n
  }

  function l(n, t) {
    return n.nodeName && n.nodeName.toLowerCase() === t.toLowerCase()
  }

  function oi(n, t, r) {
    return i.isFunction(t) ? i.grep(n, function (n, i) {
      return !!t.call(n, i, n) !== r
    }) : t.nodeType ? i.grep(n, function (n) {
      return n === t !== r
    }) : typeof t != "string" ? i.grep(n, function (n) {
      return ot.call(t, n) > -1 !== r
    }) : er.test(t) ? i.filter(t, n, r) : (t = i.filter(t, n), i.grep(n, function (n) {
      return ot.call(t, n) > -1 !== r && n.nodeType === 1
    }))
  }

  function ar(n, t) {
    while ((n = n[t]) && n.nodeType !== 1);
    return n
  }

  function ne(n) {
    var t = {};
    return i.each(n.match(h) || [], function (n, i) {
      t[i] = !0
    }), t
  }

  function nt(n) {
    return n
  }

  function pt(n) {
    throw n;
  }

  function vr(n, t, r, u) {
    var f;
    try {
      n && i.isFunction(f = n.promise) ? f.call(n).done(t).fail(r) : n && i.isFunction(f = n.then) ? f.call(n, t, r) : t.apply(undefined, [n].slice(u))
    } catch (n) {
      r.apply(undefined, [n])
    }
  }

  function bt() {
    u.removeEventListener("DOMContentLoaded", bt);
    n.removeEventListener("load", bt);
    i.ready()
  }

  function ht() {
    this.expando = i.expando + ht.uid++
  }

  function re(n) {
    return n === "true" ? !0 : n === "false" ? !1 : n === "null" ? null : n === +n + "" ? +n : te.test(n) ? JSON.parse(n) : n
  }

  function pr(n, t, i) {
    var r;
    if (i === undefined && n.nodeType === 1)
      if (r = "data-" + t.replace(ie, "-$&").toLowerCase(), i = n.getAttribute(r), typeof i == "string") {
        try {
          i = re(i)
        } catch (u) {}
        e.set(n, t, i)
      } else i = undefined;
    return i
  }

  function kr(n, t, r, u) {
    var h, e = 1,
      l = 20,
      c = u ? function () {
        return u.cur()
      } : function () {
        return i.css(n, t, "")
      },
      s = c(),
      o = r && r[3] || (i.cssNumber[t] ? "" : "px"),
      f = (i.cssNumber[t] || o !== "px" && +s) && ct.exec(i.css(n, t));
    if (f && f[3] !== o) {
      o = o || f[3];
      r = r || [];
      f = +s || 1;
      do e = e || ".5", f = f / e, i.style(n, t, f + o); while (e !== (e = c() / s) && e !== 1 && --l)
    }
    return r && (f = +f || +s || 0, h = r[1] ? f + (r[1] + 1) * r[2] : +r[2], u && (u.unit = o, u.start = f, u.end = h)), h
  }

  function ue(n) {
    var r, f = n.ownerDocument,
      u = n.nodeName,
      t = si[u];
    return t ? t : (r = f.body.appendChild(f.createElement(u)), t = i.css(r, "display"), r.parentNode.removeChild(r), t === "none" && (t = "block"), si[u] = t, t)
  }

  function tt(n, t) {
    for (var e, u, f = [], i = 0, o = n.length; i < o; i++)(u = n[i], u.style) && (e = u.style.display, t ? (e === "none" && (f[i] = r.get(u, "display") || null, f[i] || (u.style.display = "")), u.style.display === "" && kt(u) && (f[i] = ue(u))) : e !== "none" && (f[i] = "none", r.set(u, "display", e)));
    for (i = 0; i < o; i++) f[i] != null && (n[i].style.display = f[i]);
    return n
  }

  function o(n, t) {
    var r;
    return (r = typeof n.getElementsByTagName != "undefined" ? n.getElementsByTagName(t || "*") : typeof n.querySelectorAll != "undefined" ? n.querySelectorAll(t || "*") : [], t === undefined || t && l(n, t)) ? i.merge([n], r) : r
  }

  function hi(n, t) {
    for (var i = 0, u = n.length; i < u; i++) r.set(n[i], "globalEval", !t || r.get(t[i], "globalEval"))
  }

  function iu(n, t, r, u, f) {
    for (var e, s, p, a, w, v, h = t.createDocumentFragment(), y = [], l = 0, b = n.length; l < b; l++)
      if (e = n[l], e || e === 0)
        if (i.type(e) === "object") i.merge(y, e.nodeType ? [e] : e);
        else if (tu.test(e)) {
      for (s = s || h.appendChild(t.createElement("div")), p = (gr.exec(e) || ["", ""])[1].toLowerCase(), a = c[p] || c._default, s.innerHTML = a[1] + i.htmlPrefilter(e) + a[2], v = a[0]; v--;) s = s.lastChild;
      i.merge(y, s.childNodes);
      s = h.firstChild;
      s.textContent = ""
    } else y.push(t.createTextNode(e));
    for (h.textContent = "", l = 0; e = y[l++];) {
      if (u && i.inArray(e, u) > -1) {
        f && f.push(e);
        continue
      }
      if (w = i.contains(e.ownerDocument, e), s = o(h.appendChild(e), "script"), w && hi(s), r)
        for (v = 0; e = s[v++];) nu.test(e.type || "") && r.push(e)
    }
    return h
  }

  function gt() {
    return !0
  }

  function it() {
    return !1
  }

  function uu() {
    try {
      return u.activeElement
    } catch (n) {}
  }

  function ci(n, t, r, u, f, e) {
    var o, s;
    if (typeof t == "object") {
      typeof r != "string" && (u = u || r, r = undefined);
      for (s in t) ci(n, s, r, u, t[s], e);
      return n
    }
    if (u == null && f == null ? (f = r, u = r = undefined) : f == null && (typeof r == "string" ? (f = u, u = undefined) : (f = u, u = r, r = undefined)), f === !1) f = it;
    else if (!f) return n;
    return e === 1 && (o = f, f = function (n) {
      return i().off(n), o.apply(this, arguments)
    }, f.guid = o.guid || (o.guid = i.guid++)), n.each(function () {
      i.event.add(this, t, f, u, r)
    })
  }

  function fu(n, t) {
    return l(n, "table") && l(t.nodeType !== 11 ? t : t.firstChild, "tr") ? i(">tbody", n)[0] || n : n
  }

  function ae(n) {
    return n.type = (n.getAttribute("type") !== null) + "/" + n.type, n
  }

  function ve(n) {
    var t = ce.exec(n.type);
    return t ? n.type = t[1] : n.removeAttribute("type"), n
  }

  function eu(n, t) {
    var f, c, o, s, h, l, a, u;
    if (t.nodeType === 1) {
      if (r.hasData(n) && (s = r.access(n), h = r.set(t, s), u = s.events, u)) {
        delete h.handle;
        h.events = {};
        for (o in u)
          for (f = 0, c = u[o].length; f < c; f++) i.event.add(t, o, u[o][f])
      }
      e.hasData(n) && (l = e.access(n), a = i.extend({}, l), e.set(t, a))
    }
  }

  function ye(n, t) {
    var i = t.nodeName.toLowerCase();
    i === "input" && dr.test(n.type) ? t.checked = n.checked : (i === "input" || i === "textarea") && (t.defaultValue = n.defaultValue)
  }

  function rt(n, t, u, e) {
    t = gi.apply([], t);
    var l, p, c, a, s, w, h = 0,
      v = n.length,
      k = v - 1,
      y = t[0],
      b = i.isFunction(y);
    if (b || v > 1 && typeof y == "string" && !f.checkClone && he.test(y)) return n.each(function (i) {
      var r = n.eq(i);
      b && (t[0] = y.call(this, i, r.html()));
      rt(r, t, u, e)
    });
    if (v && (l = iu(t, n[0].ownerDocument, !1, n, e), p = l.firstChild, l.childNodes.length === 1 && (l = p), p || e)) {
      for (c = i.map(o(l, "script"), ae), a = c.length; h < v; h++) s = l, h !== k && (s = i.clone(s, !0, !0), a && i.merge(c, o(s, "script"))), u.call(n[h], s, h);
      if (a)
        for (w = c[c.length - 1].ownerDocument, i.map(c, ve), h = 0; h < a; h++) s = c[h], nu.test(s.type || "") && !r.access(s, "globalEval") && i.contains(w, s) && (s.src ? i._evalUrl && i._evalUrl(s.src) : ir(s.textContent.replace(le, ""), w))
    }
    return n
  }

  function ou(n, t, r) {
    for (var u, e = t ? i.filter(t, n) : n, f = 0;
      (u = e[f]) != null; f++) r || u.nodeType !== 1 || i.cleanData(o(u)), u.parentNode && (r && i.contains(u.ownerDocument, u) && hi(o(u, "script")), u.parentNode.removeChild(u));
    return n
  }

  function lt(n, t, r) {
    var o, s, h, u, e = n.style;
    return r = r || ni(n), r && (u = r.getPropertyValue(t) || r[t], u !== "" || i.contains(n.ownerDocument, n) || (u = i.style(n, t)), !f.pixelMarginRight() && li.test(u) && su.test(t) && (o = e.width, s = e.minWidth, h = e.maxWidth, e.minWidth = e.maxWidth = e.width = u, u = r.width, e.width = o, e.minWidth = s, e.maxWidth = h)), u !== undefined ? u + "" : u
  }

  function hu(n, t) {
    return {
      get: function () {
        if (n()) {
          delete this.get;
          return
        }
        return (this.get = t).apply(this, arguments)
      }
    }
  }

  function be(n) {
    if (n in vu) return n;
    for (var i = n[0].toUpperCase() + n.slice(1), t = au.length; t--;)
      if (n = au[t] + i, n in vu) return n
  }

  function yu(n) {
    var t = i.cssProps[n];
    return t || (t = i.cssProps[n] = be(n) || n), t
  }

  function pu(n, t, i) {
    var r = ct.exec(t);
    return r ? Math.max(0, r[2] - (i || 0)) + (r[3] || "px") : t
  }

  function wu(n, t, r, u, f) {
    for (var o = 0, e = r === (u ? "border" : "content") ? 4 : t === "width" ? 1 : 0; e < 4; e += 2) r === "margin" && (o += i.css(n, r + b[e], !0, f)), u ? (r === "content" && (o -= i.css(n, "padding" + b[e], !0, f)), r !== "margin" && (o -= i.css(n, "border" + b[e] + "Width", !0, f))) : (o += i.css(n, "padding" + b[e], !0, f), r !== "padding" && (o += i.css(n, "border" + b[e] + "Width", !0, f)));
    return o
  }

  function bu(n, t, r) {
    var o, e = ni(n),
      u = lt(n, t, e),
      s = i.css(n, "boxSizing", !1, e) === "border-box";
    return li.test(u) ? u : (o = s && (f.boxSizingReliable() || u === n.style[t]), u === "auto" && (u = n["offset" + t[0].toUpperCase() + t.slice(1)]), u = parseFloat(u) || 0, u + wu(n, t, r || (s ? "border" : "content"), o, e) + "px")
  }

  function s(n, t, i, r, u) {
    return new s.prototype.init(n, t, i, r, u)
  }

  function ai() {
    ti && (u.hidden === !1 && n.requestAnimationFrame ? n.requestAnimationFrame(ai) : n.setTimeout(ai, i.fx.interval), i.fx.tick())
  }

  function gu() {
    return n.setTimeout(function () {
      ut = undefined
    }), ut = i.now()
  }

  function ii(n, t) {
    var r, u = 0,
      i = {
        height: n
      };
    for (t = t ? 1 : 0; u < 4; u += 2 - t) r = b[u], i["margin" + r] = i["padding" + r] = n;
    return t && (i.opacity = i.width = n), i
  }

  function nf(n, t, i) {
    for (var u, f = (a.tweeners[t] || []).concat(a.tweeners["*"]), r = 0, e = f.length; r < e; r++)
      if (u = f[r].call(i, t, n)) return u
  }

  function ke(n, t, u) {
    var f, y, w, c, b, s, o, l, k = "width" in t || "height" in t,
      v = this,
      p = {},
      h = n.style,
      a = n.nodeType && kt(n),
      e = r.get(n, "fxshow");
    u.queue || (c = i._queueHooks(n, "fx"), c.unqueued == null && (c.unqueued = 0, b = c.empty.fire, c.empty.fire = function () {
      c.unqueued || b()
    }), c.unqueued++, v.always(function () {
      v.always(function () {
        c.unqueued--;
        i.queue(n, "fx").length || c.empty.fire()
      })
    }));
    for (f in t)
      if (y = t[f], ku.test(y)) {
        if (delete t[f], w = w || y === "toggle", y === (a ? "hide" : "show"))
          if (y === "show" && e && e[f] !== undefined) a = !0;
          else continue;
        p[f] = e && e[f] || i.style(n, f)
      } if (s = !i.isEmptyObject(t), s || !i.isEmptyObject(p)) {
      k && n.nodeType === 1 && (u.overflow = [h.overflow, h.overflowX, h.overflowY], o = e && e.display, o == null && (o = r.get(n, "display")), l = i.css(n, "display"), l === "none" && (o ? l = o : (tt([n], !0), o = n.style.display || o, l = i.css(n, "display"), tt([n]))), (l === "inline" || l === "inline-block" && o != null) && i.css(n, "float") === "none" && (s || (v.done(function () {
        h.display = o
      }), o == null && (l = h.display, o = l === "none" ? "" : l)), h.display = "inline-block"));
      u.overflow && (h.overflow = "hidden", v.always(function () {
        h.overflow = u.overflow[0];
        h.overflowX = u.overflow[1];
        h.overflowY = u.overflow[2]
      }));
      s = !1;
      for (f in p) s || (e ? "hidden" in e && (a = e.hidden) : e = r.access(n, "fxshow", {
        display: o
      }), w && (e.hidden = !a), a && tt([n], !0), v.done(function () {
        a || tt([n]);
        r.remove(n, "fxshow");
        for (f in p) i.style(n, f, p[f])
      })), s = nf(a ? e[f] : 0, f, v), f in e || (e[f] = s.start, a && (s.end = s.start, s.start = 0))
    }
  }

  function de(n, t) {
    var r, f, e, u, o;
    for (r in n)
      if (f = i.camelCase(r), e = t[f], u = n[r], Array.isArray(u) && (e = u[1], u = n[r] = u[0]), r !== f && (n[f] = u, delete n[r]), o = i.cssHooks[f], o && "expand" in o) {
        u = o.expand(u);
        delete n[f];
        for (r in u) r in n || (n[r] = u[r], t[r] = e)
      } else t[f] = e
  }

  function a(n, t, r) {
    var e, o, s = 0,
      l = a.prefilters.length,
      f = i.Deferred().always(function () {
        delete c.elem
      }),
      c = function () {
        if (o) return !1;
        for (var s = ut || gu(), t = Math.max(0, u.startTime + u.duration - s), h = t / u.duration || 0, i = 1 - h, r = 0, e = u.tweens.length; r < e; r++) u.tweens[r].run(i);
        return (f.notifyWith(n, [u, i, t]), i < 1 && e) ? t : (e || f.notifyWith(n, [u, 1, 0]), f.resolveWith(n, [u]), !1)
      },
      u = f.promise({
        elem: n,
        props: i.extend({}, t),
        opts: i.extend(!0, {
          specialEasing: {},
          easing: i.easing._default
        }, r),
        originalProperties: t,
        originalOptions: r,
        startTime: ut || gu(),
        duration: r.duration,
        tweens: [],
        createTween: function (t, r) {
          var f = i.Tween(n, u.opts, t, r, u.opts.specialEasing[t] || u.opts.easing);
          return u.tweens.push(f), f
        },
        stop: function (t) {
          var i = 0,
            r = t ? u.tweens.length : 0;
          if (o) return this;
          for (o = !0; i < r; i++) u.tweens[i].run(1);
          return t ? (f.notifyWith(n, [u, 1, 0]), f.resolveWith(n, [u, t])) : f.rejectWith(n, [u, t]), this
        }
      }),
      h = u.props;
    for (de(h, u.opts.specialEasing); s < l; s++)
      if (e = a.prefilters[s].call(u, n, h, u.opts), e) return i.isFunction(e.stop) && (i._queueHooks(u.elem, u.opts.queue).stop = i.proxy(e.stop, e)), e;
    return i.map(h, nf, u), i.isFunction(u.opts.start) && u.opts.start.call(n, u), u.progress(u.opts.progress).done(u.opts.done, u.opts.complete).fail(u.opts.fail).always(u.opts.always), i.fx.timer(i.extend(c, {
      elem: n,
      anim: u,
      queue: u.opts.queue
    })), u
  }

  function k(n) {
    var t = n.match(h) || [];
    return t.join(" ")
  }

  function d(n) {
    return n.getAttribute && n.getAttribute("class") || ""
  }

  function pi(n, t, r, u) {
    var f;
    if (Array.isArray(t)) i.each(t, function (t, i) {
      r || ge.test(n) ? u(n, i) : pi(n + "[" + (typeof i == "object" && i != null ? t : "") + "]", i, r, u)
    });
    else if (r || i.type(t) !== "object") u(n, t);
    else
      for (f in t) pi(n + "[" + f + "]", t[f], r, u)
  }

  function cf(n) {
    return function (t, r) {
      typeof t != "string" && (r = t, t = "*");
      var u, f = 0,
        e = t.toLowerCase().match(h) || [];
      if (i.isFunction(r))
        while (u = e[f++]) u[0] === "+" ? (u = u.slice(1) || "*", (n[u] = n[u] || []).unshift(r)) : (n[u] = n[u] || []).push(r)
    }
  }

  function lf(n, t, r, u) {
    function e(s) {
      var h;
      return f[s] = !0, i.each(n[s] || [], function (n, i) {
        var s = i(t, r, u);
        if (typeof s != "string" || o || f[s]) {
          if (o) return !(h = s)
        } else return t.dataTypes.unshift(s), e(s), !1
      }), h
    }
    var f = {},
      o = n === wi;
    return e(t.dataTypes[0]) || !f["*"] && e("*")
  }

  function ki(n, t) {
    var r, u, f = i.ajaxSettings.flatOptions || {};
    for (r in t) t[r] !== undefined && ((f[r] ? n : u || (u = {}))[r] = t[r]);
    return u && i.extend(!0, n, u), n
  }

  function so(n, t, i) {
    for (var e, u, f, o, s = n.contents, r = n.dataTypes; r[0] === "*";) r.shift(), e === undefined && (e = n.mimeType || t.getResponseHeader("Content-Type"));
    if (e)
      for (u in s)
        if (s[u] && s[u].test(e)) {
          r.unshift(u);
          break
        } if (r[0] in i) f = r[0];
    else {
      for (u in i) {
        if (!r[0] || n.converters[u + " " + r[0]]) {
          f = u;
          break
        }
        o || (o = u)
      }
      f = f || o
    }
    if (f) return f !== r[0] && r.unshift(f), i[f]
  }

  function ho(n, t, i, r) {
    var h, u, f, s, e, o = {},
      c = n.dataTypes.slice();
    if (c[1])
      for (f in n.converters) o[f.toLowerCase()] = n.converters[f];
    for (u = c.shift(); u;)
      if (n.responseFields[u] && (i[n.responseFields[u]] = t), !e && r && n.dataFilter && (t = n.dataFilter(t, n.dataType)), e = u, u = c.shift(), u)
        if (u === "*") u = e;
        else if (e !== "*" && e !== u) {
      if (f = o[e + " " + u] || o["* " + u], !f)
        for (h in o)
          if (s = h.split(" "), s[1] === u && (f = o[e + " " + s[0]] || o["* " + s[0]], f)) {
            f === !0 ? f = o[h] : o[h] !== !0 && (u = s[0], c.unshift(s[1]));
            break
          } if (f !== !0)
        if (f && n.throws) t = f(t);
        else try {
          t = f(t)
        } catch (l) {
          return {
            state: "parsererror",
            error: f ? l : "No conversion from " + e + " to " + u
          }
        }
    }
    return {
      state: "success",
      data: t
    }
  }
  var p = [],
    u = n.document,
    pf = Object.getPrototypeOf,
    w = p.slice,
    gi = p.concat,
    ui = p.push,
    ot = p.indexOf,
    vt = {},
    nr = vt.toString,
    yt = vt.hasOwnProperty,
    tr = yt.toString,
    wf = tr.call(Object),
    f = {},
    rr = "3.2.1",
    i = function (n, t) {
      return new i.fn.init(n, t)
    },
    bf = /^[\s\uFEFF\xA0]+|[\s\uFEFF\xA0]+$/g,
    kf = /^-ms-/,
    df = /-([a-z])/g,
    gf = function (n, t) {
      return t.toUpperCase()
    },
    y, ei, er, or, sr, hr, cr, lr, h, yr, wt, v, st, si, tu, ut, ti, ku, du, tf, ft, rf, uf, ff, vi, af, et, di, ri, vf, yf;
  i.fn = i.prototype = {
    jquery: rr,
    constructor: i,
    length: 0,
    toArray: function () {
      return w.call(this)
    },
    get: function (n) {
      return n == null ? w.call(this) : n < 0 ? this[n + this.length] : this[n]
    },
    pushStack: function (n) {
      var t = i.merge(this.constructor(), n);
      return t.prevObject = this, t
    },
    each: function (n) {
      return i.each(this, n)
    },
    map: function (n) {
      return this.pushStack(i.map(this, function (t, i) {
        return n.call(t, i, t)
      }))
    },
    slice: function () {
      return this.pushStack(w.apply(this, arguments))
    },
    first: function () {
      return this.eq(0)
    },
    last: function () {
      return this.eq(-1)
    },
    eq: function (n) {
      var i = this.length,
        t = +n + (n < 0 ? i : 0);
      return this.pushStack(t >= 0 && t < i ? [this[t]] : [])
    },
    end: function () {
      return this.prevObject || this.constructor()
    },
    push: ui,
    sort: p.sort,
    splice: p.splice
  };
  i.extend = i.fn.extend = function () {
    var e, f, r, t, o, s, n = arguments[0] || {},
      u = 1,
      c = arguments.length,
      h = !1;
    for (typeof n == "boolean" && (h = n, n = arguments[u] || {}, u++), typeof n == "object" || i.isFunction(n) || (n = {}), u === c && (n = this, u--); u < c; u++)
      if ((e = arguments[u]) != null)
        for (f in e)(r = n[f], t = e[f], n !== t) && (h && t && (i.isPlainObject(t) || (o = Array.isArray(t))) ? (o ? (o = !1, s = r && Array.isArray(r) ? r : []) : s = r && i.isPlainObject(r) ? r : {}, n[f] = i.extend(h, s, t)) : t !== undefined && (n[f] = t));
    return n
  };
  i.extend({
    expando: "jQuery" + (rr + Math.random()).replace(/\D/g, ""),
    isReady: !0,
    error: function (n) {
      throw new Error(n);
    },
    noop: function () {},
    isFunction: function (n) {
      return i.type(n) === "function"
    },
    isWindow: function (n) {
      return n != null && n === n.window
    },
    isNumeric: function (n) {
      var t = i.type(n);
      return (t === "number" || t === "string") && !isNaN(n - parseFloat(n))
    },
    isPlainObject: function (n) {
      var t, i;
      return !n || nr.call(n) !== "[object Object]" ? !1 : (t = pf(n), !t) ? !0 : (i = yt.call(t, "constructor") && t.constructor, typeof i == "function" && tr.call(i) === wf)
    },
    isEmptyObject: function (n) {
      for (var t in n) return !1;
      return !0
    },
    type: function (n) {
      return n == null ? n + "" : typeof n == "object" || typeof n == "function" ? vt[nr.call(n)] || "object" : typeof n
    },
    globalEval: function (n) {
      ir(n)
    },
    camelCase: function (n) {
      return n.replace(kf, "ms-").replace(df, gf)
    },
    each: function (n, t) {
      var r, i = 0;
      if (fi(n)) {
        for (r = n.length; i < r; i++)
          if (t.call(n[i], i, n[i]) === !1) break
      } else
        for (i in n)
          if (t.call(n[i], i, n[i]) === !1) break;
      return n
    },
    trim: function (n) {
      return n == null ? "" : (n + "").replace(bf, "")
    },
    makeArray: function (n, t) {
      var r = t || [];
      return n != null && (fi(Object(n)) ? i.merge(r, typeof n == "string" ? [n] : n) : ui.call(r, n)), r
    },
    inArray: function (n, t, i) {
      return t == null ? -1 : ot.call(t, n, i)
    },
    merge: function (n, t) {
      for (var u = +t.length, i = 0, r = n.length; i < u; i++) n[r++] = t[i];
      return n.length = r, n
    },
    grep: function (n, t, i) {
      for (var u, f = [], r = 0, e = n.length, o = !i; r < e; r++) u = !t(n[r], r), u !== o && f.push(n[r]);
      return f
    },
    map: function (n, t, i) {
      var e, u, r = 0,
        f = [];
      if (fi(n))
        for (e = n.length; r < e; r++) u = t(n[r], r, i), u != null && f.push(u);
      else
        for (r in n) u = t(n[r], r, i), u != null && f.push(u);
      return gi.apply([], f)
    },
    guid: 1,
    proxy: function (n, t) {
      var u, f, r;
      return (typeof t == "string" && (u = n[t], t = n, n = u), !i.isFunction(n)) ? undefined : (f = w.call(arguments, 2), r = function () {
        return n.apply(t || this, f.concat(w.call(arguments)))
      }, r.guid = n.guid = n.guid || i.guid++, r)
    },
    now: Date.now,
    support: f
  });
  typeof Symbol == "function" && (i.fn[Symbol.iterator] = p[Symbol.iterator]);
  i.each("Boolean Number String Function Array Date RegExp Object Error Symbol".split(" "), function (n, t) {
    vt["[object " + t + "]"] = t.toLowerCase()
  });
  y = function (n) {
    function u(n, t, r, u) {
      var s, w, l, a, d, y, g, p = t && t.ownerDocument,
        v = t ? t.nodeType : 9;
      if (r = r || [], typeof n != "string" || !n || v !== 1 && v !== 9 && v !== 11) return r;
      if (!u && ((t ? t.ownerDocument || t : c) !== i && b(t), t = t || i, h)) {
        if (v !== 11 && (d = cr.exec(n)))
          if (s = d[1]) {
            if (v === 9)
              if (l = t.getElementById(s)) {
                if (l.id === s) return r.push(l), r
              } else return r;
            else if (p && (l = p.getElementById(s)) && et(t, l) && l.id === s) return r.push(l), r
          } else {
            if (d[2]) return k.apply(r, t.getElementsByTagName(n)), r;
            if ((s = d[3]) && e.getElementsByClassName && t.getElementsByClassName) return k.apply(r, t.getElementsByClassName(s)), r
          } if (e.qsa && !lt[n + " "] && (!o || !o.test(n))) {
          if (v !== 1) p = t, g = n;
          else if (t.nodeName.toLowerCase() !== "object") {
            for ((a = t.getAttribute("id")) ? a = a.replace(vi, yi) : t.setAttribute("id", a = f), y = ft(n), w = y.length; w--;) y[w] = "#" + a + " " + yt(y[w]);
            g = y.join(",");
            p = ni.test(n) && ri(t.parentNode) || t
          }
          if (g) try {
            return k.apply(r, p.querySelectorAll(g)), r
          } catch (nt) {} finally {
            a === f && t.removeAttribute("id")
          }
        }
      }
      return si(n.replace(at, "$1"), t, r, u)
    }

    function ti() {
      function n(r, u) {
        return i.push(r + " ") > t.cacheLength && delete n[i.shift()], n[r + " "] = u
      }
      var i = [];
      return n
    }

    function l(n) {
      return n[f] = !0, n
    }

    function a(n) {
      var t = i.createElement("fieldset");
      try {
        return !!n(t)
      } catch (r) {
        return !1
      } finally {
        t.parentNode && t.parentNode.removeChild(t);
        t = null
      }
    }

    function ii(n, i) {
      for (var r = n.split("|"), u = r.length; u--;) t.attrHandle[r[u]] = i
    }

    function wi(n, t) {
      var i = t && n,
        r = i && n.nodeType === 1 && t.nodeType === 1 && n.sourceIndex - t.sourceIndex;
      if (r) return r;
      if (i)
        while (i = i.nextSibling)
          if (i === t) return -1;
      return n ? 1 : -1
    }

    function ar(n) {
      return function (t) {
        var i = t.nodeName.toLowerCase();
        return i === "input" && t.type === n
      }
    }

    function vr(n) {
      return function (t) {
        var i = t.nodeName.toLowerCase();
        return (i === "input" || i === "button") && t.type === n
      }
    }

    function bi(n) {
      return function (t) {
        return "form" in t ? t.parentNode && t.disabled === !1 ? "label" in t ? "label" in t.parentNode ? t.parentNode.disabled === n : t.disabled === n : t.isDisabled === n || t.isDisabled !== !n && lr(t) === n : t.disabled === n : "label" in t ? t.disabled === n : !1
      }
    }

    function it(n) {
      return l(function (t) {
        return t = +t, l(function (i, r) {
          for (var u, f = n([], i.length, t), e = f.length; e--;) i[u = f[e]] && (i[u] = !(r[u] = i[u]))
        })
      })
    }

    function ri(n) {
      return n && typeof n.getElementsByTagName != "undefined" && n
    }

    function ki() {}

    function yt(n) {
      for (var t = 0, r = n.length, i = ""; t < r; t++) i += n[t].value;
      return i
    }

    function pt(n, t, i) {
      var r = t.dir,
        u = t.next,
        e = u || r,
        o = i && e === "parentNode",
        s = di++;
      return t.first ? function (t, i, u) {
        while (t = t[r])
          if (t.nodeType === 1 || o) return n(t, i, u);
        return !1
      } : function (t, i, h) {
        var c, l, a, y = [v, s];
        if (h) {
          while (t = t[r])
            if ((t.nodeType === 1 || o) && n(t, i, h)) return !0
        } else
          while (t = t[r])
            if (t.nodeType === 1 || o)
              if (a = t[f] || (t[f] = {}), l = a[t.uniqueID] || (a[t.uniqueID] = {}), u && u === t.nodeName.toLowerCase()) t = t[r] || t;
              else {
                if ((c = l[e]) && c[0] === v && c[1] === s) return y[2] = c[2];
                if (l[e] = y, y[2] = n(t, i, h)) return !0
              } return !1
      }
    }

    function ui(n) {
      return n.length > 1 ? function (t, i, r) {
        for (var u = n.length; u--;)
          if (!n[u](t, i, r)) return !1;
        return !0
      } : n[0]
    }

    function yr(n, t, i) {
      for (var r = 0, f = t.length; r < f; r++) u(n, t[r], i);
      return i
    }

    function wt(n, t, i, r, u) {
      for (var e, o = [], f = 0, s = n.length, h = t != null; f < s; f++)(e = n[f]) && (!i || i(e, r, u)) && (o.push(e), h && t.push(f));
      return o
    }

    function fi(n, t, i, r, u, e) {
      return r && !r[f] && (r = fi(r)), u && !u[f] && (u = fi(u, e)), l(function (f, e, o, s) {
        var l, c, a, p = [],
          y = [],
          w = e.length,
          b = f || yr(t || "*", o.nodeType ? [o] : o, []),
          v = n && (f || !t) ? wt(b, p, n, o, s) : b,
          h = i ? u || (f ? n : w || r) ? [] : e : v;
        if (i && i(v, h, o, s), r)
          for (l = wt(h, y), r(l, [], o, s), c = l.length; c--;)(a = l[c]) && (h[y[c]] = !(v[y[c]] = a));
        if (f) {
          if (u || n) {
            if (u) {
              for (l = [], c = h.length; c--;)(a = h[c]) && l.push(v[c] = a);
              u(null, h = [], l, s)
            }
            for (c = h.length; c--;)(a = h[c]) && (l = u ? nt(f, a) : p[c]) > -1 && (f[l] = !(e[l] = a))
          }
        } else h = wt(h === e ? h.splice(w, h.length) : h), u ? u(null, e, h, s) : k.apply(e, h)
      })
    }

    function ei(n) {
      for (var o, u, r, s = n.length, h = t.relative[n[0].type], c = h || t.relative[" "], i = h ? 1 : 0, l = pt(function (n) {
          return n === o
        }, c, !0), a = pt(function (n) {
          return nt(o, n) > -1
        }, c, !0), e = [function (n, t, i) {
          var r = !h && (i || t !== ht) || ((o = t).nodeType ? l(n, t, i) : a(n, t, i));
          return o = null, r
        }]; i < s; i++)
        if (u = t.relative[n[i].type]) e = [pt(ui(e), u)];
        else {
          if (u = t.filter[n[i].type].apply(null, n[i].matches), u[f]) {
            for (r = ++i; r < s; r++)
              if (t.relative[n[r].type]) break;
            return fi(i > 1 && ui(e), i > 1 && yt(n.slice(0, i - 1).concat({
              value: n[i - 2].type === " " ? "*" : ""
            })).replace(at, "$1"), u, i < r && ei(n.slice(i, r)), r < s && ei(n = n.slice(r)), r < s && yt(n))
          }
          e.push(u)
        } return ui(e)
    }

    function pr(n, r) {
      var f = r.length > 0,
        e = n.length > 0,
        o = function (o, s, c, l, a) {
          var y, nt, d, g = 0,
            p = "0",
            tt = o && [],
            w = [],
            it = ht,
            rt = o || e && t.find.TAG("*", a),
            ut = v += it == null ? 1 : Math.random() || .1,
            ft = rt.length;
          for (a && (ht = s === i || s || a); p !== ft && (y = rt[p]) != null; p++) {
            if (e && y) {
              for (nt = 0, s || y.ownerDocument === i || (b(y), c = !h); d = n[nt++];)
                if (d(y, s || i, c)) {
                  l.push(y);
                  break
                } a && (v = ut)
            }
            f && ((y = !d && y) && g--, o && tt.push(y))
          }
          if (g += p, f && p !== g) {
            for (nt = 0; d = r[nt++];) d(tt, w, s, c);
            if (o) {
              if (g > 0)
                while (p--) tt[p] || w[p] || (w[p] = nr.call(l));
              w = wt(w)
            }
            k.apply(l, w);
            a && !o && w.length > 0 && g + r.length > 1 && u.uniqueSort(l)
          }
          return a && (v = ut, ht = it), tt
        };
      return f ? l(o) : o
    }
    var rt, e, t, st, oi, ft, bt, si, ht, w, ut, b, i, s, h, o, d, ct, et, f = "sizzle" + 1 * new Date,
      c = n.document,
      v = 0,
      di = 0,
      hi = ti(),
      ci = ti(),
      lt = ti(),
      kt = function (n, t) {
        return n === t && (ut = !0), 0
      },
      gi = {}.hasOwnProperty,
      g = [],
      nr = g.pop,
      tr = g.push,
      k = g.push,
      li = g.slice,
      nt = function (n, t) {
        for (var i = 0, r = n.length; i < r; i++)
          if (n[i] === t) return i;
        return -1
      },
      dt = "checked|selected|async|autofocus|autoplay|controls|defer|disabled|hidden|ismap|loop|multiple|open|readonly|required|scoped",
      r = "[\\x20\\t\\r\\n\\f]",
      tt = "(?:\\\\.|[\\w-]|[^\0-\\xa0])+",
      ai = "\\[" + r + "*(" + tt + ")(?:" + r + "*([*^$|!~]?=)" + r + "*(?:'((?:\\\\.|[^\\\\'])*)'|\"((?:\\\\.|[^\\\\\"])*)\"|(" + tt + "))|)" + r + "*\\]",
      gt = ":(" + tt + ")(?:\\((('((?:\\\\.|[^\\\\'])*)'|\"((?:\\\\.|[^\\\\\"])*)\")|((?:\\\\.|[^\\\\()[\\]]|" + ai + ")*)|.*)\\)|)",
      ir = new RegExp(r + "+", "g"),
      at = new RegExp("^" + r + "+|((?:^|[^\\\\])(?:\\\\.)*)" + r + "+$", "g"),
      rr = new RegExp("^" + r + "*," + r + "*"),
      ur = new RegExp("^" + r + "*([>+~]|" + r + ")" + r + "*"),
      fr = new RegExp("=" + r + "*([^\\]'\"]*?)" + r + "*\\]", "g"),
      er = new RegExp(gt),
      or = new RegExp("^" + tt + "$"),
      vt = {
        ID: new RegExp("^#(" + tt + ")"),
        CLASS: new RegExp("^\\.(" + tt + ")"),
        TAG: new RegExp("^(" + tt + "|[*])"),
        ATTR: new RegExp("^" + ai),
        PSEUDO: new RegExp("^" + gt),
        CHILD: new RegExp("^:(only|first|last|nth|nth-last)-(child|of-type)(?:\\(" + r + "*(even|odd|(([+-]|)(\\d*)n|)" + r + "*(?:([+-]|)" + r + "*(\\d+)|))" + r + "*\\)|)", "i"),
        bool: new RegExp("^(?:" + dt + ")$", "i"),
        needsContext: new RegExp("^" + r + "*[>+~]|:(even|odd|eq|gt|lt|nth|first|last)(?:\\(" + r + "*((?:-\\d)?\\d*)" + r + "*\\)|)(?=[^-]|$)", "i")
      },
      sr = /^(?:input|select|textarea|button)$/i,
      hr = /^h\d$/i,
      ot = /^[^{]+\{\s*\[native \w/,
      cr = /^(?:#([\w-]+)|(\w+)|\.([\w-]+))$/,
      ni = /[+~]/,
      y = new RegExp("\\\\([\\da-f]{1,6}" + r + "?|(" + r + ")|.)", "ig"),
      p = function (n, t, i) {
        var r = "0x" + t - 65536;
        return r !== r || i ? t : r < 0 ? String.fromCharCode(r + 65536) : String.fromCharCode(r >> 10 | 55296, r & 1023 | 56320)
      },
      vi = /([\0-\x1f\x7f]|^-?\d)|^-$|[^\0-\x1f\x7f-\uFFFF\w-]/g,
      yi = function (n, t) {
        return t ? n === "\0" ? "�" : n.slice(0, -1) + "\\" + n.charCodeAt(n.length - 1).toString(16) + " " : "\\" + n
      },
      pi = function () {
        b()
      },
      lr = pt(function (n) {
        return n.disabled === !0 && ("form" in n || "label" in n)
      }, {
        dir: "parentNode",
        next: "legend"
      });
    try {
      k.apply(g = li.call(c.childNodes), c.childNodes);
      g[c.childNodes.length].nodeType
    } catch (wr) {
      k = {
        apply: g.length ? function (n, t) {
          tr.apply(n, li.call(t))
        } : function (n, t) {
          for (var i = n.length, r = 0; n[i++] = t[r++];);
          n.length = i - 1
        }
      }
    }
    e = u.support = {};
    oi = u.isXML = function (n) {
      var t = n && (n.ownerDocument || n).documentElement;
      return t ? t.nodeName !== "HTML" : !1
    };
    b = u.setDocument = function (n) {
      var v, u, l = n ? n.ownerDocument || n : c;
      return l === i || l.nodeType !== 9 || !l.documentElement ? i : (i = l, s = i.documentElement, h = !oi(i), c !== i && (u = i.defaultView) && u.top !== u && (u.addEventListener ? u.addEventListener("unload", pi, !1) : u.attachEvent && u.attachEvent("onunload", pi)), e.attributes = a(function (n) {
        return n.className = "i", !n.getAttribute("className")
      }), e.getElementsByTagName = a(function (n) {
        return n.appendChild(i.createComment("")), !n.getElementsByTagName("*").length
      }), e.getElementsByClassName = ot.test(i.getElementsByClassName), e.getById = a(function (n) {
        return s.appendChild(n).id = f, !i.getElementsByName || !i.getElementsByName(f).length
      }), e.getById ? (t.filter.ID = function (n) {
        var t = n.replace(y, p);
        return function (n) {
          return n.getAttribute("id") === t
        }
      }, t.find.ID = function (n, t) {
        if (typeof t.getElementById != "undefined" && h) {
          var i = t.getElementById(n);
          return i ? [i] : []
        }
      }) : (t.filter.ID = function (n) {
        var t = n.replace(y, p);
        return function (n) {
          var i = typeof n.getAttributeNode != "undefined" && n.getAttributeNode("id");
          return i && i.value === t
        }
      }, t.find.ID = function (n, t) {
        if (typeof t.getElementById != "undefined" && h) {
          var i, u, f, r = t.getElementById(n);
          if (r) {
            if (i = r.getAttributeNode("id"), i && i.value === n) return [r];
            for (f = t.getElementsByName(n), u = 0; r = f[u++];)
              if (i = r.getAttributeNode("id"), i && i.value === n) return [r]
          }
          return []
        }
      }), t.find.TAG = e.getElementsByTagName ? function (n, t) {
        return typeof t.getElementsByTagName != "undefined" ? t.getElementsByTagName(n) : e.qsa ? t.querySelectorAll(n) : void 0
      } : function (n, t) {
        var i, r = [],
          f = 0,
          u = t.getElementsByTagName(n);
        if (n === "*") {
          while (i = u[f++]) i.nodeType === 1 && r.push(i);
          return r
        }
        return u
      }, t.find.CLASS = e.getElementsByClassName && function (n, t) {
        if (typeof t.getElementsByClassName != "undefined" && h) return t.getElementsByClassName(n)
      }, d = [], o = [], (e.qsa = ot.test(i.querySelectorAll)) && (a(function (n) {
        s.appendChild(n).innerHTML = "<a id='" + f + "'><\/a><select id='" + f + "-\r\\' msallowcapture=''><option selected=''><\/option><\/select>";
        n.querySelectorAll("[msallowcapture^='']").length && o.push("[*^$]=" + r + "*(?:''|\"\")");
        n.querySelectorAll("[selected]").length || o.push("\\[" + r + "*(?:value|" + dt + ")");
        n.querySelectorAll("[id~=" + f + "-]").length || o.push("~=");
        n.querySelectorAll(":checked").length || o.push(":checked");
        n.querySelectorAll("a#" + f + "+*").length || o.push(".#.+[+~]")
      }), a(function (n) {
        n.innerHTML = "<a href='' disabled='disabled'><\/a><select disabled='disabled'><option/><\/select>";
        var t = i.createElement("input");
        t.setAttribute("type", "hidden");
        n.appendChild(t).setAttribute("name", "D");
        n.querySelectorAll("[name=d]").length && o.push("name" + r + "*[*^$|!~]?=");
        n.querySelectorAll(":enabled").length !== 2 && o.push(":enabled", ":disabled");
        s.appendChild(n).disabled = !0;
        n.querySelectorAll(":disabled").length !== 2 && o.push(":enabled", ":disabled");
        n.querySelectorAll("*,:x");
        o.push(",.*:")
      })), (e.matchesSelector = ot.test(ct = s.matches || s.webkitMatchesSelector || s.mozMatchesSelector || s.oMatchesSelector || s.msMatchesSelector)) && a(function (n) {
        e.disconnectedMatch = ct.call(n, "*");
        ct.call(n, "[s!='']:x");
        d.push("!=", gt)
      }), o = o.length && new RegExp(o.join("|")), d = d.length && new RegExp(d.join("|")), v = ot.test(s.compareDocumentPosition), et = v || ot.test(s.contains) ? function (n, t) {
        var r = n.nodeType === 9 ? n.documentElement : n,
          i = t && t.parentNode;
        return n === i || !!(i && i.nodeType === 1 && (r.contains ? r.contains(i) : n.compareDocumentPosition && n.compareDocumentPosition(i) & 16))
      } : function (n, t) {
        if (t)
          while (t = t.parentNode)
            if (t === n) return !0;
        return !1
      }, kt = v ? function (n, t) {
        if (n === t) return ut = !0, 0;
        var r = !n.compareDocumentPosition - !t.compareDocumentPosition;
        return r ? r : (r = (n.ownerDocument || n) === (t.ownerDocument || t) ? n.compareDocumentPosition(t) : 1, r & 1 || !e.sortDetached && t.compareDocumentPosition(n) === r) ? n === i || n.ownerDocument === c && et(c, n) ? -1 : t === i || t.ownerDocument === c && et(c, t) ? 1 : w ? nt(w, n) - nt(w, t) : 0 : r & 4 ? -1 : 1
      } : function (n, t) {
        if (n === t) return ut = !0, 0;
        var r, u = 0,
          o = n.parentNode,
          s = t.parentNode,
          f = [n],
          e = [t];
        if (o && s) {
          if (o === s) return wi(n, t)
        } else return n === i ? -1 : t === i ? 1 : o ? -1 : s ? 1 : w ? nt(w, n) - nt(w, t) : 0;
        for (r = n; r = r.parentNode;) f.unshift(r);
        for (r = t; r = r.parentNode;) e.unshift(r);
        while (f[u] === e[u]) u++;
        return u ? wi(f[u], e[u]) : f[u] === c ? -1 : e[u] === c ? 1 : 0
      }, i)
    };
    u.matches = function (n, t) {
      return u(n, null, null, t)
    };
    u.matchesSelector = function (n, t) {
      if ((n.ownerDocument || n) !== i && b(n), t = t.replace(fr, "='$1']"), e.matchesSelector && h && !lt[t + " "] && (!d || !d.test(t)) && (!o || !o.test(t))) try {
        var r = ct.call(n, t);
        if (r || e.disconnectedMatch || n.document && n.document.nodeType !== 11) return r
      } catch (f) {}
      return u(t, i, null, [n]).length > 0
    };
    u.contains = function (n, t) {
      return (n.ownerDocument || n) !== i && b(n), et(n, t)
    };
    u.attr = function (n, r) {
      (n.ownerDocument || n) !== i && b(n);
      var f = t.attrHandle[r.toLowerCase()],
        u = f && gi.call(t.attrHandle, r.toLowerCase()) ? f(n, r, !h) : undefined;
      return u !== undefined ? u : e.attributes || !h ? n.getAttribute(r) : (u = n.getAttributeNode(r)) && u.specified ? u.value : null
    };
    u.escape = function (n) {
      return (n + "").replace(vi, yi)
    };
    u.error = function (n) {
      throw new Error("Syntax error, unrecognized expression: " + n);
    };
    u.uniqueSort = function (n) {
      var r, u = [],
        t = 0,
        i = 0;
      if (ut = !e.detectDuplicates, w = !e.sortStable && n.slice(0), n.sort(kt), ut) {
        while (r = n[i++]) r === n[i] && (t = u.push(i));
        while (t--) n.splice(u[t], 1)
      }
      return w = null, n
    };
    st = u.getText = function (n) {
      var r, i = "",
        u = 0,
        t = n.nodeType;
      if (t) {
        if (t === 1 || t === 9 || t === 11) {
          if (typeof n.textContent == "string") return n.textContent;
          for (n = n.firstChild; n; n = n.nextSibling) i += st(n)
        } else if (t === 3 || t === 4) return n.nodeValue
      } else
        while (r = n[u++]) i += st(r);
      return i
    };
    t = u.selectors = {
      cacheLength: 50,
      createPseudo: l,
      match: vt,
      attrHandle: {},
      find: {},
      relative: {
        ">": {
          dir: "parentNode",
          first: !0
        },
        " ": {
          dir: "parentNode"
        },
        "+": {
          dir: "previousSibling",
          first: !0
        },
        "~": {
          dir: "previousSibling"
        }
      },
      preFilter: {
        ATTR: function (n) {
          return n[1] = n[1].replace(y, p), n[3] = (n[3] || n[4] || n[5] || "").replace(y, p), n[2] === "~=" && (n[3] = " " + n[3] + " "), n.slice(0, 4)
        },
        CHILD: function (n) {
          return n[1] = n[1].toLowerCase(), n[1].slice(0, 3) === "nth" ? (n[3] || u.error(n[0]), n[4] = +(n[4] ? n[5] + (n[6] || 1) : 2 * (n[3] === "even" || n[3] === "odd")), n[5] = +(n[7] + n[8] || n[3] === "odd")) : n[3] && u.error(n[0]), n
        },
        PSEUDO: function (n) {
          var i, t = !n[6] && n[2];
          return vt.CHILD.test(n[0]) ? null : (n[3] ? n[2] = n[4] || n[5] || "" : t && er.test(t) && (i = ft(t, !0)) && (i = t.indexOf(")", t.length - i) - t.length) && (n[0] = n[0].slice(0, i), n[2] = t.slice(0, i)), n.slice(0, 3))
        }
      },
      filter: {
        TAG: function (n) {
          var t = n.replace(y, p).toLowerCase();
          return n === "*" ? function () {
            return !0
          } : function (n) {
            return n.nodeName && n.nodeName.toLowerCase() === t
          }
        },
        CLASS: function (n) {
          var t = hi[n + " "];
          return t || (t = new RegExp("(^|" + r + ")" + n + "(" + r + "|$)")) && hi(n, function (n) {
            return t.test(typeof n.className == "string" && n.className || typeof n.getAttribute != "undefined" && n.getAttribute("class") || "")
          })
        },
        ATTR: function (n, t, i) {
          return function (r) {
            var f = u.attr(r, n);
            return f == null ? t === "!=" : t ? (f += "", t === "=" ? f === i : t === "!=" ? f !== i : t === "^=" ? i && f.indexOf(i) === 0 : t === "*=" ? i && f.indexOf(i) > -1 : t === "$=" ? i && f.slice(-i.length) === i : t === "~=" ? (" " + f.replace(ir, " ") + " ").indexOf(i) > -1 : t === "|=" ? f === i || f.slice(0, i.length + 1) === i + "-" : !1) : !0
          }
        },
        CHILD: function (n, t, i, r, u) {
          var s = n.slice(0, 3) !== "nth",
            o = n.slice(-4) !== "last",
            e = t === "of-type";
          return r === 1 && u === 0 ? function (n) {
            return !!n.parentNode
          } : function (t, i, h) {
            var p, w, y, c, a, b, k = s !== o ? "nextSibling" : "previousSibling",
              d = t.parentNode,
              nt = e && t.nodeName.toLowerCase(),
              g = !h && !e,
              l = !1;
            if (d) {
              if (s) {
                while (k) {
                  for (c = t; c = c[k];)
                    if (e ? c.nodeName.toLowerCase() === nt : c.nodeType === 1) return !1;
                  b = k = n === "only" && !b && "nextSibling"
                }
                return !0
              }
              if (b = [o ? d.firstChild : d.lastChild], o && g) {
                for (c = d, y = c[f] || (c[f] = {}), w = y[c.uniqueID] || (y[c.uniqueID] = {}), p = w[n] || [], a = p[0] === v && p[1], l = a && p[2], c = a && d.childNodes[a]; c = ++a && c && c[k] || (l = a = 0) || b.pop();)
                  if (c.nodeType === 1 && ++l && c === t) {
                    w[n] = [v, a, l];
                    break
                  }
              } else if (g && (c = t, y = c[f] || (c[f] = {}), w = y[c.uniqueID] || (y[c.uniqueID] = {}), p = w[n] || [], a = p[0] === v && p[1], l = a), l === !1)
                while (c = ++a && c && c[k] || (l = a = 0) || b.pop())
                  if ((e ? c.nodeName.toLowerCase() === nt : c.nodeType === 1) && ++l && (g && (y = c[f] || (c[f] = {}), w = y[c.uniqueID] || (y[c.uniqueID] = {}), w[n] = [v, l]), c === t)) break;
              return l -= u, l === r || l % r == 0 && l / r >= 0
            }
          }
        },
        PSEUDO: function (n, i) {
          var e, r = t.pseudos[n] || t.setFilters[n.toLowerCase()] || u.error("unsupported pseudo: " + n);
          return r[f] ? r(i) : r.length > 1 ? (e = [n, n, "", i], t.setFilters.hasOwnProperty(n.toLowerCase()) ? l(function (n, t) {
            for (var u, f = r(n, i), e = f.length; e--;) u = nt(n, f[e]), n[u] = !(t[u] = f[e])
          }) : function (n) {
            return r(n, 0, e)
          }) : r
        }
      },
      pseudos: {
        not: l(function (n) {
          var t = [],
            r = [],
            i = bt(n.replace(at, "$1"));
          return i[f] ? l(function (n, t, r, u) {
            for (var e, o = i(n, null, u, []), f = n.length; f--;)(e = o[f]) && (n[f] = !(t[f] = e))
          }) : function (n, u, f) {
            return t[0] = n, i(t, null, f, r), t[0] = null, !r.pop()
          }
        }),
        has: l(function (n) {
          return function (t) {
            return u(n, t).length > 0
          }
        }),
        contains: l(function (n) {
          return n = n.replace(y, p),
            function (t) {
              return (t.textContent || t.innerText || st(t)).indexOf(n) > -1
            }
        }),
        lang: l(function (n) {
          return or.test(n || "") || u.error("unsupported lang: " + n), n = n.replace(y, p).toLowerCase(),
            function (t) {
              var i;
              do
                if (i = h ? t.lang : t.getAttribute("xml:lang") || t.getAttribute("lang")) return i = i.toLowerCase(), i === n || i.indexOf(n + "-") === 0; while ((t = t.parentNode) && t.nodeType === 1);
              return !1
            }
        }),
        target: function (t) {
          var i = n.location && n.location.hash;
          return i && i.slice(1) === t.id
        },
        root: function (n) {
          return n === s
        },
        focus: function (n) {
          return n === i.activeElement && (!i.hasFocus || i.hasFocus()) && !!(n.type || n.href || ~n.tabIndex)
        },
        enabled: bi(!1),
        disabled: bi(!0),
        checked: function (n) {
          var t = n.nodeName.toLowerCase();
          return t === "input" && !!n.checked || t === "option" && !!n.selected
        },
        selected: function (n) {
          return n.parentNode && n.parentNode.selectedIndex, n.selected === !0
        },
        empty: function (n) {
          for (n = n.firstChild; n; n = n.nextSibling)
            if (n.nodeType < 6) return !1;
          return !0
        },
        parent: function (n) {
          return !t.pseudos.empty(n)
        },
        header: function (n) {
          return hr.test(n.nodeName)
        },
        input: function (n) {
          return sr.test(n.nodeName)
        },
        button: function (n) {
          var t = n.nodeName.toLowerCase();
          return t === "input" && n.type === "button" || t === "button"
        },
        text: function (n) {
          var t;
          return n.nodeName.toLowerCase() === "input" && n.type === "text" && ((t = n.getAttribute("type")) == null || t.toLowerCase() === "text")
        },
        first: it(function () {
          return [0]
        }),
        last: it(function (n, t) {
          return [t - 1]
        }),
        eq: it(function (n, t, i) {
          return [i < 0 ? i + t : i]
        }),
        even: it(function (n, t) {
          for (var i = 0; i < t; i += 2) n.push(i);
          return n
        }),
        odd: it(function (n, t) {
          for (var i = 1; i < t; i += 2) n.push(i);
          return n
        }),
        lt: it(function (n, t, i) {
          for (var r = i < 0 ? i + t : i; --r >= 0;) n.push(r);
          return n
        }),
        gt: it(function (n, t, i) {
          for (var r = i < 0 ? i + t : i; ++r < t;) n.push(r);
          return n
        })
      }
    };
    t.pseudos.nth = t.pseudos.eq;
    for (rt in {
        radio: !0,
        checkbox: !0,
        file: !0,
        password: !0,
        image: !0
      }) t.pseudos[rt] = ar(rt);
    for (rt in {
        submit: !0,
        reset: !0
      }) t.pseudos[rt] = vr(rt);
    return ki.prototype = t.filters = t.pseudos, t.setFilters = new ki, ft = u.tokenize = function (n, i) {
      var e, f, s, o, r, h, c, l = ci[n + " "];
      if (l) return i ? 0 : l.slice(0);
      for (r = n, h = [], c = t.preFilter; r;) {
        (!e || (f = rr.exec(r))) && (f && (r = r.slice(f[0].length) || r), h.push(s = []));
        e = !1;
        (f = ur.exec(r)) && (e = f.shift(), s.push({
          value: e,
          type: f[0].replace(at, " ")
        }), r = r.slice(e.length));
        for (o in t.filter)(f = vt[o].exec(r)) && (!c[o] || (f = c[o](f))) && (e = f.shift(), s.push({
          value: e,
          type: o,
          matches: f
        }), r = r.slice(e.length));
        if (!e) break
      }
      return i ? r.length : r ? u.error(n) : ci(n, h).slice(0)
    }, bt = u.compile = function (n, t) {
      var r, u = [],
        e = [],
        i = lt[n + " "];
      if (!i) {
        for (t || (t = ft(n)), r = t.length; r--;) i = ei(t[r]), i[f] ? u.push(i) : e.push(i);
        i = lt(n, pr(e, u));
        i.selector = n
      }
      return i
    }, si = u.select = function (n, i, r, u) {
      var o, f, e, l, a, c = typeof n == "function" && n,
        s = !u && ft(n = c.selector || n);
      if (r = r || [], s.length === 1) {
        if (f = s[0] = s[0].slice(0), f.length > 2 && (e = f[0]).type === "ID" && i.nodeType === 9 && h && t.relative[f[1].type]) {
          if (i = (t.find.ID(e.matches[0].replace(y, p), i) || [])[0], i) c && (i = i.parentNode);
          else return r;
          n = n.slice(f.shift().value.length)
        }
        for (o = vt.needsContext.test(n) ? 0 : f.length; o--;) {
          if (e = f[o], t.relative[l = e.type]) break;
          if ((a = t.find[l]) && (u = a(e.matches[0].replace(y, p), ni.test(f[0].type) && ri(i.parentNode) || i))) {
            if (f.splice(o, 1), n = u.length && yt(f), !n) return k.apply(r, u), r;
            break
          }
        }
      }
      return (c || bt(n, s))(u, i, !h, r, !i || ni.test(n) && ri(i.parentNode) || i), r
    }, e.sortStable = f.split("").sort(kt).join("") === f, e.detectDuplicates = !!ut, b(), e.sortDetached = a(function (n) {
      return n.compareDocumentPosition(i.createElement("fieldset")) & 1
    }), a(function (n) {
      return n.innerHTML = "<a href='#'><\/a>", n.firstChild.getAttribute("href") === "#"
    }) || ii("type|href|height|width", function (n, t, i) {
      if (!i) return n.getAttribute(t, t.toLowerCase() === "type" ? 1 : 2)
    }), e.attributes && a(function (n) {
      return n.innerHTML = "<input/>", n.firstChild.setAttribute("value", ""), n.firstChild.getAttribute("value") === ""
    }) || ii("value", function (n, t, i) {
      if (!i && n.nodeName.toLowerCase() === "input") return n.defaultValue
    }), a(function (n) {
      return n.getAttribute("disabled") == null
    }) || ii(dt, function (n, t, i) {
      var r;
      if (!i) return n[t] === !0 ? t.toLowerCase() : (r = n.getAttributeNode(t)) && r.specified ? r.value : null
    }), u
  }(n);
  i.find = y;
  i.expr = y.selectors;
  i.expr[":"] = i.expr.pseudos;
  i.uniqueSort = i.unique = y.uniqueSort;
  i.text = y.getText;
  i.isXMLDoc = y.isXML;
  i.contains = y.contains;
  i.escapeSelector = y.escape;
  var g = function (n, t, r) {
      for (var u = [], f = r !== undefined;
        (n = n[t]) && n.nodeType !== 9;)
        if (n.nodeType === 1) {
          if (f && i(n).is(r)) break;
          u.push(n)
        } return u
    },
    ur = function (n, t) {
      for (var i = []; n; n = n.nextSibling) n.nodeType === 1 && n !== t && i.push(n);
      return i
    },
    fr = i.expr.match.needsContext;
  ei = /^<([a-z][^\/\0>:\x20\t\r\n\f]*)[\x20\t\r\n\f]*\/?>(?:<\/\1>|)$/i;
  er = /^.[^:#\[\.,]*$/;
  i.filter = function (n, t, r) {
    var u = t[0];
    return (r && (n = ":not(" + n + ")"), t.length === 1 && u.nodeType === 1) ? i.find.matchesSelector(u, n) ? [u] : [] : i.find.matches(n, i.grep(t, function (n) {
      return n.nodeType === 1
    }))
  };
  i.fn.extend({
    find: function (n) {
      var t, r, u = this.length,
        f = this;
      if (typeof n != "string") return this.pushStack(i(n).filter(function () {
        for (t = 0; t < u; t++)
          if (i.contains(f[t], this)) return !0
      }));
      for (r = this.pushStack([]), t = 0; t < u; t++) i.find(n, f[t], r);
      return u > 1 ? i.uniqueSort(r) : r
    },
    filter: function (n) {
      return this.pushStack(oi(this, n || [], !1))
    },
    not: function (n) {
      return this.pushStack(oi(this, n || [], !0))
    },
    is: function (n) {
      return !!oi(this, typeof n == "string" && fr.test(n) ? i(n) : n || [], !1).length
    }
  });
  sr = /^(?:\s*(<[\w\W]+>)[^>]*|#([\w-]+))$/;
  hr = i.fn.init = function (n, t, r) {
    var f, e;
    if (!n) return this;
    if (r = r || or, typeof n == "string") {
      if (f = n[0] === "<" && n[n.length - 1] === ">" && n.length >= 3 ? [null, n, null] : sr.exec(n), f && (f[1] || !t)) {
        if (f[1]) {
          if (t = t instanceof i ? t[0] : t, i.merge(this, i.parseHTML(f[1], t && t.nodeType ? t.ownerDocument || t : u, !0)), ei.test(f[1]) && i.isPlainObject(t))
            for (f in t) i.isFunction(this[f]) ? this[f](t[f]) : this.attr(f, t[f]);
          return this
        }
        return e = u.getElementById(f[2]), e && (this[0] = e, this.length = 1), this
      }
      return !t || t.jquery ? (t || r).find(n) : this.constructor(t).find(n)
    }
    return n.nodeType ? (this[0] = n, this.length = 1, this) : i.isFunction(n) ? r.ready !== undefined ? r.ready(n) : n(i) : i.makeArray(n, this)
  };
  hr.prototype = i.fn;
  or = i(u);
  cr = /^(?:parents|prev(?:Until|All))/;
  lr = {
    children: !0,
    contents: !0,
    next: !0,
    prev: !0
  };
  i.fn.extend({
    has: function (n) {
      var t = i(n, this),
        r = t.length;
      return this.filter(function () {
        for (var n = 0; n < r; n++)
          if (i.contains(this, t[n])) return !0
      })
    },
    closest: function (n, t) {
      var r, f = 0,
        o = this.length,
        u = [],
        e = typeof n != "string" && i(n);
      if (!fr.test(n))
        for (; f < o; f++)
          for (r = this[f]; r && r !== t; r = r.parentNode)
            if (r.nodeType < 11 && (e ? e.index(r) > -1 : r.nodeType === 1 && i.find.matchesSelector(r, n))) {
              u.push(r);
              break
            } return this.pushStack(u.length > 1 ? i.uniqueSort(u) : u)
    },
    index: function (n) {
      return n ? typeof n == "string" ? ot.call(i(n), this[0]) : ot.call(this, n.jquery ? n[0] : n) : this[0] && this[0].parentNode ? this.first().prevAll().length : -1
    },
    add: function (n, t) {
      return this.pushStack(i.uniqueSort(i.merge(this.get(), i(n, t))))
    },
    addBack: function (n) {
      return this.add(n == null ? this.prevObject : this.prevObject.filter(n))
    }
  });
  i.each({
    parent: function (n) {
      var t = n.parentNode;
      return t && t.nodeType !== 11 ? t : null
    },
    parents: function (n) {
      return g(n, "parentNode")
    },
    parentsUntil: function (n, t, i) {
      return g(n, "parentNode", i)
    },
    next: function (n) {
      return ar(n, "nextSibling")
    },
    prev: function (n) {
      return ar(n, "previousSibling")
    },
    nextAll: function (n) {
      return g(n, "nextSibling")
    },
    prevAll: function (n) {
      return g(n, "previousSibling")
    },
    nextUntil: function (n, t, i) {
      return g(n, "nextSibling", i)
    },
    prevUntil: function (n, t, i) {
      return g(n, "previousSibling", i)
    },
    siblings: function (n) {
      return ur((n.parentNode || {}).firstChild, n)
    },
    children: function (n) {
      return ur(n.firstChild)
    },
    contents: function (n) {
      return l(n, "iframe") ? n.contentDocument : (l(n, "template") && (n = n.content || n), i.merge([], n.childNodes))
    }
  }, function (n, t) {
    i.fn[n] = function (r, u) {
      var f = i.map(this, t, r);
      return n.slice(-5) !== "Until" && (u = r), u && typeof u == "string" && (f = i.filter(u, f)), this.length > 1 && (lr[n] || i.uniqueSort(f), cr.test(n) && f.reverse()), this.pushStack(f)
    }
  });
  h = /[^\x20\t\r\n\f]+/g;
  i.Callbacks = function (n) {
    n = typeof n == "string" ? ne(n) : i.extend({}, n);
    var e, r, h, u, t = [],
      o = [],
      f = -1,
      c = function () {
        for (u = u || n.once, h = e = !0; o.length; f = -1)
          for (r = o.shift(); ++f < t.length;) t[f].apply(r[0], r[1]) === !1 && n.stopOnFalse && (f = t.length, r = !1);
        n.memory || (r = !1);
        e = !1;
        u && (t = r ? [] : "")
      },
      s = {
        add: function () {
          return t && (r && !e && (f = t.length - 1, o.push(r)), function u(r) {
            i.each(r, function (r, f) {
              i.isFunction(f) ? n.unique && s.has(f) || t.push(f) : f && f.length && i.type(f) !== "string" && u(f)
            })
          }(arguments), r && !e && c()), this
        },
        remove: function () {
          return i.each(arguments, function (n, r) {
            for (var u;
              (u = i.inArray(r, t, u)) > -1;) t.splice(u, 1), u <= f && f--
          }), this
        },
        has: function (n) {
          return n ? i.inArray(n, t) > -1 : t.length > 0
        },
        empty: function () {
          return t && (t = []), this
        },
        disable: function () {
          return u = o = [], t = r = "", this
        },
        disabled: function () {
          return !t
        },
        lock: function () {
          return u = o = [], r || e || (t = r = ""), this
        },
        locked: function () {
          return !!u
        },
        fireWith: function (n, t) {
          return u || (t = t || [], t = [n, t.slice ? t.slice() : t], o.push(t), e || c()), this
        },
        fire: function () {
          return s.fireWith(this, arguments), this
        },
        fired: function () {
          return !!h
        }
      };
    return s
  };
  i.extend({
    Deferred: function (t) {
      var u = [
          ["notify", "progress", i.Callbacks("memory"), i.Callbacks("memory"), 2],
          ["resolve", "done", i.Callbacks("once memory"), i.Callbacks("once memory"), 0, "resolved"],
          ["reject", "fail", i.Callbacks("once memory"), i.Callbacks("once memory"), 1, "rejected"]
        ],
        e = "pending",
        f = {
          state: function () {
            return e
          },
          always: function () {
            return r.done(arguments).fail(arguments), this
          },
          "catch": function (n) {
            return f.then(null, n)
          },
          pipe: function () {
            var n = arguments;
            return i.Deferred(function (t) {
              i.each(u, function (u, f) {
                var e = i.isFunction(n[f[4]]) && n[f[4]];
                r[f[1]](function () {
                  var n = e && e.apply(this, arguments);
                  n && i.isFunction(n.promise) ? n.promise().progress(t.notify).done(t.resolve).fail(t.reject) : t[f[0] + "With"](this, e ? [n] : arguments)
                })
              });
              n = null
            }).promise()
          },
          then: function (t, r, f) {
            function o(t, r, u, f) {
              return function () {
                var s = this,
                  h = arguments,
                  l = function () {
                    var n, c;
                    if (!(t < e)) {
                      if (n = u.apply(s, h), n === r.promise()) throw new TypeError("Thenable self-resolution");
                      c = n && (typeof n == "object" || typeof n == "function") && n.then;
                      i.isFunction(c) ? f ? c.call(n, o(e, r, nt, f), o(e, r, pt, f)) : (e++, c.call(n, o(e, r, nt, f), o(e, r, pt, f), o(e, r, nt, r.notifyWith))) : (u !== nt && (s = undefined, h = [n]), (f || r.resolveWith)(s, h))
                    }
                  },
                  c = f ? l : function () {
                    try {
                      l()
                    } catch (n) {
                      i.Deferred.exceptionHook && i.Deferred.exceptionHook(n, c.stackTrace);
                      t + 1 >= e && (u !== pt && (s = undefined, h = [n]), r.rejectWith(s, h))
                    }
                  };
                t ? c() : (i.Deferred.getStackHook && (c.stackTrace = i.Deferred.getStackHook()), n.setTimeout(c))
              }
            }
            var e = 0;
            return i.Deferred(function (n) {
              u[0][3].add(o(0, n, i.isFunction(f) ? f : nt, n.notifyWith));
              u[1][3].add(o(0, n, i.isFunction(t) ? t : nt));
              u[2][3].add(o(0, n, i.isFunction(r) ? r : pt))
            }).promise()
          },
          promise: function (n) {
            return n != null ? i.extend(n, f) : f
          }
        },
        r = {};
      return i.each(u, function (n, t) {
        var i = t[2],
          o = t[5];
        f[t[1]] = i.add;
        o && i.add(function () {
          e = o
        }, u[3 - n][2].disable, u[0][2].lock);
        i.add(t[3].fire);
        r[t[0]] = function () {
          return r[t[0] + "With"](this === r ? undefined : this, arguments), this
        };
        r[t[0] + "With"] = i.fireWith
      }), f.promise(r), t && t.call(r, r), r
    },
    when: function (n) {
      var f = arguments.length,
        t = f,
        e = Array(t),
        u = w.call(arguments),
        r = i.Deferred(),
        o = function (n) {
          return function (t) {
            e[n] = this;
            u[n] = arguments.length > 1 ? w.call(arguments) : t;
            --f || r.resolveWith(e, u)
          }
        };
      if (f <= 1 && (vr(n, r.done(o(t)).resolve, r.reject, !f), r.state() === "pending" || i.isFunction(u[t] && u[t].then))) return r.then();
      while (t--) vr(u[t], o(t), r.reject);
      return r.promise()
    }
  });
  yr = /^(Eval|Internal|Range|Reference|Syntax|Type|URI)Error$/;
  i.Deferred.exceptionHook = function (t, i) {
    n.console && n.console.warn && t && yr.test(t.name) && n.console.warn("jQuery.Deferred exception: " + t.message, t.stack, i)
  };
  i.readyException = function (t) {
    n.setTimeout(function () {
      throw t;
    })
  };
  wt = i.Deferred();
  i.fn.ready = function (n) {
    return wt.then(n).catch(function (n) {
      i.readyException(n)
    }), this
  };
  i.extend({
    isReady: !1,
    readyWait: 1,
    ready: function (n) {
      (n === !0 ? --i.readyWait : i.isReady) || (i.isReady = !0, n !== !0 && --i.readyWait > 0) || wt.resolveWith(u, [i])
    }
  });
  i.ready.then = wt.then;
  u.readyState !== "complete" && (u.readyState === "loading" || u.documentElement.doScroll) ? (u.addEventListener("DOMContentLoaded", bt), n.addEventListener("load", bt)) : n.setTimeout(i.ready);
  v = function (n, t, r, u, f, e, o) {
    var s = 0,
      c = n.length,
      h = r == null;
    if (i.type(r) === "object") {
      f = !0;
      for (s in r) v(n, t, s, r[s], !0, e, o)
    } else if (u !== undefined && (f = !0, i.isFunction(u) || (o = !0), h && (o ? (t.call(n, u), t = null) : (h = t, t = function (n, t, r) {
        return h.call(i(n), r)
      })), t))
      for (; s < c; s++) t(n[s], r, o ? u : u.call(n[s], s, t(n[s], r)));
    return f ? n : h ? t.call(n) : c ? t(n[0], r) : e
  };
  st = function (n) {
    return n.nodeType === 1 || n.nodeType === 9 || !+n.nodeType
  };
  ht.uid = 1;
  ht.prototype = {
    cache: function (n) {
      var t = n[this.expando];
      return t || (t = {}, st(n) && (n.nodeType ? n[this.expando] = t : Object.defineProperty(n, this.expando, {
        value: t,
        configurable: !0
      }))), t
    },
    set: function (n, t, r) {
      var u, f = this.cache(n);
      if (typeof t == "string") f[i.camelCase(t)] = r;
      else
        for (u in t) f[i.camelCase(u)] = t[u];
      return f
    },
    get: function (n, t) {
      return t === undefined ? this.cache(n) : n[this.expando] && n[this.expando][i.camelCase(t)]
    },
    access: function (n, t, i) {
      return t === undefined || t && typeof t == "string" && i === undefined ? this.get(n, t) : (this.set(n, t, i), i !== undefined ? i : t)
    },
    remove: function (n, t) {
      var u, r = n[this.expando];
      if (r !== undefined) {
        if (t !== undefined)
          for (Array.isArray(t) ? t = t.map(i.camelCase) : (t = i.camelCase(t), t = t in r ? [t] : t.match(h) || []), u = t.length; u--;) delete r[t[u]];
        (t === undefined || i.isEmptyObject(r)) && (n.nodeType ? n[this.expando] = undefined : delete n[this.expando])
      }
    },
    hasData: function (n) {
      var t = n[this.expando];
      return t !== undefined && !i.isEmptyObject(t)
    }
  };
  var r = new ht,
    e = new ht,
    te = /^(?:\{[\w\W]*\}|\[[\w\W]*\])$/,
    ie = /[A-Z]/g;
  i.extend({
    hasData: function (n) {
      return e.hasData(n) || r.hasData(n)
    },
    data: function (n, t, i) {
      return e.access(n, t, i)
    },
    removeData: function (n, t) {
      e.remove(n, t)
    },
    _data: function (n, t, i) {
      return r.access(n, t, i)
    },
    _removeData: function (n, t) {
      r.remove(n, t)
    }
  });
  i.fn.extend({
    data: function (n, t) {
      var o, f, s, u = this[0],
        h = u && u.attributes;
      if (n === undefined) {
        if (this.length && (s = e.get(u), u.nodeType === 1 && !r.get(u, "hasDataAttrs"))) {
          for (o = h.length; o--;) h[o] && (f = h[o].name, f.indexOf("data-") === 0 && (f = i.camelCase(f.slice(5)), pr(u, f, s[f])));
          r.set(u, "hasDataAttrs", !0)
        }
        return s
      }
      return typeof n == "object" ? this.each(function () {
        e.set(this, n)
      }) : v(this, function (t) {
        var i;
        if (u && t === undefined) return (i = e.get(u, n), i !== undefined) ? i : (i = pr(u, n), i !== undefined) ? i : void 0;
        this.each(function () {
          e.set(this, n, t)
        })
      }, null, t, arguments.length > 1, null, !0)
    },
    removeData: function (n) {
      return this.each(function () {
        e.remove(this, n)
      })
    }
  });
  i.extend({
    queue: function (n, t, u) {
      var f;
      if (n) return t = (t || "fx") + "queue", f = r.get(n, t), u && (!f || Array.isArray(u) ? f = r.access(n, t, i.makeArray(u)) : f.push(u)), f || []
    },
    dequeue: function (n, t) {
      t = t || "fx";
      var r = i.queue(n, t),
        e = r.length,
        u = r.shift(),
        f = i._queueHooks(n, t),
        o = function () {
          i.dequeue(n, t)
        };
      u === "inprogress" && (u = r.shift(), e--);
      u && (t === "fx" && r.unshift("inprogress"), delete f.stop, u.call(n, o, f));
      !e && f && f.empty.fire()
    },
    _queueHooks: function (n, t) {
      var u = t + "queueHooks";
      return r.get(n, u) || r.access(n, u, {
        empty: i.Callbacks("once memory").add(function () {
          r.remove(n, [t + "queue", u])
        })
      })
    }
  });
  i.fn.extend({
    queue: function (n, t) {
      var r = 2;
      return (typeof n != "string" && (t = n, n = "fx", r--), arguments.length < r) ? i.queue(this[0], n) : t === undefined ? this : this.each(function () {
        var r = i.queue(this, n, t);
        i._queueHooks(this, n);
        n === "fx" && r[0] !== "inprogress" && i.dequeue(this, n)
      })
    },
    dequeue: function (n) {
      return this.each(function () {
        i.dequeue(this, n)
      })
    },
    clearQueue: function (n) {
      return this.queue(n || "fx", [])
    },
    promise: function (n, t) {
      var u, e = 1,
        o = i.Deferred(),
        f = this,
        s = this.length,
        h = function () {
          --e || o.resolveWith(f, [f])
        };
      for (typeof n != "string" && (t = n, n = undefined), n = n || "fx"; s--;) u = r.get(f[s], n + "queueHooks"), u && u.empty && (e++, u.empty.add(h));
      return h(), o.promise(t)
    }
  });
  var wr = /[+-]?(?:\d*\.|)\d+(?:[eE][+-]?\d+|)/.source,
    ct = new RegExp("^(?:([+-])=|)(" + wr + ")([a-z%]*)$", "i"),
    b = ["Top", "Right", "Bottom", "Left"],
    kt = function (n, t) {
      return n = t || n, n.style.display === "none" || n.style.display === "" && i.contains(n.ownerDocument, n) && i.css(n, "display") === "none"
    },
    br = function (n, t, i, r) {
      var f, u, e = {};
      for (u in t) e[u] = n.style[u], n.style[u] = t[u];
      f = i.apply(n, r || []);
      for (u in t) n.style[u] = e[u];
      return f
    };
  si = {};
  i.fn.extend({
    show: function () {
      return tt(this, !0)
    },
    hide: function () {
      return tt(this)
    },
    toggle: function (n) {
      return typeof n == "boolean" ? n ? this.show() : this.hide() : this.each(function () {
        kt(this) ? i(this).show() : i(this).hide()
      })
    }
  });
  var dr = /^(?:checkbox|radio)$/i,
    gr = /<([a-z][^\/\0>\x20\t\r\n\f]+)/i,
    nu = /^$|\/(?:java|ecma)script/i,
    c = {
      option: [1, "<select multiple='multiple'>", "<\/select>"],
      thead: [1, "<table>", "<\/table>"],
      col: [2, "<table><colgroup>", "<\/colgroup><\/table>"],
      tr: [2, "<table><tbody>", "<\/tbody><\/table>"],
      td: [3, "<table><tbody><tr>", "<\/tr><\/tbody><\/table>"],
      _default: [0, "", ""]
    };
  c.optgroup = c.option;
  c.tbody = c.tfoot = c.colgroup = c.caption = c.thead;
  c.th = c.td;
  tu = /<|&#?\w+;/,
    function () {
      var i = u.createDocumentFragment(),
        n = i.appendChild(u.createElement("div")),
        t = u.createElement("input");
      t.setAttribute("type", "radio");
      t.setAttribute("checked", "checked");
      t.setAttribute("name", "t");
      n.appendChild(t);
      f.checkClone = n.cloneNode(!0).cloneNode(!0).lastChild.checked;
      n.innerHTML = "<textarea>x<\/textarea>";
      f.noCloneChecked = !!n.cloneNode(!0).lastChild.defaultValue
    }();
  var dt = u.documentElement,
    fe = /^key/,
    ee = /^(?:mouse|pointer|contextmenu|drag|drop)|click/,
    ru = /^([^.]*)(?:\.(.+)|)/;
  i.event = {
    global: {},
    add: function (n, t, u, f, e) {
      var v, y, w, p, b, c, s, l, o, k, d, a = r.get(n);
      if (a)
        for (u.handler && (v = u, u = v.handler, e = v.selector), e && i.find.matchesSelector(dt, e), u.guid || (u.guid = i.guid++), (p = a.events) || (p = a.events = {}), (y = a.handle) || (y = a.handle = function (t) {
            return typeof i != "undefined" && i.event.triggered !== t.type ? i.event.dispatch.apply(n, arguments) : undefined
          }), t = (t || "").match(h) || [""], b = t.length; b--;)(w = ru.exec(t[b]) || [], o = d = w[1], k = (w[2] || "").split(".").sort(), o) && (s = i.event.special[o] || {}, o = (e ? s.delegateType : s.bindType) || o, s = i.event.special[o] || {}, c = i.extend({
          type: o,
          origType: d,
          data: f,
          handler: u,
          guid: u.guid,
          selector: e,
          needsContext: e && i.expr.match.needsContext.test(e),
          namespace: k.join(".")
        }, v), (l = p[o]) || (l = p[o] = [], l.delegateCount = 0, s.setup && s.setup.call(n, f, k, y) !== !1 || n.addEventListener && n.addEventListener(o, y)), s.add && (s.add.call(n, c), c.handler.guid || (c.handler.guid = u.guid)), e ? l.splice(l.delegateCount++, 0, c) : l.push(c), i.event.global[o] = !0)
    },
    remove: function (n, t, u, f, e) {
      var y, k, c, v, p, s, l, a, o, b, d, w = r.hasData(n) && r.get(n);
      if (w && (v = w.events)) {
        for (t = (t || "").match(h) || [""], p = t.length; p--;) {
          if (c = ru.exec(t[p]) || [], o = d = c[1], b = (c[2] || "").split(".").sort(), !o) {
            for (o in v) i.event.remove(n, o + t[p], u, f, !0);
            continue
          }
          for (l = i.event.special[o] || {}, o = (f ? l.delegateType : l.bindType) || o, a = v[o] || [], c = c[2] && new RegExp("(^|\\.)" + b.join("\\.(?:.*\\.|)") + "(\\.|$)"), k = y = a.length; y--;) s = a[y], (e || d === s.origType) && (!u || u.guid === s.guid) && (!c || c.test(s.namespace)) && (!f || f === s.selector || f === "**" && s.selector) && (a.splice(y, 1), s.selector && a.delegateCount--, l.remove && l.remove.call(n, s));
          k && !a.length && (l.teardown && l.teardown.call(n, b, w.handle) !== !1 || i.removeEvent(n, o, w.handle), delete v[o])
        }
        i.isEmptyObject(v) && r.remove(n, "handle events")
      }
    },
    dispatch: function (n) {
      var t = i.event.fix(n),
        u, c, s, e, f, l, h = new Array(arguments.length),
        a = (r.get(this, "events") || {})[t.type] || [],
        o = i.event.special[t.type] || {};
      for (h[0] = t, u = 1; u < arguments.length; u++) h[u] = arguments[u];
      if (t.delegateTarget = this, !o.preDispatch || o.preDispatch.call(this, t) !== !1) {
        for (l = i.event.handlers.call(this, t, a), u = 0;
          (e = l[u++]) && !t.isPropagationStopped();)
          for (t.currentTarget = e.elem, c = 0;
            (f = e.handlers[c++]) && !t.isImmediatePropagationStopped();)(!t.rnamespace || t.rnamespace.test(f.namespace)) && (t.handleObj = f, t.data = f.data, s = ((i.event.special[f.origType] || {}).handle || f.handler).apply(e.elem, h), s !== undefined && (t.result = s) === !1 && (t.preventDefault(), t.stopPropagation()));
        return o.postDispatch && o.postDispatch.call(this, t), t.result
      }
    },
    handlers: function (n, t) {
      var f, e, u, o, s, c = [],
        h = t.delegateCount,
        r = n.target;
      if (h && r.nodeType && !(n.type === "click" && n.button >= 1))
        for (; r !== this; r = r.parentNode || this)
          if (r.nodeType === 1 && !(n.type === "click" && r.disabled === !0)) {
            for (o = [], s = {}, f = 0; f < h; f++) e = t[f], u = e.selector + " ", s[u] === undefined && (s[u] = e.needsContext ? i(u, this).index(r) > -1 : i.find(u, this, null, [r]).length), s[u] && o.push(e);
            o.length && c.push({
              elem: r,
              handlers: o
            })
          } return r = this, h < t.length && c.push({
        elem: r,
        handlers: t.slice(h)
      }), c
    },
    addProp: function (n, t) {
      Object.defineProperty(i.Event.prototype, n, {
        enumerable: !0,
        configurable: !0,
        get: i.isFunction(t) ? function () {
          if (this.originalEvent) return t(this.originalEvent)
        } : function () {
          if (this.originalEvent) return this.originalEvent[n]
        },
        set: function (t) {
          Object.defineProperty(this, n, {
            enumerable: !0,
            configurable: !0,
            writable: !0,
            value: t
          })
        }
      })
    },
    fix: function (n) {
      return n[i.expando] ? n : new i.Event(n)
    },
    special: {
      load: {
        noBubble: !0
      },
      focus: {
        trigger: function () {
          if (this !== uu() && this.focus) return this.focus(), !1
        },
        delegateType: "focusin"
      },
      blur: {
        trigger: function () {
          if (this === uu() && this.blur) return this.blur(), !1
        },
        delegateType: "focusout"
      },
      click: {
        trigger: function () {
          if (this.type === "checkbox" && this.click && l(this, "input")) return this.click(), !1
        },
        _default: function (n) {
          return l(n.target, "a")
        }
      },
      beforeunload: {
        postDispatch: function (n) {
          n.result !== undefined && n.originalEvent && (n.originalEvent.returnValue = n.result)
        }
      }
    }
  };
  i.removeEvent = function (n, t, i) {
    n.removeEventListener && n.removeEventListener(t, i)
  };
  i.Event = function (n, t) {
    if (!(this instanceof i.Event)) return new i.Event(n, t);
    n && n.type ? (this.originalEvent = n, this.type = n.type, this.isDefaultPrevented = n.defaultPrevented || n.defaultPrevented === undefined && n.returnValue === !1 ? gt : it, this.target = n.target && n.target.nodeType === 3 ? n.target.parentNode : n.target, this.currentTarget = n.currentTarget, this.relatedTarget = n.relatedTarget) : this.type = n;
    t && i.extend(this, t);
    this.timeStamp = n && n.timeStamp || i.now();
    this[i.expando] = !0
  };
  i.Event.prototype = {
    constructor: i.Event,
    isDefaultPrevented: it,
    isPropagationStopped: it,
    isImmediatePropagationStopped: it,
    isSimulated: !1,
    preventDefault: function () {
      var n = this.originalEvent;
      this.isDefaultPrevented = gt;
      n && !this.isSimulated && n.preventDefault()
    },
    stopPropagation: function () {
      var n = this.originalEvent;
      this.isPropagationStopped = gt;
      n && !this.isSimulated && n.stopPropagation()
    },
    stopImmediatePropagation: function () {
      var n = this.originalEvent;
      this.isImmediatePropagationStopped = gt;
      n && !this.isSimulated && n.stopImmediatePropagation();
      this.stopPropagation()
    }
  };
  i.each({
    altKey: !0,
    bubbles: !0,
    cancelable: !0,
    changedTouches: !0,
    ctrlKey: !0,
    detail: !0,
    eventPhase: !0,
    metaKey: !0,
    pageX: !0,
    pageY: !0,
    shiftKey: !0,
    view: !0,
    char: !0,
    charCode: !0,
    key: !0,
    keyCode: !0,
    button: !0,
    buttons: !0,
    clientX: !0,
    clientY: !0,
    offsetX: !0,
    offsetY: !0,
    pointerId: !0,
    pointerType: !0,
    screenX: !0,
    screenY: !0,
    targetTouches: !0,
    toElement: !0,
    touches: !0,
    which: function (n) {
      var t = n.button;
      return n.which == null && fe.test(n.type) ? n.charCode != null ? n.charCode : n.keyCode : !n.which && t !== undefined && ee.test(n.type) ? t & 1 ? 1 : t & 2 ? 3 : t & 4 ? 2 : 0 : n.which
    }
  }, i.event.addProp);
  i.each({
    mouseenter: "mouseover",
    mouseleave: "mouseout",
    pointerenter: "pointerover",
    pointerleave: "pointerout"
  }, function (n, t) {
    i.event.special[n] = {
      delegateType: t,
      bindType: t,
      handle: function (n) {
        var u, f = this,
          r = n.relatedTarget,
          e = n.handleObj;
        return r && (r === f || i.contains(f, r)) || (n.type = e.origType, u = e.handler.apply(this, arguments), n.type = t), u
      }
    }
  });
  i.fn.extend({
    on: function (n, t, i, r) {
      return ci(this, n, t, i, r)
    },
    one: function (n, t, i, r) {
      return ci(this, n, t, i, r, 1)
    },
    off: function (n, t, r) {
      var u, f;
      if (n && n.preventDefault && n.handleObj) return u = n.handleObj, i(n.delegateTarget).off(u.namespace ? u.origType + "." + u.namespace : u.origType, u.selector, u.handler), this;
      if (typeof n == "object") {
        for (f in n) this.off(f, t, n[f]);
        return this
      }
      return (t === !1 || typeof t == "function") && (r = t, t = undefined), r === !1 && (r = it), this.each(function () {
        i.event.remove(this, n, r, t)
      })
    }
  });
  var oe = /<(?!area|br|col|embed|hr|img|input|link|meta|param)(([a-z][^\/\0>\x20\t\r\n\f]*)[^>]*)\/>/gi,
    se = /<script|<style|<link/i,
    he = /checked\s*(?:[^=]|=\s*.checked.)/i,
    ce = /^true\/(.*)/,
    le = /^\s*<!(?:\[CDATA\[|--)|(?:\]\]|--)>\s*$/g;
  i.extend({
    htmlPrefilter: function (n) {
      return n.replace(oe, "<$1><\/$2>")
    },
    clone: function (n, t, r) {
      var u, c, s, e, h = n.cloneNode(!0),
        l = i.contains(n.ownerDocument, n);
      if (!f.noCloneChecked && (n.nodeType === 1 || n.nodeType === 11) && !i.isXMLDoc(n))
        for (e = o(h), s = o(n), u = 0, c = s.length; u < c; u++) ye(s[u], e[u]);
      if (t)
        if (r)
          for (s = s || o(n), e = e || o(h), u = 0, c = s.length; u < c; u++) eu(s[u], e[u]);
        else eu(n, h);
      return e = o(h, "script"), e.length > 0 && hi(e, !l && o(n, "script")), h
    },
    cleanData: function (n) {
      for (var u, t, f, s = i.event.special, o = 0;
        (t = n[o]) !== undefined; o++)
        if (st(t)) {
          if (u = t[r.expando]) {
            if (u.events)
              for (f in u.events) s[f] ? i.event.remove(t, f) : i.removeEvent(t, f, u.handle);
            t[r.expando] = undefined
          }
          t[e.expando] && (t[e.expando] = undefined)
        }
    }
  });
  i.fn.extend({
    detach: function (n) {
      return ou(this, n, !0)
    },
    remove: function (n) {
      return ou(this, n)
    },
    text: function (n) {
      return v(this, function (n) {
        return n === undefined ? i.text(this) : this.empty().each(function () {
          (this.nodeType === 1 || this.nodeType === 11 || this.nodeType === 9) && (this.textContent = n)
        })
      }, null, n, arguments.length)
    },
    append: function () {
      return rt(this, arguments, function (n) {
        if (this.nodeType === 1 || this.nodeType === 11 || this.nodeType === 9) {
          var t = fu(this, n);
          t.appendChild(n)
        }
      })
    },
    prepend: function () {
      return rt(this, arguments, function (n) {
        if (this.nodeType === 1 || this.nodeType === 11 || this.nodeType === 9) {
          var t = fu(this, n);
          t.insertBefore(n, t.firstChild)
        }
      })
    },
    before: function () {
      return rt(this, arguments, function (n) {
        this.parentNode && this.parentNode.insertBefore(n, this)
      })
    },
    after: function () {
      return rt(this, arguments, function (n) {
        this.parentNode && this.parentNode.insertBefore(n, this.nextSibling)
      })
    },
    empty: function () {
      for (var n, t = 0;
        (n = this[t]) != null; t++) n.nodeType === 1 && (i.cleanData(o(n, !1)), n.textContent = "");
      return this
    },
    clone: function (n, t) {
      return n = n == null ? !1 : n, t = t == null ? n : t, this.map(function () {
        return i.clone(this, n, t)
      })
    },
    html: function (n) {
      return v(this, function (n) {
        var t = this[0] || {},
          r = 0,
          u = this.length;
        if (n === undefined && t.nodeType === 1) return t.innerHTML;
        if (typeof n == "string" && !se.test(n) && !c[(gr.exec(n) || ["", ""])[1].toLowerCase()]) {
          n = i.htmlPrefilter(n);
          try {
            for (; r < u; r++) t = this[r] || {}, t.nodeType === 1 && (i.cleanData(o(t, !1)), t.innerHTML = n);
            t = 0
          } catch (f) {}
        }
        t && this.empty().append(n)
      }, null, n, arguments.length)
    },
    replaceWith: function () {
      var n = [];
      return rt(this, arguments, function (t) {
        var r = this.parentNode;
        i.inArray(this, n) < 0 && (i.cleanData(o(this)), r && r.replaceChild(t, this))
      }, n)
    }
  });
  i.each({
    appendTo: "append",
    prependTo: "prepend",
    insertBefore: "before",
    insertAfter: "after",
    replaceAll: "replaceWith"
  }, function (n, t) {
    i.fn[n] = function (n) {
      for (var u, f = [], e = i(n), o = e.length - 1, r = 0; r <= o; r++) u = r === o ? this : this.clone(!0), i(e[r])[t](u), ui.apply(f, u.get());
      return this.pushStack(f)
    }
  });
  var su = /^margin/,
    li = new RegExp("^(" + wr + ")(?!px)[a-z%]+$", "i"),
    ni = function (t) {
      var i = t.ownerDocument.defaultView;
      return i && i.opener || (i = n), i.getComputedStyle(t)
    };
  (function () {
    function r() {
      if (t) {
        t.style.cssText = "box-sizing:border-box;position:relative;display:block;margin:auto;border:1px;padding:1px;top:1%;width:50%";
        t.innerHTML = "";
        dt.appendChild(e);
        var i = n.getComputedStyle(t);
        o = i.top !== "1%";
        c = i.marginLeft === "2px";
        s = i.width === "4px";
        t.style.marginRight = "50%";
        h = i.marginRight === "4px";
        dt.removeChild(e);
        t = null
      }
    }
    var o, s, h, c, e = u.createElement("div"),
      t = u.createElement("div");
    t.style && (t.style.backgroundClip = "content-box", t.cloneNode(!0).style.backgroundClip = "", f.clearCloneStyle = t.style.backgroundClip === "content-box", e.style.cssText = "border:0;width:8px;height:0;top:0;left:-9999px;padding:0;margin-top:1px;position:absolute", e.appendChild(t), i.extend(f, {
      pixelPosition: function () {
        return r(), o
      },
      boxSizingReliable: function () {
        return r(), s
      },
      pixelMarginRight: function () {
        return r(), h
      },
      reliableMarginLeft: function () {
        return r(), c
      }
    }))
  })();
  var pe = /^(none|table(?!-c[ea]).+)/,
    cu = /^--/,
    we = {
      position: "absolute",
      visibility: "hidden",
      display: "block"
    },
    lu = {
      letterSpacing: "0",
      fontWeight: "400"
    },
    au = ["Webkit", "Moz", "ms"],
    vu = u.createElement("div").style;
  i.extend({
    cssHooks: {
      opacity: {
        get: function (n, t) {
          if (t) {
            var i = lt(n, "opacity");
            return i === "" ? "1" : i
          }
        }
      }
    },
    cssNumber: {
      animationIterationCount: !0,
      columnCount: !0,
      fillOpacity: !0,
      flexGrow: !0,
      flexShrink: !0,
      fontWeight: !0,
      lineHeight: !0,
      opacity: !0,
      order: !0,
      orphans: !0,
      widows: !0,
      zIndex: !0,
      zoom: !0
    },
    cssProps: {
      float: "cssFloat"
    },
    style: function (n, t, r, u) {
      if (n && n.nodeType !== 3 && n.nodeType !== 8 && n.style) {
        var e, s, o, c = i.camelCase(t),
          l = cu.test(t),
          h = n.style;
        if (l || (t = yu(c)), o = i.cssHooks[t] || i.cssHooks[c], r !== undefined) {
          if (s = typeof r, s === "string" && (e = ct.exec(r)) && e[1] && (r = kr(n, t, e), s = "number"), r == null || r !== r) return;
          s === "number" && (r += e && e[3] || (i.cssNumber[c] ? "" : "px"));
          f.clearCloneStyle || r !== "" || t.indexOf("background") !== 0 || (h[t] = "inherit");
          o && "set" in o && (r = o.set(n, r, u)) === undefined || (l ? h.setProperty(t, r) : h[t] = r)
        } else return o && "get" in o && (e = o.get(n, !1, u)) !== undefined ? e : h[t]
      }
    },
    css: function (n, t, r, u) {
      var f, o, e, s = i.camelCase(t),
        h = cu.test(t);
      return (h || (t = yu(s)), e = i.cssHooks[t] || i.cssHooks[s], e && "get" in e && (f = e.get(n, !0, r)), f === undefined && (f = lt(n, t, u)), f === "normal" && t in lu && (f = lu[t]), r === "" || r) ? (o = parseFloat(f), r === !0 || isFinite(o) ? o || 0 : f) : f
    }
  });
  i.each(["height", "width"], function (n, t) {
    i.cssHooks[t] = {
      get: function (n, r, u) {
        if (r) return pe.test(i.css(n, "display")) && (!n.getClientRects().length || !n.getBoundingClientRect().width) ? br(n, we, function () {
          return bu(n, t, u)
        }) : bu(n, t, u)
      },
      set: function (n, r, u) {
        var f, e = u && ni(n),
          o = u && wu(n, t, u, i.css(n, "boxSizing", !1, e) === "border-box", e);
        return o && (f = ct.exec(r)) && (f[3] || "px") !== "px" && (n.style[t] = r, r = i.css(n, t)), pu(n, r, o)
      }
    }
  });
  i.cssHooks.marginLeft = hu(f.reliableMarginLeft, function (n, t) {
    if (t) return (parseFloat(lt(n, "marginLeft")) || n.getBoundingClientRect().left - br(n, {
      marginLeft: 0
    }, function () {
      return n.getBoundingClientRect().left
    })) + "px"
  });
  i.each({
    margin: "",
    padding: "",
    border: "Width"
  }, function (n, t) {
    i.cssHooks[n + t] = {
      expand: function (i) {
        for (var r = 0, f = {}, u = typeof i == "string" ? i.split(" ") : [i]; r < 4; r++) f[n + b[r] + t] = u[r] || u[r - 2] || u[0];
        return f
      }
    };
    su.test(n) || (i.cssHooks[n + t].set = pu)
  });
  i.fn.extend({
    css: function (n, t) {
      return v(this, function (n, t, r) {
        var f, e, o = {},
          u = 0;
        if (Array.isArray(t)) {
          for (f = ni(n), e = t.length; u < e; u++) o[t[u]] = i.css(n, t[u], !1, f);
          return o
        }
        return r !== undefined ? i.style(n, t, r) : i.css(n, t)
      }, n, t, arguments.length > 1)
    }
  });
  i.Tween = s;
  s.prototype = {
    constructor: s,
    init: function (n, t, r, u, f, e) {
      this.elem = n;
      this.prop = r;
      this.easing = f || i.easing._default;
      this.options = t;
      this.start = this.now = this.cur();
      this.end = u;
      this.unit = e || (i.cssNumber[r] ? "" : "px")
    },
    cur: function () {
      var n = s.propHooks[this.prop];
      return n && n.get ? n.get(this) : s.propHooks._default.get(this)
    },
    run: function (n) {
      var t, r = s.propHooks[this.prop];
      return this.pos = this.options.duration ? t = i.easing[this.easing](n, this.options.duration * n, 0, 1, this.options.duration) : t = n, this.now = (this.end - this.start) * t + this.start, this.options.step && this.options.step.call(this.elem, this.now, this), r && r.set ? r.set(this) : s.propHooks._default.set(this), this
    }
  };
  s.prototype.init.prototype = s.prototype;
  s.propHooks = {
    _default: {
      get: function (n) {
        var t;
        return n.elem.nodeType !== 1 || n.elem[n.prop] != null && n.elem.style[n.prop] == null ? n.elem[n.prop] : (t = i.css(n.elem, n.prop, ""), !t || t === "auto" ? 0 : t)
      },
      set: function (n) {
        i.fx.step[n.prop] ? i.fx.step[n.prop](n) : n.elem.nodeType === 1 && (n.elem.style[i.cssProps[n.prop]] != null || i.cssHooks[n.prop]) ? i.style(n.elem, n.prop, n.now + n.unit) : n.elem[n.prop] = n.now
      }
    }
  };
  s.propHooks.scrollTop = s.propHooks.scrollLeft = {
    set: function (n) {
      n.elem.nodeType && n.elem.parentNode && (n.elem[n.prop] = n.now)
    }
  };
  i.easing = {
    linear: function (n) {
      return n
    },
    swing: function (n) {
      return .5 - Math.cos(n * Math.PI) / 2
    },
    _default: "swing"
  };
  i.fx = s.prototype.init;
  i.fx.step = {};
  ku = /^(?:toggle|show|hide)$/;
  du = /queueHooks$/;
  i.Animation = i.extend(a, {
    tweeners: {
      "*": [function (n, t) {
        var i = this.createTween(n, t);
        return kr(i.elem, n, ct.exec(t), i), i
      }]
    },
    tweener: function (n, t) {
      i.isFunction(n) ? (t = n, n = ["*"]) : n = n.match(h);
      for (var r, u = 0, f = n.length; u < f; u++) r = n[u], a.tweeners[r] = a.tweeners[r] || [], a.tweeners[r].unshift(t)
    },
    prefilters: [ke],
    prefilter: function (n, t) {
      t ? a.prefilters.unshift(n) : a.prefilters.push(n)
    }
  });
  i.speed = function (n, t, r) {
    var u = n && typeof n == "object" ? i.extend({}, n) : {
      complete: r || !r && t || i.isFunction(n) && n,
      duration: n,
      easing: r && t || t && !i.isFunction(t) && t
    };
    return i.fx.off ? u.duration = 0 : typeof u.duration != "number" && (u.duration = u.duration in i.fx.speeds ? i.fx.speeds[u.duration] : i.fx.speeds._default), (u.queue == null || u.queue === !0) && (u.queue = "fx"), u.old = u.complete, u.complete = function () {
      i.isFunction(u.old) && u.old.call(this);
      u.queue && i.dequeue(this, u.queue)
    }, u
  };
  i.fn.extend({
    fadeTo: function (n, t, i, r) {
      return this.filter(kt).css("opacity", 0).show().end().animate({
        opacity: t
      }, n, i, r)
    },
    animate: function (n, t, u, f) {
      var s = i.isEmptyObject(n),
        o = i.speed(t, u, f),
        e = function () {
          var t = a(this, i.extend({}, n), o);
          (s || r.get(this, "finish")) && t.stop(!0)
        };
      return e.finish = e, s || o.queue === !1 ? this.each(e) : this.queue(o.queue, e)
    },
    stop: function (n, t, u) {
      var f = function (n) {
        var t = n.stop;
        delete n.stop;
        t(u)
      };
      return typeof n != "string" && (u = t, t = n, n = undefined), t && n !== !1 && this.queue(n || "fx", []), this.each(function () {
        var s = !0,
          t = n != null && n + "queueHooks",
          o = i.timers,
          e = r.get(this);
        if (t) e[t] && e[t].stop && f(e[t]);
        else
          for (t in e) e[t] && e[t].stop && du.test(t) && f(e[t]);
        for (t = o.length; t--;) o[t].elem === this && (n == null || o[t].queue === n) && (o[t].anim.stop(u), s = !1, o.splice(t, 1));
        (s || !u) && i.dequeue(this, n)
      })
    },
    finish: function (n) {
      return n !== !1 && (n = n || "fx"), this.each(function () {
        var t, e = r.get(this),
          u = e[n + "queue"],
          o = e[n + "queueHooks"],
          f = i.timers,
          s = u ? u.length : 0;
        for (e.finish = !0, i.queue(this, n, []), o && o.stop && o.stop.call(this, !0), t = f.length; t--;) f[t].elem === this && f[t].queue === n && (f[t].anim.stop(!0), f.splice(t, 1));
        for (t = 0; t < s; t++) u[t] && u[t].finish && u[t].finish.call(this);
        delete e.finish
      })
    }
  });
  i.each(["toggle", "show", "hide"], function (n, t) {
    var r = i.fn[t];
    i.fn[t] = function (n, i, u) {
      return n == null || typeof n == "boolean" ? r.apply(this, arguments) : this.animate(ii(t, !0), n, i, u)
    }
  });
  i.each({
    slideDown: ii("show"),
    slideUp: ii("hide"),
    slideToggle: ii("toggle"),
    fadeIn: {
      opacity: "show"
    },
    fadeOut: {
      opacity: "hide"
    },
    fadeToggle: {
      opacity: "toggle"
    }
  }, function (n, t) {
    i.fn[n] = function (n, i, r) {
      return this.animate(t, n, i, r)
    }
  });
  i.timers = [];
  i.fx.tick = function () {
    var r, n = 0,
      t = i.timers;
    for (ut = i.now(); n < t.length; n++) r = t[n], r() || t[n] !== r || t.splice(n--, 1);
    t.length || i.fx.stop();
    ut = undefined
  };
  i.fx.timer = function (n) {
    i.timers.push(n);
    i.fx.start()
  };
  i.fx.interval = 13;
  i.fx.start = function () {
    ti || (ti = !0, ai())
  };
  i.fx.stop = function () {
    ti = null
  };
  i.fx.speeds = {
    slow: 600,
    fast: 200,
    _default: 400
  };
  i.fn.delay = function (t, r) {
      return t = i.fx ? i.fx.speeds[t] || t : t, r = r || "fx", this.queue(r, function (i, r) {
        var u = n.setTimeout(i, t);
        r.stop = function () {
          n.clearTimeout(u)
        }
      })
    },
    function () {
      var n = u.createElement("input"),
        t = u.createElement("select"),
        i = t.appendChild(u.createElement("option"));
      n.type = "checkbox";
      f.checkOn = n.value !== "";
      f.optSelected = i.selected;
      n = u.createElement("input");
      n.value = "t";
      n.type = "radio";
      f.radioValue = n.value === "t"
    }();
  ft = i.expr.attrHandle;
  i.fn.extend({
    attr: function (n, t) {
      return v(this, i.attr, n, t, arguments.length > 1)
    },
    removeAttr: function (n) {
      return this.each(function () {
        i.removeAttr(this, n)
      })
    }
  });
  i.extend({
    attr: function (n, t, r) {
      var u, f, e = n.nodeType;
      if (e !== 3 && e !== 8 && e !== 2) {
        if (typeof n.getAttribute == "undefined") return i.prop(n, t, r);
        if (e === 1 && i.isXMLDoc(n) || (f = i.attrHooks[t.toLowerCase()] || (i.expr.match.bool.test(t) ? tf : undefined)), r !== undefined) {
          if (r === null) {
            i.removeAttr(n, t);
            return
          }
          return f && "set" in f && (u = f.set(n, r, t)) !== undefined ? u : (n.setAttribute(t, r + ""), r)
        }
        return f && "get" in f && (u = f.get(n, t)) !== null ? u : (u = i.find.attr(n, t), u == null ? undefined : u)
      }
    },
    attrHooks: {
      type: {
        set: function (n, t) {
          if (!f.radioValue && t === "radio" && l(n, "input")) {
            var i = n.value;
            return n.setAttribute("type", t), i && (n.value = i), t
          }
        }
      }
    },
    removeAttr: function (n, t) {
      var i, u = 0,
        r = t && t.match(h);
      if (r && n.nodeType === 1)
        while (i = r[u++]) n.removeAttribute(i)
    }
  });
  tf = {
    set: function (n, t, r) {
      return t === !1 ? i.removeAttr(n, r) : n.setAttribute(r, r), r
    }
  };
  i.each(i.expr.match.bool.source.match(/\w+/g), function (n, t) {
    var r = ft[t] || i.find.attr;
    ft[t] = function (n, t, i) {
      var f, e, u = t.toLowerCase();
      return i || (e = ft[u], ft[u] = f, f = r(n, t, i) != null ? u : null, ft[u] = e), f
    }
  });
  rf = /^(?:input|select|textarea|button)$/i;
  uf = /^(?:a|area)$/i;
  i.fn.extend({
    prop: function (n, t) {
      return v(this, i.prop, n, t, arguments.length > 1)
    },
    removeProp: function (n) {
      return this.each(function () {
        delete this[i.propFix[n] || n]
      })
    }
  });
  i.extend({
    prop: function (n, t, r) {
      var f, u, e = n.nodeType;
      if (e !== 3 && e !== 8 && e !== 2) return (e === 1 && i.isXMLDoc(n) || (t = i.propFix[t] || t, u = i.propHooks[t]), r !== undefined) ? u && "set" in u && (f = u.set(n, r, t)) !== undefined ? f : n[t] = r : u && "get" in u && (f = u.get(n, t)) !== null ? f : n[t]
    },
    propHooks: {
      tabIndex: {
        get: function (n) {
          var t = i.find.attr(n, "tabindex");
          return t ? parseInt(t, 10) : rf.test(n.nodeName) || uf.test(n.nodeName) && n.href ? 0 : -1
        }
      }
    },
    propFix: {
      "for": "htmlFor",
      "class": "className"
    }
  });
  f.optSelected || (i.propHooks.selected = {
    get: function (n) {
      var t = n.parentNode;
      return t && t.parentNode && t.parentNode.selectedIndex, null
    },
    set: function (n) {
      var t = n.parentNode;
      t && (t.selectedIndex, t.parentNode && t.parentNode.selectedIndex)
    }
  });
  i.each(["tabIndex", "readOnly", "maxLength", "cellSpacing", "cellPadding", "rowSpan", "colSpan", "useMap", "frameBorder", "contentEditable"], function () {
    i.propFix[this.toLowerCase()] = this
  });
  i.fn.extend({
    addClass: function (n) {
      var o, r, t, u, f, s, e, c = 0;
      if (i.isFunction(n)) return this.each(function (t) {
        i(this).addClass(n.call(this, t, d(this)))
      });
      if (typeof n == "string" && n)
        for (o = n.match(h) || []; r = this[c++];)
          if (u = d(r), t = r.nodeType === 1 && " " + k(u) + " ", t) {
            for (s = 0; f = o[s++];) t.indexOf(" " + f + " ") < 0 && (t += f + " ");
            e = k(t);
            u !== e && r.setAttribute("class", e)
          } return this
    },
    removeClass: function (n) {
      var o, r, t, u, f, s, e, c = 0;
      if (i.isFunction(n)) return this.each(function (t) {
        i(this).removeClass(n.call(this, t, d(this)))
      });
      if (!arguments.length) return this.attr("class", "");
      if (typeof n == "string" && n)
        for (o = n.match(h) || []; r = this[c++];)
          if (u = d(r), t = r.nodeType === 1 && " " + k(u) + " ", t) {
            for (s = 0; f = o[s++];)
              while (t.indexOf(" " + f + " ") > -1) t = t.replace(" " + f + " ", " ");
            e = k(t);
            u !== e && r.setAttribute("class", e)
          } return this
    },
    toggleClass: function (n, t) {
      var u = typeof n;
      return typeof t == "boolean" && u === "string" ? t ? this.addClass(n) : this.removeClass(n) : i.isFunction(n) ? this.each(function (r) {
        i(this).toggleClass(n.call(this, r, d(this), t), t)
      }) : this.each(function () {
        var t, e, f, o;
        if (u === "string")
          for (e = 0, f = i(this), o = n.match(h) || []; t = o[e++];) f.hasClass(t) ? f.removeClass(t) : f.addClass(t);
        else(n === undefined || u === "boolean") && (t = d(this), t && r.set(this, "__className__", t), this.setAttribute && this.setAttribute("class", t || n === !1 ? "" : r.get(this, "__className__") || ""))
      })
    },
    hasClass: function (n) {
      for (var t, r = 0, i = " " + n + " "; t = this[r++];)
        if (t.nodeType === 1 && (" " + k(d(t)) + " ").indexOf(i) > -1) return !0;
      return !1
    }
  });
  ff = /\r/g;
  i.fn.extend({
    val: function (n) {
      var t, r, f, u = this[0];
      return arguments.length ? (f = i.isFunction(n), this.each(function (r) {
        var u;
        this.nodeType === 1 && (u = f ? n.call(this, r, i(this).val()) : n, u == null ? u = "" : typeof u == "number" ? u += "" : Array.isArray(u) && (u = i.map(u, function (n) {
          return n == null ? "" : n + ""
        })), t = i.valHooks[this.type] || i.valHooks[this.nodeName.toLowerCase()], t && "set" in t && t.set(this, u, "value") !== undefined || (this.value = u))
      })) : u ? (t = i.valHooks[u.type] || i.valHooks[u.nodeName.toLowerCase()], t && "get" in t && (r = t.get(u, "value")) !== undefined) ? r : (r = u.value, typeof r == "string") ? r.replace(ff, "") : r == null ? "" : r : void 0
    }
  });
  i.extend({
    valHooks: {
      option: {
        get: function (n) {
          var t = i.find.attr(n, "value");
          return t != null ? t : k(i.text(n))
        }
      },
      select: {
        get: function (n) {
          for (var e, t, o = n.options, u = n.selectedIndex, f = n.type === "select-one", s = f ? null : [], h = f ? u + 1 : o.length, r = u < 0 ? h : f ? u : 0; r < h; r++)
            if (t = o[r], (t.selected || r === u) && !t.disabled && (!t.parentNode.disabled || !l(t.parentNode, "optgroup"))) {
              if (e = i(t).val(), f) return e;
              s.push(e)
            } return s
        },
        set: function (n, t) {
          for (var u, r, f = n.options, e = i.makeArray(t), o = f.length; o--;) r = f[o], (r.selected = i.inArray(i.valHooks.option.get(r), e) > -1) && (u = !0);
          return u || (n.selectedIndex = -1), e
        }
      }
    }
  });
  i.each(["radio", "checkbox"], function () {
    i.valHooks[this] = {
      set: function (n, t) {
        if (Array.isArray(t)) return n.checked = i.inArray(i(n).val(), t) > -1
      }
    };
    f.checkOn || (i.valHooks[this].get = function (n) {
      return n.getAttribute("value") === null ? "on" : n.value
    })
  });
  vi = /^(?:focusinfocus|focusoutblur)$/;
  i.extend(i.event, {
    trigger: function (t, f, e, o) {
      var w, s, c, b, a, v, l, p = [e || u],
        h = yt.call(t, "type") ? t.type : t,
        y = yt.call(t, "namespace") ? t.namespace.split(".") : [];
      if ((s = c = e = e || u, e.nodeType !== 3 && e.nodeType !== 8) && !vi.test(h + i.event.triggered) && (h.indexOf(".") > -1 && (y = h.split("."), h = y.shift(), y.sort()), a = h.indexOf(":") < 0 && "on" + h, t = t[i.expando] ? t : new i.Event(h, typeof t == "object" && t), t.isTrigger = o ? 2 : 3, t.namespace = y.join("."), t.rnamespace = t.namespace ? new RegExp("(^|\\.)" + y.join("\\.(?:.*\\.|)") + "(\\.|$)") : null, t.result = undefined, t.target || (t.target = e), f = f == null ? [t] : i.makeArray(f, [t]), l = i.event.special[h] || {}, o || !l.trigger || l.trigger.apply(e, f) !== !1)) {
        if (!o && !l.noBubble && !i.isWindow(e)) {
          for (b = l.delegateType || h, vi.test(b + h) || (s = s.parentNode); s; s = s.parentNode) p.push(s), c = s;
          c === (e.ownerDocument || u) && p.push(c.defaultView || c.parentWindow || n)
        }
        for (w = 0;
          (s = p[w++]) && !t.isPropagationStopped();) t.type = w > 1 ? b : l.bindType || h, v = (r.get(s, "events") || {})[t.type] && r.get(s, "handle"), v && v.apply(s, f), v = a && s[a], v && v.apply && st(s) && (t.result = v.apply(s, f), t.result === !1 && t.preventDefault());
        return t.type = h, o || t.isDefaultPrevented() || (!l._default || l._default.apply(p.pop(), f) === !1) && st(e) && a && i.isFunction(e[h]) && !i.isWindow(e) && (c = e[a], c && (e[a] = null), i.event.triggered = h, e[h](), i.event.triggered = undefined, c && (e[a] = c)), t.result
      }
    },
    simulate: function (n, t, r) {
      var u = i.extend(new i.Event, r, {
        type: n,
        isSimulated: !0
      });
      i.event.trigger(u, null, t)
    }
  });
  i.fn.extend({
    trigger: function (n, t) {
      return this.each(function () {
        i.event.trigger(n, t, this)
      })
    },
    triggerHandler: function (n, t) {
      var r = this[0];
      if (r) return i.event.trigger(n, t, r, !0)
    }
  });
  i.each("blur focus focusin focusout resize scroll click dblclick mousedown mouseup mousemove mouseover mouseout mouseenter mouseleave change select submit keydown keypress keyup contextmenu".split(" "), function (n, t) {
    i.fn[t] = function (n, i) {
      return arguments.length > 0 ? this.on(t, null, n, i) : this.trigger(t)
    }
  });
  i.fn.extend({
    hover: function (n, t) {
      return this.mouseenter(n).mouseleave(t || n)
    }
  });
  f.focusin = "onfocusin" in n;
  f.focusin || i.each({
    focus: "focusin",
    blur: "focusout"
  }, function (n, t) {
    var u = function (n) {
      i.event.simulate(t, n.target, i.event.fix(n))
    };
    i.event.special[t] = {
      setup: function () {
        var i = this.ownerDocument || this,
          f = r.access(i, t);
        f || i.addEventListener(n, u, !0);
        r.access(i, t, (f || 0) + 1)
      },
      teardown: function () {
        var i = this.ownerDocument || this,
          f = r.access(i, t) - 1;
        f ? r.access(i, t, f) : (i.removeEventListener(n, u, !0), r.remove(i, t))
      }
    }
  });
  var at = n.location,
    ef = i.now(),
    yi = /\?/;
  i.parseXML = function (t) {
    var r;
    if (!t || typeof t != "string") return null;
    try {
      r = (new n.DOMParser).parseFromString(t, "text/xml")
    } catch (u) {
      r = undefined
    }
    return (!r || r.getElementsByTagName("parsererror").length) && i.error("Invalid XML: " + t), r
  };
  var ge = /\[\]$/,
    of = /\r?\n/g,
    no = /^(?:submit|button|image|reset|file)$/i,
    to = /^(?:input|select|textarea|keygen)/i;
  i.param = function (n, t) {
    var r, u = [],
      f = function (n, t) {
        var r = i.isFunction(t) ? t() : t;
        u[u.length] = encodeURIComponent(n) + "=" + encodeURIComponent(r == null ? "" : r)
      };
    if (Array.isArray(n) || n.jquery && !i.isPlainObject(n)) i.each(n, function () {
      f(this.name, this.value)
    });
    else
      for (r in n) pi(r, n[r], t, f);
    return u.join("&")
  };
  i.fn.extend({
    serialize: function () {
      return i.param(this.serializeArray())
    },
    serializeArray: function () {
      return this.map(function () {
        var n = i.prop(this, "elements");
        return n ? i.makeArray(n) : this
      }).filter(function () {
        var n = this.type;
        return this.name && !i(this).is(":disabled") && to.test(this.nodeName) && !no.test(n) && (this.checked || !dr.test(n))
      }).map(function (n, t) {
        var r = i(this).val();
        return r == null ? null : Array.isArray(r) ? i.map(r, function (n) {
          return {
            name: t.name,
            value: n.replace( of , "\r\n")
          }
        }) : {
          name: t.name,
          value: r.replace( of , "\r\n")
        }
      }).get()
    }
  });
  var io = /%20/g,
    ro = /#.*$/,
    uo = /([?&])_=[^&]*/,
    fo = /^(.*?):[ \t]*([^\r\n]*)$/mg,
    eo = /^(?:GET|HEAD)$/,
    oo = /^\/\//,
    sf = {},
    wi = {},
    hf = "*/".concat("*"),
    bi = u.createElement("a");
  return bi.href = at.href, i.extend({
    active: 0,
    lastModified: {},
    etag: {},
    ajaxSettings: {
      url: at.href,
      type: "GET",
      isLocal: /^(?:about|app|app-storage|.+-extension|file|res|widget):$/.test(at.protocol),
      global: !0,
      processData: !0,
      async: !0,
      contentType: "application/x-www-form-urlencoded; charset=UTF-8",
      accepts: {
        "*": hf,
        text: "text/plain",
        html: "text/html",
        xml: "application/xml, text/xml",
        json: "application/json, text/javascript"
      },
      contents: {
        xml: /\bxml\b/,
        html: /\bhtml/,
        json: /\bjson\b/
      },
      responseFields: {
        xml: "responseXML",
        text: "responseText",
        json: "responseJSON"
      },
      converters: {
        "* text": String,
        "text html": !0,
        "text json": JSON.parse,
        "text xml": i.parseXML
      },
      flatOptions: {
        url: !0,
        context: !0
      }
    },
    ajaxSetup: function (n, t) {
      return t ? ki(ki(n, i.ajaxSettings), t) : ki(i.ajaxSettings, n)
    },
    ajaxPrefilter: cf(sf),
    ajaxTransport: cf(wi),
    ajax: function (t, r) {
      function b(t, r, u, h) {
        var y, rt, g, p, b, a = r;
        s || (s = !0, d && n.clearTimeout(d), l = undefined, k = h || "", e.readyState = t > 0 ? 4 : 0, y = t >= 200 && t < 300 || t === 304, u && (p = so(f, e, u)), p = ho(f, p, e, y), y ? (f.ifModified && (b = e.getResponseHeader("Last-Modified"), b && (i.lastModified[o] = b), b = e.getResponseHeader("etag"), b && (i.etag[o] = b)), t === 204 || f.type === "HEAD" ? a = "nocontent" : t === 304 ? a = "notmodified" : (a = p.state, rt = p.data, g = p.error, y = !g)) : (g = a, (t || !a) && (a = "error", t < 0 && (t = 0))), e.status = t, e.statusText = (r || a) + "", y ? tt.resolveWith(c, [rt, a, e]) : tt.rejectWith(c, [e, a, g]), e.statusCode(w), w = undefined, v && nt.trigger(y ? "ajaxSuccess" : "ajaxError", [e, f, y ? rt : g]), it.fireWith(c, [e, a]), v && (nt.trigger("ajaxComplete", [e, f]), --i.active || i.event.trigger("ajaxStop")))
      }
      typeof t == "object" && (r = t, t = undefined);
      r = r || {};
      var l, o, k, y, d, a, s, v, g, p, f = i.ajaxSetup({}, r),
        c = f.context || f,
        nt = f.context && (c.nodeType || c.jquery) ? i(c) : i.event,
        tt = i.Deferred(),
        it = i.Callbacks("once memory"),
        w = f.statusCode || {},
        rt = {},
        ut = {},
        ft = "canceled",
        e = {
          readyState: 0,
          getResponseHeader: function (n) {
            var t;
            if (s) {
              if (!y)
                for (y = {}; t = fo.exec(k);) y[t[1].toLowerCase()] = t[2];
              t = y[n.toLowerCase()]
            }
            return t == null ? null : t
          },
          getAllResponseHeaders: function () {
            return s ? k : null
          },
          setRequestHeader: function (n, t) {
            return s == null && (n = ut[n.toLowerCase()] = ut[n.toLowerCase()] || n, rt[n] = t), this
          },
          overrideMimeType: function (n) {
            return s == null && (f.mimeType = n), this
          },
          statusCode: function (n) {
            var t;
            if (n)
              if (s) e.always(n[e.status]);
              else
                for (t in n) w[t] = [w[t], n[t]];
            return this
          },
          abort: function (n) {
            var t = n || ft;
            return l && l.abort(t), b(0, t), this
          }
        };
      if (tt.promise(e), f.url = ((t || f.url || at.href) + "").replace(oo, at.protocol + "//"), f.type = r.method || r.type || f.method || f.type, f.dataTypes = (f.dataType || "*").toLowerCase().match(h) || [""], f.crossDomain == null) {
        a = u.createElement("a");
        try {
          a.href = f.url;
          a.href = a.href;
          f.crossDomain = bi.protocol + "//" + bi.host != a.protocol + "//" + a.host
        } catch (et) {
          f.crossDomain = !0
        }
      }
      if (f.data && f.processData && typeof f.data != "string" && (f.data = i.param(f.data, f.traditional)), lf(sf, f, r, e), s) return e;
      v = i.event && f.global;
      v && i.active++ == 0 && i.event.trigger("ajaxStart");
      f.type = f.type.toUpperCase();
      f.hasContent = !eo.test(f.type);
      o = f.url.replace(ro, "");
      f.hasContent ? f.data && f.processData && (f.contentType || "").indexOf("application/x-www-form-urlencoded") === 0 && (f.data = f.data.replace(io, "+")) : (p = f.url.slice(o.length), f.data && (o += (yi.test(o) ? "&" : "?") + f.data, delete f.data), f.cache === !1 && (o = o.replace(uo, "$1"), p = (yi.test(o) ? "&" : "?") + "_=" + ef++ + p), f.url = o + p);
      f.ifModified && (i.lastModified[o] && e.setRequestHeader("If-Modified-Since", i.lastModified[o]), i.etag[o] && e.setRequestHeader("If-None-Match", i.etag[o]));
      (f.data && f.hasContent && f.contentType !== !1 || r.contentType) && e.setRequestHeader("Content-Type", f.contentType);
      e.setRequestHeader("Accept", f.dataTypes[0] && f.accepts[f.dataTypes[0]] ? f.accepts[f.dataTypes[0]] + (f.dataTypes[0] !== "*" ? ", " + hf + "; q=0.01" : "") : f.accepts["*"]);
      for (g in f.headers) e.setRequestHeader(g, f.headers[g]);
      if (f.beforeSend && (f.beforeSend.call(c, e, f) === !1 || s)) return e.abort();
      if (ft = "abort", it.add(f.complete), e.done(f.success), e.fail(f.error), l = lf(wi, f, r, e), l) {
        if (e.readyState = 1, v && nt.trigger("ajaxSend", [e, f]), s) return e;
        f.async && f.timeout > 0 && (d = n.setTimeout(function () {
          e.abort("timeout")
        }, f.timeout));
        try {
          s = !1;
          l.send(rt, b)
        } catch (et) {
          if (s) throw et;
          b(-1, et)
        }
      } else b(-1, "No Transport");
      return e
    },
    getJSON: function (n, t, r) {
      return i.get(n, t, r, "json")
    },
    getScript: function (n, t) {
      return i.get(n, undefined, t, "script")
    }
  }), i.each(["get", "post"], function (n, t) {
    i[t] = function (n, r, u, f) {
      return i.isFunction(r) && (f = f || u, u = r, r = undefined), i.ajax(i.extend({
        url: n,
        type: t,
        dataType: f,
        data: r,
        success: u
      }, i.isPlainObject(n) && n))
    }
  }), i._evalUrl = function (n) {
    return i.ajax({
      url: n,
      type: "GET",
      dataType: "script",
      cache: !0,
      async: !1,
      global: !1,
      throws: !0
    })
  }, i.fn.extend({
    wrapAll: function (n) {
      var t;
      return this[0] && (i.isFunction(n) && (n = n.call(this[0])), t = i(n, this[0].ownerDocument).eq(0).clone(!0), this[0].parentNode && t.insertBefore(this[0]), t.map(function () {
        for (var n = this; n.firstElementChild;) n = n.firstElementChild;
        return n
      }).append(this)), this
    },
    wrapInner: function (n) {
      return i.isFunction(n) ? this.each(function (t) {
        i(this).wrapInner(n.call(this, t))
      }) : this.each(function () {
        var t = i(this),
          r = t.contents();
        r.length ? r.wrapAll(n) : t.append(n)
      })
    },
    wrap: function (n) {
      var t = i.isFunction(n);
      return this.each(function (r) {
        i(this).wrapAll(t ? n.call(this, r) : n)
      })
    },
    unwrap: function (n) {
      return this.parent(n).not("body").each(function () {
        i(this).replaceWith(this.childNodes)
      }), this
    }
  }), i.expr.pseudos.hidden = function (n) {
    return !i.expr.pseudos.visible(n)
  }, i.expr.pseudos.visible = function (n) {
    return !!(n.offsetWidth || n.offsetHeight || n.getClientRects().length)
  }, i.ajaxSettings.xhr = function () {
    try {
      return new n.XMLHttpRequest
    } catch (t) {}
  }, af = {
    0: 200,
    1223: 204
  }, et = i.ajaxSettings.xhr(), f.cors = !!et && "withCredentials" in et, f.ajax = et = !!et, i.ajaxTransport(function (t) {
    var i, r;
    if (f.cors || et && !t.crossDomain) return {
      send: function (u, f) {
        var o, e = t.xhr();
        if (e.open(t.type, t.url, t.async, t.username, t.password), t.xhrFields)
          for (o in t.xhrFields) e[o] = t.xhrFields[o];
        t.mimeType && e.overrideMimeType && e.overrideMimeType(t.mimeType);
        t.crossDomain || u["X-Requested-With"] || (u["X-Requested-With"] = "XMLHttpRequest");
        for (o in u) e.setRequestHeader(o, u[o]);
        i = function (n) {
          return function () {
            i && (i = r = e.onload = e.onerror = e.onabort = e.onreadystatechange = null, n === "abort" ? e.abort() : n === "error" ? typeof e.status != "number" ? f(0, "error") : f(e.status, e.statusText) : f(af[e.status] || e.status, e.statusText, (e.responseType || "text") !== "text" || typeof e.responseText != "string" ? {
              binary: e.response
            } : {
              text: e.responseText
            }, e.getAllResponseHeaders()))
          }
        };
        e.onload = i();
        r = e.onerror = i("error");
        e.onabort !== undefined ? e.onabort = r : e.onreadystatechange = function () {
          e.readyState === 4 && n.setTimeout(function () {
            i && r()
          })
        };
        i = i("abort");
        try {
          e.send(t.hasContent && t.data || null)
        } catch (s) {
          if (i) throw s;
        }
      },
      abort: function () {
        i && i()
      }
    }
  }), i.ajaxPrefilter(function (n) {
    n.crossDomain && (n.contents.script = !1)
  }), i.ajaxSetup({
    accepts: {
      script: "text/javascript, application/javascript, application/ecmascript, application/x-ecmascript"
    },
    contents: {
      script: /\b(?:java|ecma)script\b/
    },
    converters: {
      "text script": function (n) {
        return i.globalEval(n), n
      }
    }
  }), i.ajaxPrefilter("script", function (n) {
    n.cache === undefined && (n.cache = !1);
    n.crossDomain && (n.type = "GET")
  }), i.ajaxTransport("script", function (n) {
    if (n.crossDomain) {
      var r, t;
      return {
        send: function (f, e) {
          r = i("<script>").prop({
            charset: n.scriptCharset,
            src: n.url
          }).on("load error", t = function (n) {
            r.remove();
            t = null;
            n && e(n.type === "error" ? 404 : 200, n.type)
          });
          u.head.appendChild(r[0])
        },
        abort: function () {
          t && t()
        }
      }
    }
  }), di = [], ri = /(=)\?(?=&|$)|\?\?/, i.ajaxSetup({
    jsonp: "callback",
    jsonpCallback: function () {
      var n = di.pop() || i.expando + "_" + ef++;
      return this[n] = !0, n
    }
  }), i.ajaxPrefilter("json jsonp", function (t, r, u) {
    var f, e, o, s = t.jsonp !== !1 && (ri.test(t.url) ? "url" : typeof t.data == "string" && (t.contentType || "").indexOf("application/x-www-form-urlencoded") === 0 && ri.test(t.data) && "data");
    if (s || t.dataTypes[0] === "jsonp") return f = t.jsonpCallback = i.isFunction(t.jsonpCallback) ? t.jsonpCallback() : t.jsonpCallback, s ? t[s] = t[s].replace(ri, "$1" + f) : t.jsonp !== !1 && (t.url += (yi.test(t.url) ? "&" : "?") + t.jsonp + "=" + f), t.converters["script json"] = function () {
      return o || i.error(f + " was not called"), o[0]
    }, t.dataTypes[0] = "json", e = n[f], n[f] = function () {
      o = arguments
    }, u.always(function () {
      e === undefined ? i(n).removeProp(f) : n[f] = e;
      t[f] && (t.jsonpCallback = r.jsonpCallback, di.push(f));
      o && i.isFunction(e) && e(o[0]);
      o = e = undefined
    }), "script"
  }), f.createHTMLDocument = function () {
    var n = u.implementation.createHTMLDocument("").body;
    return n.innerHTML = "<form><\/form><form><\/form>", n.childNodes.length === 2
  }(), i.parseHTML = function (n, t, r) {
    if (typeof n != "string") return [];
    typeof t == "boolean" && (r = t, t = !1);
    var s, e, o;
    return (t || (f.createHTMLDocument ? (t = u.implementation.createHTMLDocument(""), s = t.createElement("base"), s.href = u.location.href, t.head.appendChild(s)) : t = u), e = ei.exec(n), o = !r && [], e) ? [t.createElement(e[1])] : (e = iu([n], t, o), o && o.length && i(o).remove(), i.merge([], e.childNodes))
  }, i.fn.load = function (n, t, r) {
    var u, o, s, f = this,
      e = n.indexOf(" ");
    return e > -1 && (u = k(n.slice(e)), n = n.slice(0, e)), i.isFunction(t) ? (r = t, t = undefined) : t && typeof t == "object" && (o = "POST"), f.length > 0 && i.ajax({
      url: n,
      type: o || "GET",
      dataType: "html",
      data: t
    }).done(function (n) {
      s = arguments;
      f.html(u ? i("<div>").append(i.parseHTML(n)).find(u) : n)
    }).always(r && function (n, t) {
      f.each(function () {
        r.apply(this, s || [n.responseText, t, n])
      })
    }), this
  }, i.each(["ajaxStart", "ajaxStop", "ajaxComplete", "ajaxError", "ajaxSuccess", "ajaxSend"], function (n, t) {
    i.fn[t] = function (n) {
      return this.on(t, n)
    }
  }), i.expr.pseudos.animated = function (n) {
    return i.grep(i.timers, function (t) {
      return n === t.elem
    }).length
  }, i.offset = {
    setOffset: function (n, t, r) {
      var e, o, s, h, u, c, v, l = i.css(n, "position"),
        a = i(n),
        f = {};
      l === "static" && (n.style.position = "relative");
      u = a.offset();
      s = i.css(n, "top");
      c = i.css(n, "left");
      v = (l === "absolute" || l === "fixed") && (s + c).indexOf("auto") > -1;
      v ? (e = a.position(), h = e.top, o = e.left) : (h = parseFloat(s) || 0, o = parseFloat(c) || 0);
      i.isFunction(t) && (t = t.call(n, r, i.extend({}, u)));
      t.top != null && (f.top = t.top - u.top + h);
      t.left != null && (f.left = t.left - u.left + o);
      "using" in t ? t.using.call(n, f) : a.css(f)
    }
  }, i.fn.extend({
    offset: function (n) {
      if (arguments.length) return n === undefined ? this : this.each(function (t) {
        i.offset.setOffset(this, n, t)
      });
      var r, u, f, e, t = this[0];
      if (t) return t.getClientRects().length ? (f = t.getBoundingClientRect(), r = t.ownerDocument, u = r.documentElement, e = r.defaultView, {
        top: f.top + e.pageYOffset - u.clientTop,
        left: f.left + e.pageXOffset - u.clientLeft
      }) : {
        top: 0,
        left: 0
      }
    },
    position: function () {
      if (this[0]) {
        var t, r, u = this[0],
          n = {
            top: 0,
            left: 0
          };
        return i.css(u, "position") === "fixed" ? r = u.getBoundingClientRect() : (t = this.offsetParent(), r = this.offset(), l(t[0], "html") || (n = t.offset()), n = {
          top: n.top + i.css(t[0], "borderTopWidth", !0),
          left: n.left + i.css(t[0], "borderLeftWidth", !0)
        }), {
          top: r.top - n.top - i.css(u, "marginTop", !0),
          left: r.left - n.left - i.css(u, "marginLeft", !0)
        }
      }
    },
    offsetParent: function () {
      return this.map(function () {
        for (var n = this.offsetParent; n && i.css(n, "position") === "static";) n = n.offsetParent;
        return n || dt
      })
    }
  }), i.each({
    scrollLeft: "pageXOffset",
    scrollTop: "pageYOffset"
  }, function (n, t) {
    var r = "pageYOffset" === t;
    i.fn[n] = function (u) {
      return v(this, function (n, u, f) {
        var e;
        if (i.isWindow(n) ? e = n : n.nodeType === 9 && (e = n.defaultView), f === undefined) return e ? e[t] : n[u];
        e ? e.scrollTo(r ? e.pageXOffset : f, r ? f : e.pageYOffset) : n[u] = f
      }, n, u, arguments.length)
    }
  }), i.each(["top", "left"], function (n, t) {
    i.cssHooks[t] = hu(f.pixelPosition, function (n, r) {
      if (r) return r = lt(n, t), li.test(r) ? i(n).position()[t] + "px" : r
    })
  }), i.each({
    Height: "height",
    Width: "width"
  }, function (n, t) {
    i.each({
      padding: "inner" + n,
      content: t,
      "": "outer" + n
    }, function (r, u) {
      i.fn[u] = function (f, e) {
        var o = arguments.length && (r || typeof f != "boolean"),
          s = r || (f === !0 || e === !0 ? "margin" : "border");
        return v(this, function (t, r, f) {
          var e;
          return i.isWindow(t) ? u.indexOf("outer") === 0 ? t["inner" + n] : t.document.documentElement["client" + n] : t.nodeType === 9 ? (e = t.documentElement, Math.max(t.body["scroll" + n], e["scroll" + n], t.body["offset" + n], e["offset" + n], e["client" + n])) : f === undefined ? i.css(t, r, s) : i.style(t, r, f, s)
        }, t, o ? f : undefined, o)
      }
    })
  }), i.fn.extend({
    bind: function (n, t, i) {
      return this.on(n, null, t, i)
    },
    unbind: function (n, t) {
      return this.off(n, null, t)
    },
    delegate: function (n, t, i, r) {
      return this.on(t, n, i, r)
    },
    undelegate: function (n, t, i) {
      return arguments.length === 1 ? this.off(n, "**") : this.off(t, n || "**", i)
    }
  }), i.holdReady = function (n) {
    n ? i.readyWait++ : i.ready(!0)
  }, i.isArray = Array.isArray, i.parseJSON = JSON.parse, i.nodeName = l, typeof define == "function" && define.amd && define("jquery", [], function () {
    return i
  }), vf = n.jQuery, yf = n.$, i.noConflict = function (t) {
    return n.$ === i && (n.$ = yf), t && n.jQuery === i && (n.jQuery = vf), i
  }, t || (n.jQuery = n.$ = i), i
});
/**!
 * @fileOverview Kickass library to create and place poppers near their reference elements.
 * @version 1.11.1
 * @license
 * Copyright (c) 2016 Federico Zivolo and contributors
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
(function (n, t) {
  typeof exports == "object" && typeof module != "undefined" ? module.exports = t() : typeof define == "function" && define.amd ? define(t) : n.Popper = t()
})(this, function () {
  "use strict";

  function ui(n) {
    var t = !1,
      i = 0,
      r = document.createElement("span"),
      u = new MutationObserver(function () {
        n();
        t = !1
      });
    return u.observe(r, {
        attributes: !0
      }),
      function () {
        t || (t = !0, r.setAttribute("x-index", i), i = i + 1)
      }
  }

  function fi(n) {
    var t = !1;
    return function () {
      t || (t = !0, setTimeout(function () {
        t = !1;
        n()
      }, ft))
    }
  }

  function st(n) {
    return n && {}.toString.call(n) === "[object Function]"
  }

  function u(n, t) {
    if (n.nodeType !== 1) return [];
    var i = window.getComputedStyle(n, null);
    return t ? i[t] : i
  }

  function w(n) {
    return n.nodeName === "HTML" ? n : n.parentNode || n.host
  }

  function f(n) {
    if (!n || ["HTML", "BODY", "#document"].indexOf(n.nodeName) !== -1) return window.document.body;
    var t = u(n),
      i = t.overflow,
      r = t.overflowX,
      e = t.overflowY;
    return /(auto|scroll)/.test(i + e + r) ? n : f(w(n))
  }

  function i(n) {
    var t = n && n.offsetParent,
      r = t && t.nodeName;
    return !r || r === "BODY" || r === "HTML" ? window.document.documentElement : ["TD", "TABLE"].indexOf(t.nodeName) !== -1 && u(t, "position") === "static" ? i(t) : t
  }

  function ei(n) {
    var t = n.nodeName;
    return t === "BODY" ? !1 : t === "HTML" || i(n.firstElementChild) === n
  }

  function b(n) {
    return n.parentNode !== null ? b(n.parentNode) : n
  }

  function s(n, t) {
    var r, f;
    if (!n || !n.nodeType || !t || !t.nodeType) return window.document.documentElement;
    var e = n.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING,
      o = e ? n : t,
      h = e ? t : n,
      u = document.createRange();
    return (u.setStart(o, 0), u.setEnd(h, 0), r = u.commonAncestorContainer, n !== r && t !== r || o.contains(h)) ? ei(r) ? r : i(r) : (f = b(n), f.host ? s(f.host, t) : s(n, b(t).host))
  }

  function r(n) {
    var f = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : "top",
      t = f === "top" ? "scrollTop" : "scrollLeft",
      i = n.nodeName,
      r, u;
    return i === "BODY" || i === "HTML" ? (r = window.document.documentElement, u = window.document.scrollingElement || r, u[t]) : n[t]
  }

  function oi(n, t) {
    var e = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : !1,
      u = r(t, "top"),
      f = r(t, "left"),
      i = e ? -1 : 1;
    return n.top += u * i, n.bottom += u * i, n.left += f * i, n.right += f * i, n
  }

  function ht(n, t) {
    var i = t === "x" ? "Left" : "Top",
      r = i === "Left" ? "Right" : "Bottom";
    return +n["border" + i + "Width"].split("px")[0] + +n["border" + r + "Width"].split("px")[0]
  }

  function ct(n, t, i, r) {
    return Math.max(t["offset" + n], i["client" + n], i["offset" + n], e() ? i["offset" + n] + r["margin" + (n === "Height" ? "Top" : "Left")] + r["margin" + (n === "Height" ? "Bottom" : "Right")] : 0)
  }

  function lt() {
    var t = window.document.body,
      n = window.document.documentElement,
      i = e() && window.getComputedStyle(n);
    return {
      height: ct("Height", t, n, i),
      width: ct("Width", t, n, i)
    }
  }

  function t(t) {
    return n({}, t, {
      right: t.left + t.width,
      bottom: t.top + t.height
    })
  }

  function k(n) {
    var i = {},
      o, s, l;
    if (e()) try {
      i = n.getBoundingClientRect();
      o = r(n, "top");
      s = r(n, "left");
      i.top += o;
      i.left += s;
      i.bottom += o;
      i.right += s
    } catch (p) {} else i = n.getBoundingClientRect();
    var f = {
        left: i.left,
        top: i.top,
        width: i.right - i.left,
        height: i.bottom - i.top
      },
      a = n.nodeName === "HTML" ? lt() : {},
      v = a.width || n.clientWidth || f.right - f.left,
      y = a.height || n.clientHeight || f.bottom - f.top,
      h = n.offsetWidth - v,
      c = n.offsetHeight - y;
    return (h || c) && (l = u(n), h -= ht(l, "x"), c -= ht(l, "y"), f.width -= h, f.height -= c), t(f)
  }

  function d(n, i) {
    var y = e(),
      w = i.nodeName === "HTML",
      o = k(n),
      p = k(i),
      l = f(n),
      s = u(i),
      a = +s.borderTopWidth.split("px")[0],
      v = +s.borderLeftWidth.split("px")[0],
      r = t({
        top: o.top - p.top - a,
        left: o.left - p.left - v,
        width: o.width,
        height: o.height
      }),
      h, c;
    return r.marginTop = 0, r.marginLeft = 0, !y && w && (h = +s.marginTop.split("px")[0], c = +s.marginLeft.split("px")[0], r.top -= a - h, r.bottom -= a - h, r.left -= v - c, r.right -= v - c, r.marginTop = h, r.marginLeft = c), (y ? i.contains(l) : i === l && l.nodeName !== "BODY") && (r = oi(r, i)), r
  }

  function ci(n) {
    var i = window.document.documentElement,
      u = d(n, i),
      f = Math.max(i.clientWidth, window.innerWidth || 0),
      e = Math.max(i.clientHeight, window.innerHeight || 0),
      o = r(i),
      s = r(i, "left"),
      h = {
        top: o - u.top + u.marginTop,
        left: s - u.left + u.marginLeft,
        width: f,
        height: e
      };
    return t(h)
  }

  function at(n) {
    var t = n.nodeName;
    return t === "BODY" || t === "HTML" ? !1 : u(n, "position") === "fixed" ? !0 : at(w(n))
  }

  function g(n, t, i, r) {
    var u = {
        top: 0,
        left: 0
      },
      h = s(n, t),
      o, e;
    if (r === "viewport") u = ci(h);
    else if (o = void 0, r === "scrollParent" ? (o = f(w(n)), o.nodeName === "BODY" && (o = window.document.documentElement)) : o = r === "window" ? window.document.documentElement : r, e = d(o, h), o.nodeName !== "HTML" || at(h)) u = e;
    else {
      var c = lt(),
        l = c.height,
        a = c.width;
      u.top += e.top - e.marginTop;
      u.bottom = l + e.top;
      u.left += e.left - e.marginLeft;
      u.right = a + e.left
    }
    return u.left += i, u.top += i, u.right -= i, u.bottom -= i, u
  }

  function li(n) {
    var t = n.width,
      i = n.height;
    return t * i
  }

  function vt(t, i, r, u, f) {
    var l = arguments.length > 5 && arguments[5] !== undefined ? arguments[5] : 0;
    if (t.indexOf("auto") === -1) return t;
    var e = g(r, u, l, f),
      o = {
        top: {
          width: e.width,
          height: i.top - e.top
        },
        right: {
          width: e.right - i.right,
          height: e.height
        },
        bottom: {
          width: e.width,
          height: e.bottom - i.bottom
        },
        left: {
          width: i.left - e.left,
          height: e.height
        }
      },
      s = Object.keys(o).map(function (t) {
        return n({
          key: t
        }, o[t], {
          area: li(o[t])
        })
      }).sort(function (n, t) {
        return t.area - n.area
      }),
      h = s.filter(function (n) {
        var t = n.width,
          i = n.height;
        return t >= r.clientWidth && i >= r.clientHeight
      }),
      a = h.length > 0 ? h[0].key : s[0].key,
      c = t.split("-")[1];
    return a + (c ? "-" + c : "")
  }

  function yt(n, t, i) {
    var r = s(t, i);
    return d(i, r)
  }

  function pt(n) {
    var t = window.getComputedStyle(n),
      i = parseFloat(t.marginTop) + parseFloat(t.marginBottom),
      r = parseFloat(t.marginLeft) + parseFloat(t.marginRight);
    return {
      width: n.offsetWidth + r,
      height: n.offsetHeight + i
    }
  }

  function l(n) {
    var t = {
      left: "right",
      right: "left",
      bottom: "top",
      top: "bottom"
    };
    return n.replace(/left|right|bottom|top/g, function (n) {
      return t[n]
    })
  }

  function wt(n, t, i) {
    i = i.split("-")[0];
    var r = pt(n),
      e = {
        width: r.width,
        height: r.height
      },
      u = ["right", "left"].indexOf(i) !== -1,
      o = u ? "top" : "left",
      f = u ? "left" : "top",
      s = u ? "height" : "width",
      h = u ? "width" : "height";
    return e[o] = t[o] + t[s] / 2 - r[s] / 2, e[f] = i === f ? t[f] - r[h] : t[l(f)], e
  }

  function o(n, t) {
    return Array.prototype.find ? n.find(t) : n.filter(t)[0]
  }

  function ai(n, t, i) {
    if (Array.prototype.findIndex) return n.findIndex(function (n) {
      return n[t] === i
    });
    var r = o(n, function (n) {
      return n[t] === i
    });
    return n.indexOf(r)
  }

  function bt(n, i, r) {
    var u = r === undefined ? n : n.slice(0, ai(n, "name", r));
    return u.forEach(function (n) {
      n.function && console.warn("`modifier.function` is deprecated, use `modifier.fn`!");
      var r = n.function || n.fn;
      n.enabled && st(r) && (i.offsets.popper = t(i.offsets.popper), i.offsets.reference = t(i.offsets.reference), i = r(i, n))
    }), i
  }

  function vi() {
    if (!this.state.isDestroyed) {
      var n = {
        instance: this,
        styles: {},
        attributes: {},
        flipped: !1,
        offsets: {}
      };
      if (n.offsets.reference = yt(this.state, this.popper, this.reference), n.placement = vt(this.options.placement, n.offsets.reference, this.popper, this.reference, this.options.modifiers.flip.boundariesElement, this.options.modifiers.flip.padding), n.originalPlacement = n.placement, n.offsets.popper = wt(this.popper, n.offsets.reference, n.placement), n.offsets.popper.position = "absolute", n = bt(this.modifiers, n), this.state.isCreated) this.options.onUpdate(n);
      else {
        this.state.isCreated = !0;
        this.options.onCreate(n)
      }
    }
  }

  function kt(n, t) {
    return n.some(function (n) {
      var i = n.name,
        r = n.enabled;
      return r && i === t
    })
  }

  function dt(n) {
    for (var i, r, u = [!1, "ms", "Webkit", "Moz", "O"], f = n.charAt(0).toUpperCase() + n.slice(1), t = 0; t < u.length - 1; t++)
      if (i = u[t], r = i ? "" + i + f : n, typeof window.document.body.style[r] != "undefined") return r;
    return null
  }

  function yi() {
    return this.state.isDestroyed = !0, kt(this.modifiers, "applyStyle") && (this.popper.removeAttribute("x-placement"), this.popper.style.left = "", this.popper.style.position = "", this.popper.style.top = "", this.popper.style[dt("transform")] = ""), this.disableEventListeners(), this.options.removeOnDestroy && this.popper.parentNode.removeChild(this.popper), this
  }

  function gt(n, t, i, r) {
    var e = n.nodeName === "BODY",
      u = e ? window : n;
    u.addEventListener(t, i, {
      passive: !0
    });
    e || gt(f(u.parentNode), t, i, r);
    r.push(u)
  }

  function pi(n, t, i, r) {
    i.updateBound = r;
    window.addEventListener("resize", i.updateBound, {
      passive: !0
    });
    var u = f(n);
    return gt(u, "scroll", i.updateBound, i.scrollParents), i.scrollElement = u, i.eventsEnabled = !0, i
  }

  function wi() {
    this.state.eventsEnabled || (this.state = pi(this.reference, this.options, this.state, this.scheduleUpdate))
  }

  function bi(n, t) {
    return window.removeEventListener("resize", t.updateBound), t.scrollParents.forEach(function (n) {
      n.removeEventListener("scroll", t.updateBound)
    }), t.updateBound = null, t.scrollParents = [], t.scrollElement = null, t.eventsEnabled = !1, t
  }

  function ki() {
    this.state.eventsEnabled && (window.cancelAnimationFrame(this.scheduleUpdate), this.state = bi(this.reference, this.state))
  }

  function nt(n) {
    return n !== "" && !isNaN(parseFloat(n)) && isFinite(n)
  }

  function tt(n, t) {
    Object.keys(t).forEach(function (i) {
      var r = "";
      ["width", "height", "top", "right", "bottom", "left"].indexOf(i) !== -1 && nt(t[i]) && (r = "px");
      n.style[i] = t[i] + r
    })
  }

  function di(n, t) {
    Object.keys(t).forEach(function (i) {
      var r = t[i];
      r !== !1 ? n.setAttribute(i, t[i]) : n.removeAttribute(i)
    })
  }

  function gi(n) {
    return tt(n.instance.popper, n.styles), di(n.instance.popper, n.attributes), n.offsets.arrow && tt(n.arrowElement, n.offsets.arrow), n
  }

  function nr(n, t, i, r, u) {
    var f = yt(u, t, n),
      e = vt(i.placement, f, t, n, i.modifiers.flip.boundariesElement, i.modifiers.flip.padding);
    return t.setAttribute("x-placement", e), tt(t, {
      position: "absolute"
    }), i
  }

  function tr(t, r) {
    var d = r.x,
      g = r.y,
      f = t.offsets.popper,
      c = o(t.instance.modifiers, function (n) {
        return n.name === "applyStyle"
      }).gpuAcceleration,
      p, w, b;
    c !== undefined && console.warn("WARNING: `gpuAcceleration` option moved to `computeStyle` modifier and will not be supported in future versions of Popper.js!");
    var nt = c !== undefined ? c : r.gpuAcceleration,
      tt = i(t.instance.popper),
      v = k(tt),
      u = {
        position: f.position
      },
      h = {
        left: Math.floor(f.left),
        top: Math.floor(f.top),
        bottom: Math.floor(f.bottom),
        right: Math.floor(f.right)
      },
      e = d === "bottom" ? "top" : "bottom",
      s = g === "right" ? "left" : "right",
      y = dt("transform"),
      l = void 0,
      a = void 0;
    return a = e === "bottom" ? -v.height + h.bottom : h.top, l = s === "right" ? -v.width + h.right : h.left, nt && y ? (u[y] = "translate3d(" + l + "px, " + a + "px, 0)", u[e] = 0, u[s] = 0, u.willChange = "transform") : (p = e === "bottom" ? -1 : 1, w = s === "right" ? -1 : 1, u[e] = a * p, u[s] = l * w, u.willChange = e + ", " + s), b = {
      "x-placement": t.placement
    }, t.attributes = n({}, b, t.attributes), t.styles = n({}, u, t.styles), t
  }

  function ni(n, t, i) {
    var u = o(n, function (n) {
        var i = n.name;
        return i === t
      }),
      f = !!u && n.some(function (n) {
        return n.name === i && n.enabled && n.order < u.order
      }),
      r, e;
    return f || (r = "`" + t + "`", e = "`" + i + "`", console.warn(e + " modifier is required by " + r + " modifier in order to work, be sure to include it before " + r + "!")), f
  }

  function ir(n, i) {
    var u, v, c;
    if (!ni(n.instance.modifiers, "arrow", "keepTogether")) return n;
    if (u = i.element, typeof u == "string") {
      if (u = n.instance.popper.querySelector(u), !u) return n
    } else if (!n.instance.popper.contains(u)) return console.warn("WARNING: `arrow.element` must be child of its popper element!"), n;
    var y = n.placement.split("-")[0],
      a = n.offsets,
      o = a.popper,
      f = a.reference,
      s = ["left", "right"].indexOf(y) !== -1,
      l = s ? "height" : "width",
      r = s ? "top" : "left",
      p = s ? "left" : "top",
      h = s ? "bottom" : "right",
      e = pt(u)[l];
    return f[h] - e < o[r] && (n.offsets.popper[r] -= o[r] - (f[h] - e)), f[r] + e > o[h] && (n.offsets.popper[r] += f[r] + e - o[h]), v = f[r] + f[l] / 2 - e / 2, c = v - t(n.offsets.popper)[r], c = Math.max(Math.min(o[l] - e, c), 0), n.arrowElement = u, n.offsets.arrow = {}, n.offsets.arrow[r] = Math.round(c), n.offsets.arrow[p] = "", n
  }

  function rr(n) {
    return n === "end" ? "start" : n === "start" ? "end" : n
  }

  function ti(n) {
    var r = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : !1,
      t = a.indexOf(n),
      i = a.slice(t + 1).concat(a.slice(0, t));
    return r ? i.reverse() : i
  }

  function ur(t, i) {
    if (kt(t.instance.modifiers, "inner") || t.flipped && t.placement === t.originalPlacement) return t;
    var e = g(t.instance.popper, t.instance.reference, i.padding, i.boundariesElement),
      r = t.placement.split("-")[0],
      o = l(r),
      u = t.placement.split("-")[1] || "",
      f = [];
    switch (i.behavior) {
      case v.FLIP:
        f = [r, o];
        break;
      case v.CLOCKWISE:
        f = ti(r);
        break;
      case v.COUNTERCLOCKWISE:
        f = ti(r, !0);
        break;
      default:
        f = i.behavior
    }
    return f.forEach(function (s, h) {
      if (r !== s || f.length === h + 1) return t;
      r = t.placement.split("-")[0];
      o = l(r);
      var a = t.offsets.popper,
        v = t.offsets.reference,
        c = Math.floor,
        p = r === "left" && c(a.right) > c(v.left) || r === "right" && c(a.left) < c(v.right) || r === "top" && c(a.bottom) > c(v.top) || r === "bottom" && c(a.top) < c(v.bottom),
        w = c(a.left) < c(e.left),
        b = c(a.right) > c(e.right),
        k = c(a.top) < c(e.top),
        d = c(a.bottom) > c(e.bottom),
        g = r === "left" && w || r === "right" && b || r === "top" && k || r === "bottom" && d,
        y = ["top", "bottom"].indexOf(r) !== -1,
        nt = !!i.flipVariations && (y && u === "start" && w || y && u === "end" && b || !y && u === "start" && k || !y && u === "end" && d);
      (p || g || nt) && (t.flipped = !0, (p || g) && (r = f[h + 1]), nt && (u = rr(u)), t.placement = r + (u ? "-" + u : ""), t.offsets.popper = n({}, t.offsets.popper, wt(t.instance.popper, t.offsets.reference, t.placement)), t = bt(t.instance.modifiers, t, "flip"))
    }), t
  }

  function fr(n) {
    var o = n.offsets,
      u = o.popper,
      i = o.reference,
      s = n.placement.split("-")[0],
      r = Math.floor,
      f = ["top", "bottom"].indexOf(s) !== -1,
      e = f ? "right" : "bottom",
      t = f ? "left" : "top",
      h = f ? "width" : "height";
    return u[e] < r(i[t]) && (n.offsets.popper[t] = r(i[t]) - u[h]), u[t] > r(i[e]) && (n.offsets.popper[t] = r(i[e])), n
  }

  function er(n, i, r, u) {
    var h = n.match(/((?:\-|\+)?\d*\.?\d*)(.*)/),
      e = +h[1],
      f = h[2],
      o, c, s;
    if (!e) return n;
    if (f.indexOf("%") === 0) {
      o = void 0;
      switch (f) {
        case "%p":
          o = r;
          break;
        case "%":
        case "%r":
        default:
          o = u
      }
      return c = t(o), c[i] / 100 * e
    }
    return f === "vh" || f === "vw" ? (s = void 0, s = f === "vh" ? Math.max(document.documentElement.clientHeight, window.innerHeight || 0) : Math.max(document.documentElement.clientWidth, window.innerWidth || 0), s / 100 * e) : e
  }

  function or(n, t, i, r) {
    var h = [0, 0],
      c = ["right", "left"].indexOf(r) !== -1,
      u = n.split(/(\+|\-)/).map(function (n) {
        return n.trim()
      }),
      f = u.indexOf(o(u, function (n) {
        return n.search(/,|\s/) !== -1
      })),
      s, e;
    return u[f] && u[f].indexOf(",") === -1 && console.warn("Offsets separated by white space(s) are deprecated, use a comma (,) instead."), s = /\s*,\s*|\s+/, e = f !== -1 ? [u.slice(0, f).concat([u[f].split(s)[0]]), [u[f].split(s)[1]].concat(u.slice(f + 1))] : [u], e = e.map(function (n, r) {
      var f = (r === 1 ? !c : c) ? "height" : "width",
        u = !1;
      return n.reduce(function (n, t) {
        return n[n.length - 1] === "" && ["+", "-"].indexOf(t) !== -1 ? (n[n.length - 1] = t, u = !0, n) : u ? (n[n.length - 1] += t, u = !1, n) : n.concat(t)
      }, []).map(function (n) {
        return er(n, f, t, i)
      })
    }), e.forEach(function (n, t) {
      n.forEach(function (i, r) {
        nt(i) && (h[t] += i * (n[r - 1] === "-" ? -1 : 1))
      })
    }), h
  }

  function sr(n, t) {
    var f = t.offset,
      o = n.placement,
      e = n.offsets,
      i = e.popper,
      s = e.reference,
      u = o.split("-")[0],
      r = void 0;
    return r = nt(+f) ? [+f, 0] : or(f, i, s, u), u === "left" ? (i.top += r[0], i.left -= r[1]) : u === "right" ? (i.top += r[0], i.left += r[1]) : u === "top" ? (i.left += r[0], i.top -= r[1]) : u === "bottom" && (i.left += r[0], i.top += r[1]), n.popper = i, n
  }

  function hr(t, r) {
    var e = r.boundariesElement || i(t.instance.popper),
      f;
    t.instance.reference === e && (e = i(e));
    f = g(t.instance.popper, t.instance.reference, r.padding, e);
    r.boundaries = f;
    var o = r.priority,
      u = t.offsets.popper,
      s = {
        primary: function (n) {
          var t = u[n];
          return u[n] < f[n] && !r.escapeWithReference && (t = Math.max(u[n], f[n])), c({}, n, t)
        },
        secondary: function (n) {
          var t = n === "right" ? "left" : "top",
            i = u[t];
          return u[n] > f[n] && !r.escapeWithReference && (i = Math.min(u[t], f[n] - (n === "right" ? u.width : u.height))), c({}, t, i)
        }
      };
    return o.forEach(function (t) {
      var i = ["left", "top"].indexOf(t) !== -1 ? "primary" : "secondary";
      u = n({}, u, s[i](t))
    }), t.offsets.popper = u, t
  }

  function cr(t) {
    var u = t.placement,
      l = u.split("-")[0],
      f = u.split("-")[1];
    if (f) {
      var e = t.offsets,
        r = e.reference,
        o = e.popper,
        s = ["bottom", "top"].indexOf(l) !== -1,
        i = s ? "left" : "top",
        h = s ? "width" : "height",
        a = {
          start: c({}, i, r[i]),
          end: c({}, i, r[i] + r[h] - o[h])
        };
      t.offsets.popper = n({}, o, a[f])
    }
    return t
  }

  function lr(n) {
    if (!ni(n.instance.modifiers, "hide", "preventOverflow")) return n;
    var t = n.offsets.reference,
      i = o(n.instance.modifiers, function (n) {
        return n.name === "preventOverflow"
      }).boundaries;
    if (t.bottom < i.top || t.left > i.right || t.top > i.bottom || t.right < i.left) {
      if (n.hide === !0) return n;
      n.hide = !0;
      n.attributes["x-out-of-boundaries"] = ""
    } else {
      if (n.hide === !1) return n;
      n.hide = !1;
      n.attributes["x-out-of-boundaries"] = !1
    }
    return n
  }

  function ar(n) {
    var i = n.placement,
      u = i.split("-")[0],
      f = n.offsets,
      r = f.popper,
      o = f.reference,
      e = ["left", "right"].indexOf(u) !== -1,
      s = ["top", "left"].indexOf(u) === -1;
    return r[e ? "left" : "top"] = o[i] - (s ? r[e ? "width" : "height"] : 0), n.placement = l(i), n.offsets.popper = t(r), n
  }
  for (var et, ot, h, e, it, a, v, ii = ["native code", "[object MutationObserverConstructor]"], ri = function (n) {
      return ii.some(function (t) {
        return (n || "").toString().indexOf(t) > -1
      })
    }, rt = typeof window != "undefined", ut = ["Edge", "Trident", "Firefox"], ft = 0, p = 0; p < ut.length; p += 1)
    if (rt && navigator.userAgent.indexOf(ut[p]) >= 0) {
      ft = 1;
      break
    } et = rt && ri(window.MutationObserver);
  ot = et ? ui : fi;
  h = undefined;
  e = function () {
    return h === undefined && (h = navigator.appVersion.indexOf("MSIE 10") !== -1), h
  };
  var si = function (n, t) {
      if (!(n instanceof t)) throw new TypeError("Cannot call a class as a function");
    },
    hi = function () {
      function n(n, t) {
        for (var i, r = 0; r < t.length; r++) i = t[r], i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(n, i.key, i)
      }
      return function (t, i, r) {
        return i && n(t.prototype, i), r && n(t, r), t
      }
    }(),
    c = function (n, t, i) {
      return t in n ? Object.defineProperty(n, t, {
        value: i,
        enumerable: !0,
        configurable: !0,
        writable: !0
      }) : n[t] = i, n
    },
    n = Object.assign || function (n) {
      for (var i, r, t = 1; t < arguments.length; t++) {
        i = arguments[t];
        for (r in i) Object.prototype.hasOwnProperty.call(i, r) && (n[r] = i[r])
      }
      return n
    };
  it = ["auto-start", "auto", "auto-end", "top-start", "top", "top-end", "right-start", "right", "right-end", "bottom-end", "bottom", "bottom-start", "left-end", "left", "left-start"];
  a = it.slice(3);
  v = {
    FLIP: "flip",
    CLOCKWISE: "clockwise",
    COUNTERCLOCKWISE: "counterclockwise"
  };
  var vr = {
      shift: {
        order: 100,
        enabled: !0,
        fn: cr
      },
      offset: {
        order: 200,
        enabled: !0,
        fn: sr,
        offset: 0
      },
      preventOverflow: {
        order: 300,
        enabled: !0,
        fn: hr,
        priority: ["left", "right", "top", "bottom"],
        padding: 5,
        boundariesElement: "scrollParent"
      },
      keepTogether: {
        order: 400,
        enabled: !0,
        fn: fr
      },
      arrow: {
        order: 500,
        enabled: !0,
        fn: ir,
        element: "[x-arrow]"
      },
      flip: {
        order: 600,
        enabled: !0,
        fn: ur,
        behavior: "flip",
        padding: 5,
        boundariesElement: "viewport"
      },
      inner: {
        order: 700,
        enabled: !1,
        fn: ar
      },
      hide: {
        order: 800,
        enabled: !0,
        fn: lr
      },
      computeStyle: {
        order: 850,
        enabled: !0,
        fn: tr,
        gpuAcceleration: !0,
        x: "bottom",
        y: "right"
      },
      applyStyle: {
        order: 900,
        enabled: !0,
        fn: gi,
        onLoad: nr,
        gpuAcceleration: undefined
      }
    },
    yr = {
      placement: "bottom",
      eventsEnabled: !0,
      removeOnDestroy: !1,
      onCreate: function () {},
      onUpdate: function () {},
      modifiers: vr
    },
    y = function () {
      function t(i, r) {
        var u = this,
          f = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {},
          e;
        si(this, t);
        this.scheduleUpdate = function () {
          return requestAnimationFrame(u.update)
        };
        this.update = ot(this.update.bind(this));
        this.options = n({}, t.Defaults, f);
        this.state = {
          isDestroyed: !1,
          isCreated: !1,
          scrollParents: []
        };
        this.reference = i.jquery ? i[0] : i;
        this.popper = r.jquery ? r[0] : r;
        this.options.modifiers = {};
        Object.keys(n({}, t.Defaults.modifiers, f.modifiers)).forEach(function (i) {
          u.options.modifiers[i] = n({}, t.Defaults.modifiers[i] || {}, f.modifiers ? f.modifiers[i] : {})
        });
        this.modifiers = Object.keys(this.options.modifiers).map(function (t) {
          return n({
            name: t
          }, u.options.modifiers[t])
        }).sort(function (n, t) {
          return n.order - t.order
        });
        this.modifiers.forEach(function (n) {
          if (n.enabled && st(n.onLoad)) n.onLoad(u.reference, u.popper, u.options, n, u.state)
        });
        this.update();
        e = this.options.eventsEnabled;
        e && this.enableEventListeners();
        this.state.eventsEnabled = e
      }
      return hi(t, [{
        key: "update",
        value: function () {
          return vi.call(this)
        }
      }, {
        key: "destroy",
        value: function () {
          return yi.call(this)
        }
      }, {
        key: "enableEventListeners",
        value: function () {
          return wi.call(this)
        }
      }, {
        key: "disableEventListeners",
        value: function () {
          return ki.call(this)
        }
      }]), t
    }();
  return y.Utils = (typeof window != "undefined" ? window : global).PopperUtils, y.placements = it, y.Defaults = yr, y
});
/*!
 * Bootstrap v4.2.1 (https://getbootstrap.com/)
 * Copyright 2011-2018 The Bootstrap Authors (https://github.com/twbs/bootstrap/graphs/contributors)
 * Licensed under MIT (https://github.com/twbs/bootstrap/blob/master/LICENSE)
 */
(function (n, t) {
  typeof exports == "object" && typeof module != "undefined" ? t(exports, require("popper.js"), require("jquery")) : typeof define == "function" && define.amd ? define(["exports", "popper.js", "jquery"], t) : t(n.bootstrap = {}, n.Popper, n.jQuery)
})(this, function (n, t, i) {
  "use strict";

  function eu(n, t) {
    for (var i, r = 0; r < t.length; r++) i = t[r], i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(n, i.key, i)
  }

  function p(n, t, i) {
    return t && eu(n.prototype, t), i && eu(n, i), n
  }

  function ku(n, t, i) {
    return t in n ? Object.defineProperty(n, t, {
      value: i,
      enumerable: !0,
      configurable: !0,
      writable: !0
    }) : n[t] = i, n
  }

  function o(n) {
    for (var i, r, t = 1; t < arguments.length; t++) i = arguments[t] != null ? arguments[t] : {}, r = Object.keys(i), typeof Object.getOwnPropertySymbols == "function" && (r = r.concat(Object.getOwnPropertySymbols(i).filter(function (n) {
      return Object.getOwnPropertyDescriptor(i, n).enumerable
    }))), r.forEach(function (t) {
      ku(n, t, i[t])
    });
    return n
  }

  function du(n, t) {
    n.prototype = Object.create(t.prototype);
    n.prototype.constructor = n;
    n.__proto__ = t
  }

  function tf(n) {
    return {}.toString.call(n).match(/\s([a-z]+)/i)[1].toLowerCase()
  }

  function rf() {
    return {
      bindType: nr,
      delegateType: nr,
      handle: function (n) {
        return i(n.target).is(this) ? n.handleObj.handler.apply(this, arguments) : undefined
      }
    }
  }

  function uf(n) {
    var u = this,
      t = !1;
    i(this).one(r.TRANSITION_END, function () {
      t = !0
    });
    return setTimeout(function () {
      t || r.triggerTransitionEnd(u)
    }, n), this
  }

  function ff() {
    i.fn.emulateTransitionEnd = uf;
    i.event.special[r.TRANSITION_END] = rf()
  }
  var r;
  t = t && t.hasOwnProperty("default") ? t["default"] : t;
  i = i && i.hasOwnProperty("default") ? i["default"] : i;
  var nr = "transitionend",
    gu = 1e6,
    nf = 1e3;
  r = {
    TRANSITION_END: "bsTransitionEnd",
    getUID: function (n) {
      do n += ~~(Math.random() * gu); while (document.getElementById(n));
      return n
    },
    getSelectorFromElement: function (n) {
      var t = n.getAttribute("data-target"),
        i;
      return t && t !== "#" || (i = n.getAttribute("href"), t = i && i !== "#" ? i.trim() : ""), t && document.querySelector(t) ? t : null
    },
    getTransitionDurationFromElement: function (n) {
      if (!n) return 0;
      var t = i(n).css("transition-duration"),
        r = i(n).css("transition-delay"),
        u = parseFloat(t),
        f = parseFloat(r);
      return !u && !f ? 0 : (t = t.split(",")[0], r = r.split(",")[0], (parseFloat(t) + parseFloat(r)) * nf)
    },
    reflow: function (n) {
      return n.offsetHeight
    },
    triggerTransitionEnd: function (n) {
      i(n).trigger(nr)
    },
    supportsTransitionEnd: function () {
      return Boolean(nr)
    },
    isElement: function (n) {
      return (n[0] || n).nodeType
    },
    typeCheckConfig: function (n, t, i) {
      for (var u in i)
        if (Object.prototype.hasOwnProperty.call(i, u)) {
          var e = i[u],
            f = t[u],
            o = f && r.isElement(f) ? "element" : tf(f);
          if (!new RegExp(e).test(o)) throw new Error(n.toUpperCase() + ": " + ('Option "' + u + '" provided type "' + o + '" ') + ('but expected type "' + e + '".'));
        }
    },
    findShadowRoot: function (n) {
      if (!document.documentElement.attachShadow) return null;
      if (typeof n.getRootNode == "function") {
        var t = n.getRootNode();
        return t instanceof ShadowRoot ? t : null
      }
      return n instanceof ShadowRoot ? n : n.parentNode ? r.findShadowRoot(n.parentNode) : null
    }
  };
  ff();
  var fi = "alert",
    ef = "4.2.1",
    tr = "bs.alert",
    ar = "." + tr,
    of = i.fn[fi],
    vr = {
      CLOSE: "close" + ar,
      CLOSED: "closed" + ar,
      CLICK_DATA_API: "click" + ar + ".data-api"
    },
    yr = {
      ALERT: "alert",
      FADE: "fade",
      SHOW: "show"
    },
    wt = function () {
      function n(n) {
        this._element = n
      }
      var t = n.prototype;
      return t.close = function (n) {
        var t = this._element,
          i;
        (n && (t = this._getRootElement(n)), i = this._triggerCloseEvent(t), i.isDefaultPrevented()) || this._removeElement(t)
      }, t.dispose = function () {
        i.removeData(this._element, tr);
        this._element = null
      }, t._getRootElement = function (n) {
        var u = r.getSelectorFromElement(n),
          t = !1;
        return u && (t = document.querySelector(u)), t || (t = i(n).closest("." + yr.ALERT)[0]), t
      }, t._triggerCloseEvent = function (n) {
        var t = i.Event(vr.CLOSE);
        return i(n).trigger(t), t
      }, t._removeElement = function (n) {
        var u = this,
          t;
        if (i(n).removeClass(yr.SHOW), !i(n).hasClass(yr.FADE)) {
          this._destroyElement(n);
          return
        }
        t = r.getTransitionDurationFromElement(n);
        i(n).one(r.TRANSITION_END, function (t) {
          return u._destroyElement(n, t)
        }).emulateTransitionEnd(t)
      }, t._destroyElement = function (n) {
        i(n).detach().trigger(vr.CLOSED).remove()
      }, n._jQueryInterface = function (t) {
        return this.each(function () {
          var u = i(this),
            r = u.data(tr);
          r || (r = new n(this), u.data(tr, r));
          t === "close" && r[t](this)
        })
      }, n._handleDismiss = function (n) {
        return function (t) {
          t && t.preventDefault();
          n.close(this)
        }
      }, p(n, null, [{
        key: "VERSION",
        get: function () {
          return ef
        }
      }]), n
    }();
  i(document).on(vr.CLICK_DATA_API, {
    DISMISS: '[data-dismiss="alert"]'
  }.DISMISS, wt._handleDismiss(new wt));
  i.fn[fi] = wt._jQueryInterface;
  i.fn[fi].Constructor = wt;
  i.fn[fi].noConflict = function () {
    return i.fn[fi] = of , wt._jQueryInterface
  };
  var ei = "button",
    sf = "4.2.1",
    ir = "bs.button",
    pr = "." + ir,
    wr = ".data-api",
    hf = i.fn[ei],
    ht = {
      ACTIVE: "active",
      BUTTON: "btn",
      FOCUS: "focus"
    },
    ct = {
      DATA_TOGGLE_CARROT: '[data-toggle^="button"]',
      DATA_TOGGLE: '[data-toggle="buttons"]',
      INPUT: 'input:not([type="hidden"])',
      ACTIVE: ".active",
      BUTTON: ".btn"
    },
    ou = {
      CLICK_DATA_API: "click" + pr + wr,
      FOCUS_BLUR_DATA_API: "focus" + pr + wr + " " + ("blur" + pr + wr)
    },
    oi = function () {
      function n(n) {
        this._element = n
      }
      var t = n.prototype;
      return t.toggle = function () {
        var r = !0,
          f = !0,
          t = i(this._element).closest(ct.DATA_TOGGLE)[0],
          n, u;
        if (t && (n = this._element.querySelector(ct.INPUT), n)) {
          if (n.type === "radio" && (n.checked && this._element.classList.contains(ht.ACTIVE) ? r = !1 : (u = t.querySelector(ct.ACTIVE), u && i(u).removeClass(ht.ACTIVE))), r) {
            if (n.hasAttribute("disabled") || t.hasAttribute("disabled") || n.classList.contains("disabled") || t.classList.contains("disabled")) return;
            n.checked = !this._element.classList.contains(ht.ACTIVE);
            i(n).trigger("change")
          }
          n.focus();
          f = !1
        }
        f && this._element.setAttribute("aria-pressed", !this._element.classList.contains(ht.ACTIVE));
        r && i(this._element).toggleClass(ht.ACTIVE)
      }, t.dispose = function () {
        i.removeData(this._element, ir);
        this._element = null
      }, n._jQueryInterface = function (t) {
        return this.each(function () {
          var r = i(this).data(ir);
          r || (r = new n(this), i(this).data(ir, r));
          t === "toggle" && r[t]()
        })
      }, p(n, null, [{
        key: "VERSION",
        get: function () {
          return sf
        }
      }]), n
    }();
  i(document).on(ou.CLICK_DATA_API, ct.DATA_TOGGLE_CARROT, function (n) {
    n.preventDefault();
    var t = n.target;
    i(t).hasClass(ht.BUTTON) || (t = i(t).closest(ct.BUTTON));
    oi._jQueryInterface.call(i(t), "toggle")
  }).on(ou.FOCUS_BLUR_DATA_API, ct.DATA_TOGGLE_CARROT, function (n) {
    var t = i(n.target).closest(ct.BUTTON)[0];
    i(t).toggleClass(ht.FOCUS, /^focus(in)?$/.test(n.type))
  });
  i.fn[ei] = oi._jQueryInterface;
  i.fn[ei].Constructor = oi;
  i.fn[ei].noConflict = function () {
    return i.fn[ei] = hf, oi._jQueryInterface
  };
  var bt = "carousel",
    cf = "4.2.1",
    si = "bs.carousel",
    h = "." + si,
    su = ".data-api",
    lf = i.fn[bt],
    af = 37,
    vf = 39,
    yf = 500,
    pf = 40,
    br = {
      interval: 5e3,
      keyboard: !0,
      slide: !1,
      pause: "hover",
      wrap: !0,
      touch: !0
    },
    wf = {
      interval: "(number|boolean)",
      keyboard: "boolean",
      slide: "(boolean|string)",
      pause: "(string|boolean)",
      wrap: "boolean",
      touch: "boolean"
    },
    k = {
      NEXT: "next",
      PREV: "prev",
      LEFT: "left",
      RIGHT: "right"
    },
    c = {
      SLIDE: "slide" + h,
      SLID: "slid" + h,
      KEYDOWN: "keydown" + h,
      MOUSEENTER: "mouseenter" + h,
      MOUSELEAVE: "mouseleave" + h,
      TOUCHSTART: "touchstart" + h,
      TOUCHMOVE: "touchmove" + h,
      TOUCHEND: "touchend" + h,
      POINTERDOWN: "pointerdown" + h,
      POINTERUP: "pointerup" + h,
      DRAG_START: "dragstart" + h,
      LOAD_DATA_API: "load" + h + su,
      CLICK_DATA_API: "click" + h + su
    },
    l = {
      CAROUSEL: "carousel",
      ACTIVE: "active",
      SLIDE: "slide",
      RIGHT: "carousel-item-right",
      LEFT: "carousel-item-left",
      NEXT: "carousel-item-next",
      PREV: "carousel-item-prev",
      ITEM: "carousel-item",
      POINTER_EVENT: "pointer-event"
    },
    d = {
      ACTIVE: ".active",
      ACTIVE_ITEM: ".active.carousel-item",
      ITEM: ".carousel-item",
      ITEM_IMG: ".carousel-item img",
      NEXT_PREV: ".carousel-item-next, .carousel-item-prev",
      INDICATORS: ".carousel-indicators",
      DATA_SLIDE: "[data-slide], [data-slide-to]",
      DATA_RIDE: '[data-ride="carousel"]'
    },
    hu = {
      TOUCH: "touch",
      PEN: "pen"
    },
    kt = function () {
      function t(n, t) {
        this._items = null;
        this._interval = null;
        this._activeElement = null;
        this._isPaused = !1;
        this._isSliding = !1;
        this.touchTimeout = null;
        this.touchStartX = 0;
        this.touchDeltaX = 0;
        this._config = this._getConfig(t);
        this._element = n;
        this._indicatorsElement = this._element.querySelector(d.INDICATORS);
        this._touchSupported = "ontouchstart" in document.documentElement || navigator.maxTouchPoints > 0;
        this._pointerEvent = Boolean(window.PointerEvent || window.MSPointerEvent);
        this._addEventListeners()
      }
      var n = t.prototype;
      return n.next = function () {
        this._isSliding || this._slide(k.NEXT)
      }, n.nextWhenVisible = function () {
        !document.hidden && i(this._element).is(":visible") && i(this._element).css("visibility") !== "hidden" && this.next()
      }, n.prev = function () {
        this._isSliding || this._slide(k.PREV)
      }, n.pause = function (n) {
        n || (this._isPaused = !0);
        this._element.querySelector(d.NEXT_PREV) && (r.triggerTransitionEnd(this._element), this.cycle(!0));
        clearInterval(this._interval);
        this._interval = null
      }, n.cycle = function (n) {
        n || (this._isPaused = !1);
        this._interval && (clearInterval(this._interval), this._interval = null);
        this._config.interval && !this._isPaused && (this._interval = setInterval((document.visibilityState ? this.nextWhenVisible : this.next).bind(this), this._config.interval))
      }, n.to = function (n) {
        var u = this,
          t, r;
        if (this._activeElement = this._element.querySelector(d.ACTIVE_ITEM), t = this._getItemIndex(this._activeElement), !(n > this._items.length - 1) && !(n < 0)) {
          if (this._isSliding) {
            i(this._element).one(c.SLID, function () {
              return u.to(n)
            });
            return
          }
          if (t === n) {
            this.pause();
            this.cycle();
            return
          }
          r = n > t ? k.NEXT : k.PREV;
          this._slide(r, this._items[n])
        }
      }, n.dispose = function () {
        i(this._element).off(h);
        i.removeData(this._element, si);
        this._items = null;
        this._config = null;
        this._element = null;
        this._interval = null;
        this._isPaused = null;
        this._isSliding = null;
        this._activeElement = null;
        this._indicatorsElement = null
      }, n._getConfig = function (n) {
        return n = o({}, br, n), r.typeCheckConfig(bt, n, wf), n
      }, n._handleSwipe = function () {
        var t = Math.abs(this.touchDeltaX),
          n;
        t <= pf || (n = t / this.touchDeltaX, n > 0 && this.prev(), n < 0 && this.next())
      }, n._addEventListeners = function () {
        var n = this;
        if (this._config.keyboard) i(this._element).on(c.KEYDOWN, function (t) {
          return n._keydown(t)
        });
        if (this._config.pause === "hover") i(this._element).on(c.MOUSEENTER, function (t) {
          return n.pause(t)
        }).on(c.MOUSELEAVE, function (t) {
          return n.cycle(t)
        });
        this._addTouchEventListeners()
      }, n._addTouchEventListeners = function () {
        var n = this;
        if (this._touchSupported) {
          var t = function (t) {
              n._pointerEvent && hu[t.originalEvent.pointerType.toUpperCase()] ? n.touchStartX = t.originalEvent.clientX : n._pointerEvent || (n.touchStartX = t.originalEvent.touches[0].clientX)
            },
            u = function (t) {
              n.touchDeltaX = t.originalEvent.touches && t.originalEvent.touches.length > 1 ? 0 : t.originalEvent.touches[0].clientX - n.touchStartX
            },
            r = function (t) {
              n._pointerEvent && hu[t.originalEvent.pointerType.toUpperCase()] && (n.touchDeltaX = t.originalEvent.clientX - n.touchStartX);
              n._handleSwipe();
              n._config.pause === "hover" && (n.pause(), n.touchTimeout && clearTimeout(n.touchTimeout), n.touchTimeout = setTimeout(function (t) {
                return n.cycle(t)
              }, yf + n._config.interval))
            };
          i(this._element.querySelectorAll(d.ITEM_IMG)).on(c.DRAG_START, function (n) {
            return n.preventDefault()
          });
          if (this._pointerEvent) {
            i(this._element).on(c.POINTERDOWN, function (n) {
              return t(n)
            });
            i(this._element).on(c.POINTERUP, function (n) {
              return r(n)
            });
            this._element.classList.add(l.POINTER_EVENT)
          } else {
            i(this._element).on(c.TOUCHSTART, function (n) {
              return t(n)
            });
            i(this._element).on(c.TOUCHMOVE, function (n) {
              return u(n)
            });
            i(this._element).on(c.TOUCHEND, function (n) {
              return r(n)
            })
          }
        }
      }, n._keydown = function (n) {
        if (!/input|textarea/i.test(n.target.tagName)) switch (n.which) {
          case af:
            n.preventDefault();
            this.prev();
            break;
          case vf:
            n.preventDefault();
            this.next()
        }
      }, n._getItemIndex = function (n) {
        return this._items = n && n.parentNode ? [].slice.call(n.parentNode.querySelectorAll(d.ITEM)) : [], this._items.indexOf(n)
      }, n._getItemByDirection = function (n, t) {
        var f = n === k.NEXT,
          e = n === k.PREV,
          i = this._getItemIndex(t),
          o = this._items.length - 1,
          s = e && i === 0 || f && i === o,
          u, r;
        return s && !this._config.wrap ? t : (u = n === k.PREV ? -1 : 1, r = (i + u) % this._items.length, r === -1 ? this._items[this._items.length - 1] : this._items[r])
      }, n._triggerSlideEvent = function (n, t) {
        var u = this._getItemIndex(n),
          f = this._getItemIndex(this._element.querySelector(d.ACTIVE_ITEM)),
          r = i.Event(c.SLIDE, {
            relatedTarget: n,
            direction: t,
            from: f,
            to: u
          });
        return i(this._element).trigger(r), r
      }, n._setActiveIndicatorElement = function (n) {
        var r, t;
        this._indicatorsElement && (r = [].slice.call(this._indicatorsElement.querySelectorAll(d.ACTIVE)), i(r).removeClass(l.ACTIVE), t = this._indicatorsElement.children[this._getItemIndex(n)], t && i(t).addClass(l.ACTIVE))
      }, n._slide = function (n, t) {
        var v = this,
          f = this._element.querySelector(d.ACTIVE_ITEM),
          b = this._getItemIndex(f),
          u = t || f && this._getItemByDirection(n, f),
          g = this._getItemIndex(u),
          y = Boolean(this._interval),
          e, o, s, p, h, a, w;
        if (n === k.NEXT ? (e = l.LEFT, o = l.NEXT, s = k.LEFT) : (e = l.RIGHT, o = l.PREV, s = k.RIGHT), u && i(u).hasClass(l.ACTIVE)) {
          this._isSliding = !1;
          return
        }(p = this._triggerSlideEvent(u, s), p.isDefaultPrevented()) || f && u && (this._isSliding = !0, y && this.pause(), this._setActiveIndicatorElement(u), h = i.Event(c.SLID, {
          relatedTarget: u,
          direction: s,
          from: b,
          to: g
        }), i(this._element).hasClass(l.SLIDE) ? (i(u).addClass(o), r.reflow(u), i(f).addClass(e), i(u).addClass(e), a = parseInt(u.getAttribute("data-interval"), 10), a ? (this._config.defaultInterval = this._config.defaultInterval || this._config.interval, this._config.interval = a) : this._config.interval = this._config.defaultInterval || this._config.interval, w = r.getTransitionDurationFromElement(f), i(f).one(r.TRANSITION_END, function () {
          i(u).removeClass(e + " " + o).addClass(l.ACTIVE);
          i(f).removeClass(l.ACTIVE + " " + o + " " + e);
          v._isSliding = !1;
          setTimeout(function () {
            return i(v._element).trigger(h)
          }, 0)
        }).emulateTransitionEnd(w)) : (i(f).removeClass(l.ACTIVE), i(u).addClass(l.ACTIVE), this._isSliding = !1, i(this._element).trigger(h)), y && this.cycle())
      }, t._jQueryInterface = function (n) {
        return this.each(function () {
          var r = i(this).data(si),
            u = o({}, br, i(this).data()),
            f;
          if (typeof n == "object" && (u = o({}, u, n)), f = typeof n == "string" ? n : u.slide, r || (r = new t(this, u), i(this).data(si, r)), typeof n == "number") r.to(n);
          else if (typeof f == "string") {
            if (typeof r[f] == "undefined") throw new TypeError('No method named "' + f + '"');
            r[f]()
          } else u.interval && (r.pause(), r.cycle())
        })
      }, t._dataApiClickHandler = function (n) {
        var s = r.getSelectorFromElement(this),
          u, e, f;
        s && (u = i(s)[0], u && i(u).hasClass(l.CAROUSEL)) && (e = o({}, i(u).data(), i(this).data()), f = this.getAttribute("data-slide-to"), f && (e.interval = !1), t._jQueryInterface.call(i(u), e), f && i(u).data(si).to(f), n.preventDefault())
      }, p(t, null, [{
        key: "VERSION",
        get: function () {
          return cf
        }
      }, {
        key: "Default",
        get: function () {
          return br
        }
      }]), t
    }();
  i(document).on(c.CLICK_DATA_API, d.DATA_SLIDE, kt._dataApiClickHandler);
  i(window).on(c.LOAD_DATA_API, function () {
    for (var t, r = [].slice.call(document.querySelectorAll(d.DATA_RIDE)), n = 0, u = r.length; n < u; n++) t = i(r[n]), kt._jQueryInterface.call(t, t.data())
  });
  i.fn[bt] = kt._jQueryInterface;
  i.fn[bt].Constructor = kt;
  i.fn[bt].noConflict = function () {
    return i.fn[bt] = lf, kt._jQueryInterface
  };
  var dt = "collapse",
    bf = "4.2.1",
    lt = "bs.collapse",
    hi = "." + lt,
    kf = i.fn[dt],
    kr = {
      toggle: !0,
      parent: ""
    },
    df = {
      toggle: "boolean",
      parent: "(string|element)"
    },
    ci = {
      SHOW: "show" + hi,
      SHOWN: "shown" + hi,
      HIDE: "hide" + hi,
      HIDDEN: "hidden" + hi,
      CLICK_DATA_API: "click" + hi + ".data-api"
    },
    e = {
      SHOW: "show",
      COLLAPSE: "collapse",
      COLLAPSING: "collapsing",
      COLLAPSED: "collapsed"
    },
    dr = {
      WIDTH: "width",
      HEIGHT: "height"
    },
    gr = {
      ACTIVES: ".show, .collapsing",
      DATA_TOGGLE: '[data-toggle="collapse"]'
    },
    li = function () {
      function t(n, t) {
        var u, i, e;
        for (this._isTransitioning = !1, this._element = n, this._config = this._getConfig(t), this._triggerArray = [].slice.call(document.querySelectorAll('[data-toggle="collapse"][href="#' + n.id + '"],' + ('[data-toggle="collapse"][data-target="#' + n.id + '"]'))), u = [].slice.call(document.querySelectorAll(gr.DATA_TOGGLE)), i = 0, e = u.length; i < e; i++) {
          var o = u[i],
            f = r.getSelectorFromElement(o),
            s = [].slice.call(document.querySelectorAll(f)).filter(function (t) {
              return t === n
            });
          f !== null && s.length > 0 && (this._selector = f, this._triggerArray.push(o))
        }
        this._parent = this._config.parent ? this._getParent() : null;
        this._config.parent || this._addAriaAndCollapsedClass(this._element, this._triggerArray);
        this._config.toggle && this.toggle()
      }
      var n = t.prototype;
      return n.toggle = function () {
        i(this._element).hasClass(e.SHOW) ? this.hide() : this.show()
      }, n.show = function () {
        var u = this,
          n, o, s, f;
        if (!this._isTransitioning && !i(this._element).hasClass(e.SHOW) && (this._parent && (n = [].slice.call(this._parent.querySelectorAll(gr.ACTIVES)).filter(function (n) {
            return typeof u._config.parent == "string" ? n.getAttribute("data-parent") === u._config.parent : n.classList.contains(e.COLLAPSE)
          }), n.length === 0 && (n = null)), !n || (o = i(n).not(this._selector).data(lt), !o || !o._isTransitioning)) && (s = i.Event(ci.SHOW), i(this._element).trigger(s), !s.isDefaultPrevented())) {
          n && (t._jQueryInterface.call(i(n).not(this._selector), "hide"), o || i(n).data(lt, null));
          f = this._getDimension();
          i(this._element).removeClass(e.COLLAPSE).addClass(e.COLLAPSING);
          this._element.style[f] = 0;
          this._triggerArray.length && i(this._triggerArray).removeClass(e.COLLAPSED).attr("aria-expanded", !0);
          this.setTransitioning(!0);
          var h = function () {
              i(u._element).removeClass(e.COLLAPSING).addClass(e.COLLAPSE).addClass(e.SHOW);
              u._element.style[f] = "";
              u.setTransitioning(!1);
              i(u._element).trigger(ci.SHOWN)
            },
            c = f[0].toUpperCase() + f.slice(1),
            l = "scroll" + c,
            a = r.getTransitionDurationFromElement(this._element);
          i(this._element).one(r.TRANSITION_END, h).emulateTransitionEnd(a);
          this._element.style[f] = this._element[l] + "px"
        }
      }, n.hide = function () {
        var h = this,
          u, n, f, t, o, s, c, l, a;
        if (!this._isTransitioning && i(this._element).hasClass(e.SHOW) && (u = i.Event(ci.HIDE), i(this._element).trigger(u), !u.isDefaultPrevented())) {
          if (n = this._getDimension(), this._element.style[n] = this._element.getBoundingClientRect()[n] + "px", r.reflow(this._element), i(this._element).addClass(e.COLLAPSING).removeClass(e.COLLAPSE).removeClass(e.SHOW), f = this._triggerArray.length, f > 0)
            for (t = 0; t < f; t++) o = this._triggerArray[t], s = r.getSelectorFromElement(o), s !== null && (c = i([].slice.call(document.querySelectorAll(s))), c.hasClass(e.SHOW) || i(o).addClass(e.COLLAPSED).attr("aria-expanded", !1));
          this.setTransitioning(!0);
          l = function () {
            h.setTransitioning(!1);
            i(h._element).removeClass(e.COLLAPSING).addClass(e.COLLAPSE).trigger(ci.HIDDEN)
          };
          this._element.style[n] = "";
          a = r.getTransitionDurationFromElement(this._element);
          i(this._element).one(r.TRANSITION_END, l).emulateTransitionEnd(a)
        }
      }, n.setTransitioning = function (n) {
        this._isTransitioning = n
      }, n.dispose = function () {
        i.removeData(this._element, lt);
        this._config = null;
        this._parent = null;
        this._element = null;
        this._triggerArray = null;
        this._isTransitioning = null
      }, n._getConfig = function (n) {
        return n = o({}, kr, n), n.toggle = Boolean(n.toggle), r.typeCheckConfig(dt, n, df), n
      }, n._getDimension = function () {
        var n = i(this._element).hasClass(dr.WIDTH);
        return n ? dr.WIDTH : dr.HEIGHT
      }, n._getParent = function () {
        var e = this,
          n, u, f;
        return r.isElement(this._config.parent) ? (n = this._config.parent, typeof this._config.parent.jquery != "undefined" && (n = this._config.parent[0])) : n = document.querySelector(this._config.parent), u = '[data-toggle="collapse"][data-parent="' + this._config.parent + '"]', f = [].slice.call(n.querySelectorAll(u)), i(f).each(function (n, i) {
          e._addAriaAndCollapsedClass(t._getTargetFromElement(i), [i])
        }), n
      }, n._addAriaAndCollapsedClass = function (n, t) {
        var r = i(n).hasClass(e.SHOW);
        t.length && i(t).toggleClass(e.COLLAPSED, !r).attr("aria-expanded", r)
      }, t._getTargetFromElement = function (n) {
        var t = r.getSelectorFromElement(n);
        return t ? document.querySelector(t) : null
      }, t._jQueryInterface = function (n) {
        return this.each(function () {
          var u = i(this),
            r = u.data(lt),
            f = o({}, kr, u.data(), typeof n == "object" && n ? n : {});
          if (!r && f.toggle && /show|hide/.test(n) && (f.toggle = !1), r || (r = new t(this, f), u.data(lt, r)), typeof n == "string") {
            if (typeof r[n] == "undefined") throw new TypeError('No method named "' + n + '"');
            r[n]()
          }
        })
      }, p(t, null, [{
        key: "VERSION",
        get: function () {
          return bf
        }
      }, {
        key: "Default",
        get: function () {
          return kr
        }
      }]), t
    }();
  i(document).on(ci.CLICK_DATA_API, gr.DATA_TOGGLE, function (n) {
    n.currentTarget.tagName === "A" && n.preventDefault();
    var t = i(this),
      u = r.getSelectorFromElement(this),
      f = [].slice.call(document.querySelectorAll(u));
    i(f).each(function () {
      var n = i(this),
        r = n.data(lt),
        u = r ? "toggle" : t.data();
      li._jQueryInterface.call(n, u)
    })
  });
  i.fn[dt] = li._jQueryInterface;
  i.fn[dt].Constructor = li;
  i.fn[dt].noConflict = function () {
    return i.fn[dt] = kf, li._jQueryInterface
  };
  var gt = "dropdown",
    gf = "4.2.1",
    ai = "bs.dropdown",
    ut = "." + ai,
    nu = ".data-api",
    ne = i.fn[gt],
    rr = 27,
    cu = 32,
    lu = 9,
    tu = 38,
    iu = 40,
    te = 3,
    ie = new RegExp(tu + "|" + iu + "|" + rr),
    s = {
      HIDE: "hide" + ut,
      HIDDEN: "hidden" + ut,
      SHOW: "show" + ut,
      SHOWN: "shown" + ut,
      CLICK: "click" + ut,
      CLICK_DATA_API: "click" + ut + nu,
      KEYDOWN_DATA_API: "keydown" + ut + nu,
      KEYUP_DATA_API: "keyup" + ut + nu
    },
    u = {
      DISABLED: "disabled",
      SHOW: "show",
      DROPUP: "dropup",
      DROPRIGHT: "dropright",
      DROPLEFT: "dropleft",
      MENURIGHT: "dropdown-menu-right",
      MENULEFT: "dropdown-menu-left",
      POSITION_STATIC: "position-static"
    },
    g = {
      DATA_TOGGLE: '[data-toggle="dropdown"]',
      FORM_CHILD: ".dropdown form",
      MENU: ".dropdown-menu",
      NAVBAR_NAV: ".navbar-nav",
      VISIBLE_ITEMS: ".dropdown-menu .dropdown-item:not(.disabled):not(:disabled)"
    },
    ni = {
      TOP: "top-start",
      TOPEND: "top-end",
      BOTTOM: "bottom-start",
      BOTTOMEND: "bottom-end",
      RIGHT: "right-start",
      RIGHTEND: "right-end",
      LEFT: "left-start",
      LEFTEND: "left-end"
    },
    re = {
      offset: 0,
      flip: !0,
      boundary: "scrollParent",
      reference: "toggle",
      display: "dynamic"
    },
    ue = {
      offset: "(number|string|function)",
      flip: "boolean",
      boundary: "(string|element)",
      reference: "(string|element)",
      display: "string"
    },
    et = function () {
      function n(n, t) {
        this._element = n;
        this._popper = null;
        this._config = this._getConfig(t);
        this._menu = this._getMenuElement();
        this._inNavbar = this._detectNavbar();
        this._addEventListeners()
      }
      var f = n.prototype;
      return f.toggle = function () {
        var f, c, o, h, e;
        if (!this._element.disabled && !i(this._element).hasClass(u.DISABLED) && (f = n._getParentFromElement(this._element), c = i(this._menu).hasClass(u.SHOW), n._clearMenus(), !c) && (o = {
            relatedTarget: this._element
          }, h = i.Event(s.SHOW, o), i(f).trigger(h), !h.isDefaultPrevented())) {
          if (!this._inNavbar) {
            if (typeof t == "undefined") throw new TypeError("Bootstrap's dropdowns require Popper.js (https://popper.js.org/)");
            e = this._element;
            this._config.reference === "parent" ? e = f : r.isElement(this._config.reference) && (e = this._config.reference, typeof this._config.reference.jquery != "undefined" && (e = this._config.reference[0]));
            this._config.boundary !== "scrollParent" && i(f).addClass(u.POSITION_STATIC);
            this._popper = new t(e, this._menu, this._getPopperConfig())
          }
          if ("ontouchstart" in document.documentElement && i(f).closest(g.NAVBAR_NAV).length === 0) i(document.body).children().on("mouseover", null, i.noop);
          this._element.focus();
          this._element.setAttribute("aria-expanded", !0);
          i(this._menu).toggleClass(u.SHOW);
          i(f).toggleClass(u.SHOW).trigger(i.Event(s.SHOWN, o))
        }
      }, f.show = function () {
        if (!this._element.disabled && !i(this._element).hasClass(u.DISABLED) && !i(this._menu).hasClass(u.SHOW)) {
          var t = {
              relatedTarget: this._element
            },
            r = i.Event(s.SHOW, t),
            f = n._getParentFromElement(this._element);
          (i(f).trigger(r), r.isDefaultPrevented()) || (i(this._menu).toggleClass(u.SHOW), i(f).toggleClass(u.SHOW).trigger(i.Event(s.SHOWN, t)))
        }
      }, f.hide = function () {
        if (!this._element.disabled && !i(this._element).hasClass(u.DISABLED) && i(this._menu).hasClass(u.SHOW)) {
          var t = {
              relatedTarget: this._element
            },
            r = i.Event(s.HIDE, t),
            f = n._getParentFromElement(this._element);
          (i(f).trigger(r), r.isDefaultPrevented()) || (i(this._menu).toggleClass(u.SHOW), i(f).toggleClass(u.SHOW).trigger(i.Event(s.HIDDEN, t)))
        }
      }, f.dispose = function () {
        i.removeData(this._element, ai);
        i(this._element).off(ut);
        this._element = null;
        this._menu = null;
        this._popper !== null && (this._popper.destroy(), this._popper = null)
      }, f.update = function () {
        this._inNavbar = this._detectNavbar();
        this._popper !== null && this._popper.scheduleUpdate()
      }, f._addEventListeners = function () {
        var n = this;
        i(this._element).on(s.CLICK, function (t) {
          t.preventDefault();
          t.stopPropagation();
          n.toggle()
        })
      }, f._getConfig = function (n) {
        return n = o({}, this.constructor.Default, i(this._element).data(), n), r.typeCheckConfig(gt, n, this.constructor.DefaultType), n
      }, f._getMenuElement = function () {
        if (!this._menu) {
          var t = n._getParentFromElement(this._element);
          t && (this._menu = t.querySelector(g.MENU))
        }
        return this._menu
      }, f._getPlacement = function () {
        var t = i(this._element.parentNode),
          n = ni.BOTTOM;
        return t.hasClass(u.DROPUP) ? (n = ni.TOP, i(this._menu).hasClass(u.MENURIGHT) && (n = ni.TOPEND)) : t.hasClass(u.DROPRIGHT) ? n = ni.RIGHT : t.hasClass(u.DROPLEFT) ? n = ni.LEFT : i(this._menu).hasClass(u.MENURIGHT) && (n = ni.BOTTOMEND), n
      }, f._detectNavbar = function () {
        return i(this._element).closest(".navbar").length > 0
      }, f._getPopperConfig = function () {
        var i = this,
          n = {},
          t;
        return typeof this._config.offset == "function" ? n.fn = function (n) {
          return n.offsets = o({}, n.offsets, i._config.offset(n.offsets) || {}), n
        } : n.offset = this._config.offset, t = {
          placement: this._getPlacement(),
          modifiers: {
            offset: n,
            flip: {
              enabled: this._config.flip
            },
            preventOverflow: {
              boundariesElement: this._config.boundary
            }
          }
        }, this._config.display === "static" && (t.modifiers.applyStyle = {
          enabled: !1
        }), t
      }, n._jQueryInterface = function (t) {
        return this.each(function () {
          var r = i(this).data(ai),
            u = typeof t == "object" ? t : null;
          if (r || (r = new n(this, u), i(this).data(ai, r)), typeof t == "string") {
            if (typeof r[t] == "undefined") throw new TypeError('No method named "' + t + '"');
            r[t]()
          }
        })
      }, n._clearMenus = function (t) {
        var f, r, c, a, h;
        if (!t || t.which !== te && (t.type !== "keyup" || t.which === lu))
          for (f = [].slice.call(document.querySelectorAll(g.DATA_TOGGLE)), r = 0, c = f.length; r < c; r++) {
            var e = n._getParentFromElement(f[r]),
              l = i(f[r]).data(ai),
              o = {
                relatedTarget: f[r]
              };
            (t && t.type === "click" && (o.clickEvent = t), l) && (a = l._menu, i(e).hasClass(u.SHOW)) && (t && (t.type === "click" && /input|textarea/i.test(t.target.tagName) || t.type === "keyup" && t.which === lu) && i.contains(e, t.target) || (h = i.Event(s.HIDE, o), i(e).trigger(h), h.isDefaultPrevented()) || ("ontouchstart" in document.documentElement && i(document.body).children().off("mouseover", null, i.noop), f[r].setAttribute("aria-expanded", "false"), i(a).removeClass(u.SHOW), i(e).removeClass(u.SHOW).trigger(i.Event(s.HIDDEN, o))))
          }
      }, n._getParentFromElement = function (n) {
        var t, i = r.getSelectorFromElement(n);
        return i && (t = document.querySelector(i)), t || n.parentNode
      }, n._dataApiKeydownHandler = function (t) {
        var e, o, s, f, r;
        if ((/input|textarea/i.test(t.target.tagName) ? t.which !== cu && (t.which === rr || (t.which === iu || t.which === tu) && !i(t.target).closest(g.MENU).length) : ie.test(t.which)) && (t.preventDefault(), t.stopPropagation(), !this.disabled && !i(this).hasClass(u.DISABLED))) {
          if (e = n._getParentFromElement(this), o = i(e).hasClass(u.SHOW), !o || o && (t.which === rr || t.which === cu)) {
            t.which === rr && (s = e.querySelector(g.DATA_TOGGLE), i(s).trigger("focus"));
            i(this).trigger("click");
            return
          }(f = [].slice.call(e.querySelectorAll(g.VISIBLE_ITEMS)), f.length !== 0) && (r = f.indexOf(t.target), t.which === tu && r > 0 && r--, t.which === iu && r < f.length - 1 && r++, r < 0 && (r = 0), f[r].focus())
        }
      }, p(n, null, [{
        key: "VERSION",
        get: function () {
          return gf
        }
      }, {
        key: "Default",
        get: function () {
          return re
        }
      }, {
        key: "DefaultType",
        get: function () {
          return ue
        }
      }]), n
    }();
  i(document).on(s.KEYDOWN_DATA_API, g.DATA_TOGGLE, et._dataApiKeydownHandler).on(s.KEYDOWN_DATA_API, g.MENU, et._dataApiKeydownHandler).on(s.CLICK_DATA_API + " " + s.KEYUP_DATA_API, et._clearMenus).on(s.CLICK_DATA_API, g.DATA_TOGGLE, function (n) {
    n.preventDefault();
    n.stopPropagation();
    et._jQueryInterface.call(i(this), "toggle")
  }).on(s.CLICK_DATA_API, g.FORM_CHILD, function (n) {
    n.stopPropagation()
  });
  i.fn[gt] = et._jQueryInterface;
  i.fn[gt].Constructor = et;
  i.fn[gt].noConflict = function () {
    return i.fn[gt] = ne, et._jQueryInterface
  };
  var ti = "modal",
    fe = "4.2.1",
    vi = "bs.modal",
    v = "." + vi,
    ee = i.fn[ti],
    oe = 27,
    ru = {
      backdrop: !0,
      keyboard: !0,
      focus: !0,
      show: !0
    },
    se = {
      backdrop: "(boolean|string)",
      keyboard: "boolean",
      focus: "boolean",
      show: "boolean"
    },
    f = {
      HIDE: "hide" + v,
      HIDDEN: "hidden" + v,
      SHOW: "show" + v,
      SHOWN: "shown" + v,
      FOCUSIN: "focusin" + v,
      RESIZE: "resize" + v,
      CLICK_DISMISS: "click.dismiss" + v,
      KEYDOWN_DISMISS: "keydown.dismiss" + v,
      MOUSEUP_DISMISS: "mouseup.dismiss" + v,
      MOUSEDOWN_DISMISS: "mousedown.dismiss" + v,
      CLICK_DATA_API: "click" + v + ".data-api"
    },
    a = {
      SCROLLBAR_MEASURER: "modal-scrollbar-measure",
      BACKDROP: "modal-backdrop",
      OPEN: "modal-open",
      FADE: "fade",
      SHOW: "show"
    },
    at = {
      DIALOG: ".modal-dialog",
      DATA_TOGGLE: '[data-toggle="modal"]',
      DATA_DISMISS: '[data-dismiss="modal"]',
      FIXED_CONTENT: ".fixed-top, .fixed-bottom, .is-fixed, .sticky-top",
      STICKY_CONTENT: ".sticky-top"
    },
    yi = function () {
      function t(n, t) {
        this._config = this._getConfig(t);
        this._element = n;
        this._dialog = n.querySelector(at.DIALOG);
        this._backdrop = null;
        this._isShown = !1;
        this._isBodyOverflowing = !1;
        this._ignoreBackdropClick = !1;
        this._isTransitioning = !1;
        this._scrollbarWidth = 0
      }
      var n = t.prototype;
      return n.toggle = function (n) {
        return this._isShown ? this.hide() : this.show(n)
      }, n.show = function (n) {
        var t = this,
          r;
        if (!this._isShown && !this._isTransitioning && (i(this._element).hasClass(a.FADE) && (this._isTransitioning = !0), r = i.Event(f.SHOW, {
            relatedTarget: n
          }), i(this._element).trigger(r), !this._isShown && !r.isDefaultPrevented())) {
          this._isShown = !0;
          this._checkScrollbar();
          this._setScrollbar();
          this._adjustDialog();
          this._setEscapeEvent();
          this._setResizeEvent();
          i(this._element).on(f.CLICK_DISMISS, at.DATA_DISMISS, function (n) {
            return t.hide(n)
          });
          i(this._dialog).on(f.MOUSEDOWN_DISMISS, function () {
            i(t._element).one(f.MOUSEUP_DISMISS, function (n) {
              i(n.target).is(t._element) && (t._ignoreBackdropClick = !0)
            })
          });
          this._showBackdrop(function () {
            return t._showElement(n)
          })
        }
      }, n.hide = function (n) {
        var o = this,
          t, u, e;
        (n && n.preventDefault(), this._isShown && !this._isTransitioning) && (t = i.Event(f.HIDE), i(this._element).trigger(t), this._isShown && !t.isDefaultPrevented()) && (this._isShown = !1, u = i(this._element).hasClass(a.FADE), u && (this._isTransitioning = !0), this._setEscapeEvent(), this._setResizeEvent(), i(document).off(f.FOCUSIN), i(this._element).removeClass(a.SHOW), i(this._element).off(f.CLICK_DISMISS), i(this._dialog).off(f.MOUSEDOWN_DISMISS), u ? (e = r.getTransitionDurationFromElement(this._element), i(this._element).one(r.TRANSITION_END, function (n) {
          return o._hideModal(n)
        }).emulateTransitionEnd(e)) : this._hideModal())
      }, n.dispose = function () {
        [window, this._element, this._dialog].forEach(function (n) {
          return i(n).off(v)
        });
        i(document).off(f.FOCUSIN);
        i.removeData(this._element, vi);
        this._config = null;
        this._element = null;
        this._dialog = null;
        this._backdrop = null;
        this._isShown = null;
        this._isBodyOverflowing = null;
        this._ignoreBackdropClick = null;
        this._isTransitioning = null;
        this._scrollbarWidth = null
      }, n.handleUpdate = function () {
        this._adjustDialog()
      }, n._getConfig = function (n) {
        return n = o({}, ru, n), r.typeCheckConfig(ti, n, se), n
      }, n._showElement = function (n) {
        var t = this,
          e = i(this._element).hasClass(a.FADE),
          o, u, s;
        this._element.parentNode && this._element.parentNode.nodeType === Node.ELEMENT_NODE || document.body.appendChild(this._element);
        this._element.style.display = "block";
        this._element.removeAttribute("aria-hidden");
        this._element.setAttribute("aria-modal", !0);
        this._element.scrollTop = 0;
        e && r.reflow(this._element);
        i(this._element).addClass(a.SHOW);
        this._config.focus && this._enforceFocus();
        o = i.Event(f.SHOWN, {
          relatedTarget: n
        });
        u = function () {
          t._config.focus && t._element.focus();
          t._isTransitioning = !1;
          i(t._element).trigger(o)
        };
        e ? (s = r.getTransitionDurationFromElement(this._dialog), i(this._dialog).one(r.TRANSITION_END, u).emulateTransitionEnd(s)) : u()
      }, n._enforceFocus = function () {
        var n = this;
        i(document).off(f.FOCUSIN).on(f.FOCUSIN, function (t) {
          document !== t.target && n._element !== t.target && i(n._element).has(t.target).length === 0 && n._element.focus()
        })
      }, n._setEscapeEvent = function () {
        var n = this;
        if (this._isShown && this._config.keyboard) i(this._element).on(f.KEYDOWN_DISMISS, function (t) {
          t.which === oe && (t.preventDefault(), n.hide())
        });
        else this._isShown || i(this._element).off(f.KEYDOWN_DISMISS)
      }, n._setResizeEvent = function () {
        var n = this;
        if (this._isShown) i(window).on(f.RESIZE, function (t) {
          return n.handleUpdate(t)
        });
        else i(window).off(f.RESIZE)
      }, n._hideModal = function () {
        var n = this;
        this._element.style.display = "none";
        this._element.setAttribute("aria-hidden", !0);
        this._element.removeAttribute("aria-modal");
        this._isTransitioning = !1;
        this._showBackdrop(function () {
          i(document.body).removeClass(a.OPEN);
          n._resetAdjustments();
          n._resetScrollbar();
          i(n._element).trigger(f.HIDDEN)
        })
      }, n._removeBackdrop = function () {
        this._backdrop && (i(this._backdrop).remove(), this._backdrop = null)
      }, n._showBackdrop = function (n) {
        var t = this,
          u = i(this._element).hasClass(a.FADE) ? a.FADE : "",
          o, e, s;
        if (this._isShown && this._config.backdrop) {
          this._backdrop = document.createElement("div");
          this._backdrop.className = a.BACKDROP;
          u && this._backdrop.classList.add(u);
          i(this._backdrop).appendTo(document.body);
          i(this._element).on(f.CLICK_DISMISS, function (n) {
            if (t._ignoreBackdropClick) {
              t._ignoreBackdropClick = !1;
              return
            }
            n.target === n.currentTarget && (t._config.backdrop === "static" ? t._element.focus() : t.hide())
          });
          if (u && r.reflow(this._backdrop), i(this._backdrop).addClass(a.SHOW), !n) return;
          if (!u) {
            n();
            return
          }
          o = r.getTransitionDurationFromElement(this._backdrop);
          i(this._backdrop).one(r.TRANSITION_END, n).emulateTransitionEnd(o)
        } else !this._isShown && this._backdrop ? (i(this._backdrop).removeClass(a.SHOW), e = function () {
          t._removeBackdrop();
          n && n()
        }, i(this._element).hasClass(a.FADE) ? (s = r.getTransitionDurationFromElement(this._backdrop), i(this._backdrop).one(r.TRANSITION_END, e).emulateTransitionEnd(s)) : e()) : n && n()
      }, n._adjustDialog = function () {
        var n = this._element.scrollHeight > document.documentElement.clientHeight;
        !this._isBodyOverflowing && n && (this._element.style.paddingLeft = this._scrollbarWidth + "px");
        this._isBodyOverflowing && !n && (this._element.style.paddingRight = this._scrollbarWidth + "px")
      }, n._resetAdjustments = function () {
        this._element.style.paddingLeft = "";
        this._element.style.paddingRight = ""
      }, n._checkScrollbar = function () {
        var n = document.body.getBoundingClientRect();
        this._isBodyOverflowing = n.left + n.right < window.innerWidth;
        this._scrollbarWidth = this._getScrollbarWidth()
      }, n._setScrollbar = function () {
        var n = this,
          t, r, u, f;
        this._isBodyOverflowing && (t = [].slice.call(document.querySelectorAll(at.FIXED_CONTENT)), r = [].slice.call(document.querySelectorAll(at.STICKY_CONTENT)), i(t).each(function (t, r) {
          var u = r.style.paddingRight,
            f = i(r).css("padding-right");
          i(r).data("padding-right", u).css("padding-right", parseFloat(f) + n._scrollbarWidth + "px")
        }), i(r).each(function (t, r) {
          var u = r.style.marginRight,
            f = i(r).css("margin-right");
          i(r).data("margin-right", u).css("margin-right", parseFloat(f) - n._scrollbarWidth + "px")
        }), u = document.body.style.paddingRight, f = i(document.body).css("padding-right"), i(document.body).data("padding-right", u).css("padding-right", parseFloat(f) + this._scrollbarWidth + "px"));
        i(document.body).addClass(a.OPEN)
      }, n._resetScrollbar = function () {
        var r = [].slice.call(document.querySelectorAll(at.FIXED_CONTENT)),
          t, n;
        i(r).each(function (n, t) {
          var r = i(t).data("padding-right");
          i(t).removeData("padding-right");
          t.style.paddingRight = r ? r : ""
        });
        t = [].slice.call(document.querySelectorAll("" + at.STICKY_CONTENT));
        i(t).each(function (n, t) {
          var r = i(t).data("margin-right");
          typeof r != "undefined" && i(t).css("margin-right", r).removeData("margin-right")
        });
        n = i(document.body).data("padding-right");
        i(document.body).removeData("padding-right");
        document.body.style.paddingRight = n ? n : ""
      }, n._getScrollbarWidth = function () {
        var n = document.createElement("div"),
          t;
        return n.className = a.SCROLLBAR_MEASURER, document.body.appendChild(n), t = n.getBoundingClientRect().width - n.clientWidth, document.body.removeChild(n), t
      }, t._jQueryInterface = function (n, r) {
        return this.each(function () {
          var u = i(this).data(vi),
            f = o({}, ru, i(this).data(), typeof n == "object" && n ? n : {});
          if (u || (u = new t(this, f), i(this).data(vi, u)), typeof n == "string") {
            if (typeof u[n] == "undefined") throw new TypeError('No method named "' + n + '"');
            u[n](r)
          } else f.show && u.show(r)
        })
      }, p(t, null, [{
        key: "VERSION",
        get: function () {
          return fe
        }
      }, {
        key: "Default",
        get: function () {
          return ru
        }
      }]), t
    }();
  i(document).on(f.CLICK_DATA_API, at.DATA_TOGGLE, function (n) {
    var u = this,
      t, e = r.getSelectorFromElement(this),
      s, h;
    e && (t = document.querySelector(e));
    s = i(t).data(vi) ? "toggle" : o({}, i(t).data(), i(this).data());
    (this.tagName === "A" || this.tagName === "AREA") && n.preventDefault();
    h = i(t).one(f.SHOW, function (n) {
      if (!n.isDefaultPrevented()) h.one(f.HIDDEN, function () {
        i(u).is(":visible") && u.focus()
      })
    });
    yi._jQueryInterface.call(i(t), s, this)
  });
  i.fn[ti] = yi._jQueryInterface;
  i.fn[ti].Constructor = yi;
  i.fn[ti].noConflict = function () {
    return i.fn[ti] = ee, yi._jQueryInterface
  };
  var vt = "tooltip",
    he = "4.2.1",
    ur = "bs.tooltip",
    w = "." + ur,
    ce = i.fn[vt],
    au = "bs-tooltip",
    le = new RegExp("(^|\\s)" + au + "\\S+", "g"),
    ae = {
      animation: "boolean",
      template: "string",
      title: "(string|element|function)",
      trigger: "string",
      delay: "(number|object)",
      html: "boolean",
      selector: "(string|boolean)",
      placement: "(string|function)",
      offset: "(number|string)",
      container: "(string|element|boolean)",
      fallbackPlacement: "(string|array)",
      boundary: "(string|element)"
    },
    ve = {
      AUTO: "auto",
      TOP: "top",
      RIGHT: "right",
      BOTTOM: "bottom",
      LEFT: "left"
    },
    ye = {
      animation: !0,
      template: '<div class="tooltip" role="tooltip"><div class="arrow"><\/div><div class="tooltip-inner"><\/div><\/div>',
      trigger: "hover focus",
      title: "",
      delay: 0,
      html: !1,
      selector: !1,
      placement: "top",
      offset: 0,
      container: !1,
      fallbackPlacement: "flip",
      boundary: "scrollParent"
    },
    ot = {
      SHOW: "show",
      OUT: "out"
    },
    pe = {
      HIDE: "hide" + w,
      HIDDEN: "hidden" + w,
      SHOW: "show" + w,
      SHOWN: "shown" + w,
      INSERTED: "inserted" + w,
      CLICK: "click" + w,
      FOCUSIN: "focusin" + w,
      FOCUSOUT: "focusout" + w,
      MOUSEENTER: "mouseenter" + w,
      MOUSELEAVE: "mouseleave" + w
    },
    nt = {
      FADE: "fade",
      SHOW: "show"
    },
    vu = {
      TOOLTIP: ".tooltip",
      TOOLTIP_INNER: ".tooltip-inner",
      ARROW: ".arrow"
    },
    tt = {
      HOVER: "hover",
      FOCUS: "focus",
      CLICK: "click",
      MANUAL: "manual"
    },
    yt = function () {
      function u(n, i) {
        if (typeof t == "undefined") throw new TypeError("Bootstrap's tooltips require Popper.js (https://popper.js.org/)");
        this._isEnabled = !0;
        this._timeout = 0;
        this._hoverState = "";
        this._activeTrigger = {};
        this._popper = null;
        this.element = n;
        this.config = this._getConfig(i);
        this.tip = null;
        this._setListeners()
      }
      var n = u.prototype;
      return n.enable = function () {
        this._isEnabled = !0
      }, n.disable = function () {
        this._isEnabled = !1
      }, n.toggleEnabled = function () {
        this._isEnabled = !this._isEnabled
      }, n.toggle = function (n) {
        if (this._isEnabled)
          if (n) {
            var r = this.constructor.DATA_KEY,
              t = i(n.currentTarget).data(r);
            t || (t = new this.constructor(n.currentTarget, this._getDelegateConfig()), i(n.currentTarget).data(r, t));
            t._activeTrigger.click = !t._activeTrigger.click;
            t._isWithActiveTrigger() ? t._enter(null, t) : t._leave(null, t)
          } else {
            if (i(this.getTipElement()).hasClass(nt.SHOW)) {
              this._leave(null, this);
              return
            }
            this._enter(null, this)
          }
      }, n.dispose = function () {
        clearTimeout(this._timeout);
        i.removeData(this.element, this.constructor.DATA_KEY);
        i(this.element).off(this.constructor.EVENT_KEY);
        i(this.element).closest(".modal").off("hide.bs.modal");
        this.tip && i(this.tip).remove();
        this._isEnabled = null;
        this._timeout = null;
        this._hoverState = null;
        this._activeTrigger = null;
        this._popper !== null && this._popper.destroy();
        this._popper = null;
        this.element = null;
        this.config = null;
        this.tip = null
      }, n.show = function () {
        var n = this,
          f, e, c, u, o, l, s, a, h, v;
        if (i(this.element).css("display") === "none") throw new Error("Please use show on visible elements");
        if (f = i.Event(this.constructor.Event.SHOW), this.isWithContent() && this._isEnabled) {
          if (i(this.element).trigger(f), e = r.findShadowRoot(this.element), c = i.contains(e !== null ? e : this.element.ownerDocument.documentElement, this.element), f.isDefaultPrevented() || !c) return;
          if (u = this.getTipElement(), o = r.getUID(this.constructor.NAME), u.setAttribute("id", o), this.element.setAttribute("aria-describedby", o), this.setContent(), this.config.animation && i(u).addClass(nt.FADE), l = typeof this.config.placement == "function" ? this.config.placement.call(this, u, this.element) : this.config.placement, s = this._getAttachment(l), this.addAttachmentClass(s), a = this._getContainer(), i(u).data(this.constructor.DATA_KEY, this), i.contains(this.element.ownerDocument.documentElement, this.tip) || i(u).appendTo(a), i(this.element).trigger(this.constructor.Event.INSERTED), this._popper = new t(this.element, u, {
              placement: s,
              modifiers: {
                offset: {
                  offset: this.config.offset
                },
                flip: {
                  behavior: this.config.fallbackPlacement
                },
                arrow: {
                  element: vu.ARROW
                },
                preventOverflow: {
                  boundariesElement: this.config.boundary
                }
              },
              onCreate: function (t) {
                t.originalPlacement !== t.placement && n._handlePopperPlacementChange(t)
              },
              onUpdate: function (t) {
                return n._handlePopperPlacementChange(t)
              }
            }), i(u).addClass(nt.SHOW), "ontouchstart" in document.documentElement) i(document.body).children().on("mouseover", null, i.noop);
          h = function () {
            n.config.animation && n._fixTransition();
            var t = n._hoverState;
            n._hoverState = null;
            i(n.element).trigger(n.constructor.Event.SHOWN);
            t === ot.OUT && n._leave(null, n)
          };
          i(this.tip).hasClass(nt.FADE) ? (v = r.getTransitionDurationFromElement(this.tip), i(this.tip).one(r.TRANSITION_END, h).emulateTransitionEnd(v)) : h()
        }
      }, n.hide = function (n) {
        var t = this,
          u = this.getTipElement(),
          f = i.Event(this.constructor.Event.HIDE),
          e = function () {
            t._hoverState !== ot.SHOW && u.parentNode && u.parentNode.removeChild(u);
            t._cleanTipClass();
            t.element.removeAttribute("aria-describedby");
            i(t.element).trigger(t.constructor.Event.HIDDEN);
            t._popper !== null && t._popper.destroy();
            n && n()
          },
          o;
        (i(this.element).trigger(f), f.isDefaultPrevented()) || (i(u).removeClass(nt.SHOW), "ontouchstart" in document.documentElement && i(document.body).children().off("mouseover", null, i.noop), this._activeTrigger[tt.CLICK] = !1, this._activeTrigger[tt.FOCUS] = !1, this._activeTrigger[tt.HOVER] = !1, i(this.tip).hasClass(nt.FADE) ? (o = r.getTransitionDurationFromElement(u), i(u).one(r.TRANSITION_END, e).emulateTransitionEnd(o)) : e(), this._hoverState = "")
      }, n.update = function () {
        this._popper !== null && this._popper.scheduleUpdate()
      }, n.isWithContent = function () {
        return Boolean(this.getTitle())
      }, n.addAttachmentClass = function (n) {
        i(this.getTipElement()).addClass(au + "-" + n)
      }, n.getTipElement = function () {
        return this.tip = this.tip || i(this.config.template)[0], this.tip
      }, n.setContent = function () {
        var n = this.getTipElement();
        this.setElementContent(i(n.querySelectorAll(vu.TOOLTIP_INNER)), this.getTitle());
        i(n).removeClass(nt.FADE + " " + nt.SHOW)
      }, n.setElementContent = function (n, t) {
        var r = this.config.html;
        typeof t == "object" && (t.nodeType || t.jquery) ? r ? i(t).parent().is(n) || n.empty().append(t) : n.text(i(t).text()) : n[r ? "html" : "text"](t)
      }, n.getTitle = function () {
        var n = this.element.getAttribute("data-original-title");
        return n || (n = typeof this.config.title == "function" ? this.config.title.call(this.element) : this.config.title), n
      }, n._getContainer = function () {
        return this.config.container === !1 ? document.body : r.isElement(this.config.container) ? i(this.config.container) : i(document).find(this.config.container)
      }, n._getAttachment = function (n) {
        return ve[n.toUpperCase()]
      }, n._setListeners = function () {
        var n = this,
          t = this.config.trigger.split(" ");
        t.forEach(function (t) {
          if (t === "click") i(n.element).on(n.constructor.Event.CLICK, n.config.selector, function (t) {
            return n.toggle(t)
          });
          else if (t !== tt.MANUAL) {
            var r = t === tt.HOVER ? n.constructor.Event.MOUSEENTER : n.constructor.Event.FOCUSIN,
              u = t === tt.HOVER ? n.constructor.Event.MOUSELEAVE : n.constructor.Event.FOCUSOUT;
            i(n.element).on(r, n.config.selector, function (t) {
              return n._enter(t)
            }).on(u, n.config.selector, function (t) {
              return n._leave(t)
            })
          }
        });
        i(this.element).closest(".modal").on("hide.bs.modal", function () {
          n.element && n.hide()
        });
        this.config.selector ? this.config = o({}, this.config, {
          trigger: "manual",
          selector: ""
        }) : this._fixTitle()
      }, n._fixTitle = function () {
        var n = typeof this.element.getAttribute("data-original-title");
        (this.element.getAttribute("title") || n !== "string") && (this.element.setAttribute("data-original-title", this.element.getAttribute("title") || ""), this.element.setAttribute("title", ""))
      }, n._enter = function (n, t) {
        var r = this.constructor.DATA_KEY;
        if (t = t || i(n.currentTarget).data(r), t || (t = new this.constructor(n.currentTarget, this._getDelegateConfig()), i(n.currentTarget).data(r, t)), n && (t._activeTrigger[n.type === "focusin" ? tt.FOCUS : tt.HOVER] = !0), i(t.getTipElement()).hasClass(nt.SHOW) || t._hoverState === ot.SHOW) {
          t._hoverState = ot.SHOW;
          return
        }
        if (clearTimeout(t._timeout), t._hoverState = ot.SHOW, !t.config.delay || !t.config.delay.show) {
          t.show();
          return
        }
        t._timeout = setTimeout(function () {
          t._hoverState === ot.SHOW && t.show()
        }, t.config.delay.show)
      }, n._leave = function (n, t) {
        var r = this.constructor.DATA_KEY;
        if (t = t || i(n.currentTarget).data(r), t || (t = new this.constructor(n.currentTarget, this._getDelegateConfig()), i(n.currentTarget).data(r, t)), n && (t._activeTrigger[n.type === "focusout" ? tt.FOCUS : tt.HOVER] = !1), !t._isWithActiveTrigger()) {
          if (clearTimeout(t._timeout), t._hoverState = ot.OUT, !t.config.delay || !t.config.delay.hide) {
            t.hide();
            return
          }
          t._timeout = setTimeout(function () {
            t._hoverState === ot.OUT && t.hide()
          }, t.config.delay.hide)
        }
      }, n._isWithActiveTrigger = function () {
        for (var n in this._activeTrigger)
          if (this._activeTrigger[n]) return !0;
        return !1
      }, n._getConfig = function (n) {
        return n = o({}, this.constructor.Default, i(this.element).data(), typeof n == "object" && n ? n : {}), typeof n.delay == "number" && (n.delay = {
          show: n.delay,
          hide: n.delay
        }), typeof n.title == "number" && (n.title = n.title.toString()), typeof n.content == "number" && (n.content = n.content.toString()), r.typeCheckConfig(vt, n, this.constructor.DefaultType), n
      }, n._getDelegateConfig = function () {
        var t = {},
          n;
        if (this.config)
          for (n in this.config) this.constructor.Default[n] !== this.config[n] && (t[n] = this.config[n]);
        return t
      }, n._cleanTipClass = function () {
        var t = i(this.getTipElement()),
          n = t.attr("class").match(le);
        n !== null && n.length && t.removeClass(n.join(""))
      }, n._handlePopperPlacementChange = function (n) {
        var t = n.instance;
        this.tip = t.popper;
        this._cleanTipClass();
        this.addAttachmentClass(this._getAttachment(n.placement))
      }, n._fixTransition = function () {
        var n = this.getTipElement(),
          t = this.config.animation;
        n.getAttribute("x-placement") === null && (i(n).removeClass(nt.FADE), this.config.animation = !1, this.hide(), this.show(), this.config.animation = t)
      }, u._jQueryInterface = function (n) {
        return this.each(function () {
          var t = i(this).data(ur),
            r = typeof n == "object" && n;
          if ((t || !/dispose|hide/.test(n)) && (t || (t = new u(this, r), i(this).data(ur, t)), typeof n == "string")) {
            if (typeof t[n] == "undefined") throw new TypeError('No method named "' + n + '"');
            t[n]()
          }
        })
      }, p(u, null, [{
        key: "VERSION",
        get: function () {
          return he
        }
      }, {
        key: "Default",
        get: function () {
          return ye
        }
      }, {
        key: "NAME",
        get: function () {
          return vt
        }
      }, {
        key: "DATA_KEY",
        get: function () {
          return ur
        }
      }, {
        key: "Event",
        get: function () {
          return pe
        }
      }, {
        key: "EVENT_KEY",
        get: function () {
          return w
        }
      }, {
        key: "DefaultType",
        get: function () {
          return ae
        }
      }]), u
    }();
  i.fn[vt] = yt._jQueryInterface;
  i.fn[vt].Constructor = yt;
  i.fn[vt].noConflict = function () {
    return i.fn[vt] = ce, yt._jQueryInterface
  };
  var ii = "popover",
    we = "4.2.1",
    fr = "bs.popover",
    b = "." + fr,
    be = i.fn[ii],
    yu = "bs-popover",
    ke = new RegExp("(^|\\s)" + yu + "\\S+", "g"),
    de = o({}, yt.Default, {
      placement: "right",
      trigger: "click",
      content: "",
      template: '<div class="popover" role="tooltip"><div class="arrow"><\/div><h3 class="popover-header"><\/h3><div class="popover-body"><\/div><\/div>'
    }),
    ge = o({}, yt.DefaultType, {
      content: "(string|element|function)"
    }),
    pu = {
      FADE: "fade",
      SHOW: "show"
    },
    wu = {
      TITLE: ".popover-header",
      CONTENT: ".popover-body"
    },
    no = {
      HIDE: "hide" + b,
      HIDDEN: "hidden" + b,
      SHOW: "show" + b,
      SHOWN: "shown" + b,
      INSERTED: "inserted" + b,
      CLICK: "click" + b,
      FOCUSIN: "focusin" + b,
      FOCUSOUT: "focusout" + b,
      MOUSEENTER: "mouseenter" + b,
      MOUSELEAVE: "mouseleave" + b
    },
    er = function (n) {
      function t() {
        return n.apply(this, arguments) || this
      }
      du(t, n);
      var r = t.prototype;
      return r.isWithContent = function () {
        return this.getTitle() || this._getContent()
      }, r.addAttachmentClass = function (n) {
        i(this.getTipElement()).addClass(yu + "-" + n)
      }, r.getTipElement = function () {
        return this.tip = this.tip || i(this.config.template)[0], this.tip
      }, r.setContent = function () {
        var t = i(this.getTipElement()),
          n;
        this.setElementContent(t.find(wu.TITLE), this.getTitle());
        n = this._getContent();
        typeof n == "function" && (n = n.call(this.element));
        this.setElementContent(t.find(wu.CONTENT), n);
        t.removeClass(pu.FADE + " " + pu.SHOW)
      }, r._getContent = function () {
        return this.element.getAttribute("data-content") || this.config.content
      }, r._cleanTipClass = function () {
        var t = i(this.getTipElement()),
          n = t.attr("class").match(ke);
        n !== null && n.length > 0 && t.removeClass(n.join(""))
      }, t._jQueryInterface = function (n) {
        return this.each(function () {
          var r = i(this).data(fr),
            u = typeof n == "object" ? n : null;
          if ((r || !/dispose|hide/.test(n)) && (r || (r = new t(this, u), i(this).data(fr, r)), typeof n == "string")) {
            if (typeof r[n] == "undefined") throw new TypeError('No method named "' + n + '"');
            r[n]()
          }
        })
      }, p(t, null, [{
        key: "VERSION",
        get: function () {
          return we
        }
      }, {
        key: "Default",
        get: function () {
          return de
        }
      }, {
        key: "NAME",
        get: function () {
          return ii
        }
      }, {
        key: "DATA_KEY",
        get: function () {
          return fr
        }
      }, {
        key: "Event",
        get: function () {
          return no
        }
      }, {
        key: "EVENT_KEY",
        get: function () {
          return b
        }
      }, {
        key: "DefaultType",
        get: function () {
          return ge
        }
      }]), t
    }(yt);
  i.fn[ii] = er._jQueryInterface;
  i.fn[ii].Constructor = er;
  i.fn[ii].noConflict = function () {
    return i.fn[ii] = be, er._jQueryInterface
  };
  var pt = "scrollspy",
    to = "4.2.1",
    or = "bs.scrollspy",
    sr = "." + or,
    io = i.fn[pt],
    bu = {
      offset: 10,
      method: "auto",
      target: ""
    },
    ro = {
      offset: "number",
      method: "string",
      target: "(string|element)"
    },
    uu = {
      ACTIVATE: "activate" + sr,
      SCROLL: "scroll" + sr,
      LOAD_DATA_API: "load" + sr + ".data-api"
    },
    st = {
      DROPDOWN_ITEM: "dropdown-item",
      DROPDOWN_MENU: "dropdown-menu",
      ACTIVE: "active"
    },
    y = {
      DATA_SPY: '[data-spy="scroll"]',
      ACTIVE: ".active",
      NAV_LIST_GROUP: ".nav, .list-group",
      NAV_LINKS: ".nav-link",
      NAV_ITEMS: ".nav-item",
      LIST_ITEMS: ".list-group-item",
      DROPDOWN: ".dropdown",
      DROPDOWN_ITEMS: ".dropdown-item",
      DROPDOWN_TOGGLE: ".dropdown-toggle"
    },
    fu = {
      OFFSET: "offset",
      POSITION: "position"
    },
    pi = function () {
      function t(n, t) {
        var r = this;
        this._element = n;
        this._scrollElement = n.tagName === "BODY" ? window : n;
        this._config = this._getConfig(t);
        this._selector = this._config.target + " " + y.NAV_LINKS + "," + (this._config.target + " " + y.LIST_ITEMS + ",") + (this._config.target + " " + y.DROPDOWN_ITEMS);
        this._offsets = [];
        this._targets = [];
        this._activeTarget = null;
        this._scrollHeight = 0;
        i(this._scrollElement).on(uu.SCROLL, function (n) {
          return r._process(n)
        });
        this.refresh();
        this._process()
      }
      var n = t.prototype;
      return n.refresh = function () {
        var n = this,
          f = this._scrollElement === this._scrollElement.window ? fu.OFFSET : fu.POSITION,
          t = this._config.method === "auto" ? f : this._config.method,
          e = t === fu.POSITION ? this._getScrollTop() : 0,
          u;
        this._offsets = [];
        this._targets = [];
        this._scrollHeight = this._getScrollHeight();
        u = [].slice.call(document.querySelectorAll(this._selector));
        u.map(function (n) {
          var u, f = r.getSelectorFromElement(n),
            o;
          return (f && (u = document.querySelector(f)), u && (o = u.getBoundingClientRect(), o.width || o.height)) ? [i(u)[t]().top + e, f] : null
        }).filter(function (n) {
          return n
        }).sort(function (n, t) {
          return n[0] - t[0]
        }).forEach(function (t) {
          n._offsets.push(t[0]);
          n._targets.push(t[1])
        })
      }, n.dispose = function () {
        i.removeData(this._element, or);
        i(this._scrollElement).off(sr);
        this._element = null;
        this._scrollElement = null;
        this._config = null;
        this._selector = null;
        this._offsets = null;
        this._targets = null;
        this._activeTarget = null;
        this._scrollHeight = null
      }, n._getConfig = function (n) {
        if (n = o({}, bu, typeof n == "object" && n ? n : {}), typeof n.target != "string") {
          var t = i(n.target).attr("id");
          t || (t = r.getUID(pt), i(n.target).attr("id", t));
          n.target = "#" + t
        }
        return r.typeCheckConfig(pt, n, ro), n
      }, n._getScrollTop = function () {
        return this._scrollElement === window ? this._scrollElement.pageYOffset : this._scrollElement.scrollTop
      }, n._getScrollHeight = function () {
        return this._scrollElement.scrollHeight || Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)
      }, n._getOffsetHeight = function () {
        return this._scrollElement === window ? window.innerHeight : this._scrollElement.getBoundingClientRect().height
      }, n._process = function () {
        var t = this._getScrollTop() + this._config.offset,
          r = this._getScrollHeight(),
          e = this._config.offset + r - this._getOffsetHeight(),
          i, u, n, f;
        if (this._scrollHeight !== r && this.refresh(), t >= e) {
          i = this._targets[this._targets.length - 1];
          this._activeTarget !== i && this._activate(i);
          return
        }
        if (this._activeTarget && t < this._offsets[0] && this._offsets[0] > 0) {
          this._activeTarget = null;
          this._clear();
          return
        }
        for (u = this._offsets.length, n = u; n--;) f = this._activeTarget !== this._targets[n] && t >= this._offsets[n] && (typeof this._offsets[n + 1] == "undefined" || t < this._offsets[n + 1]), f && this._activate(this._targets[n])
      }, n._activate = function (n) {
        this._activeTarget = n;
        this._clear();
        var r = this._selector.split(",").map(function (t) {
            return t + '[data-target="' + n + '"],' + t + '[href="' + n + '"]'
          }),
          t = i([].slice.call(document.querySelectorAll(r.join(","))));
        t.hasClass(st.DROPDOWN_ITEM) ? (t.closest(y.DROPDOWN).find(y.DROPDOWN_TOGGLE).addClass(st.ACTIVE), t.addClass(st.ACTIVE)) : (t.addClass(st.ACTIVE), t.parents(y.NAV_LIST_GROUP).prev(y.NAV_LINKS + ", " + y.LIST_ITEMS).addClass(st.ACTIVE), t.parents(y.NAV_LIST_GROUP).prev(y.NAV_ITEMS).children(y.NAV_LINKS).addClass(st.ACTIVE));
        i(this._scrollElement).trigger(uu.ACTIVATE, {
          relatedTarget: n
        })
      }, n._clear = function () {
        [].slice.call(document.querySelectorAll(this._selector)).filter(function (n) {
          return n.classList.contains(st.ACTIVE)
        }).forEach(function (n) {
          return n.classList.remove(st.ACTIVE)
        })
      }, t._jQueryInterface = function (n) {
        return this.each(function () {
          var r = i(this).data(or),
            u = typeof n == "object" && n;
          if (r || (r = new t(this, u), i(this).data(or, r)), typeof n == "string") {
            if (typeof r[n] == "undefined") throw new TypeError('No method named "' + n + '"');
            r[n]()
          }
        })
      }, p(t, null, [{
        key: "VERSION",
        get: function () {
          return to
        }
      }, {
        key: "Default",
        get: function () {
          return bu
        }
      }]), t
    }();
  i(window).on(uu.LOAD_DATA_API, function () {
    for (var n, t = [].slice.call(document.querySelectorAll(y.DATA_SPY)), u = t.length, r = u; r--;) n = i(t[r]), pi._jQueryInterface.call(n, n.data())
  });
  i.fn[pt] = pi._jQueryInterface;
  i.fn[pt].Constructor = pi;
  i.fn[pt].noConflict = function () {
    return i.fn[pt] = io, pi._jQueryInterface
  };
  var wi = "tab",
    uo = "4.2.1",
    hr = "bs.tab",
    bi = "." + hr,
    fo = i.fn[wi],
    ki = {
      HIDE: "hide" + bi,
      HIDDEN: "hidden" + bi,
      SHOW: "show" + bi,
      SHOWN: "shown" + bi,
      CLICK_DATA_API: "click" + bi + ".data-api"
    },
    it = {
      DROPDOWN_MENU: "dropdown-menu",
      ACTIVE: "active",
      DISABLED: "disabled",
      FADE: "fade",
      SHOW: "show"
    },
    ft = {
      DROPDOWN: ".dropdown",
      NAV_LIST_GROUP: ".nav, .list-group",
      ACTIVE: ".active",
      ACTIVE_UL: "> li > .active",
      DATA_TOGGLE: '[data-toggle="tab"], [data-toggle="pill"], [data-toggle="list"]',
      DROPDOWN_TOGGLE: ".dropdown-toggle",
      DROPDOWN_ACTIVE_CHILD: "> .dropdown-menu .active"
    },
    di = function () {
      function n(n) {
        this._element = n
      }
      var t = n.prototype;
      return t.show = function () {
        var h = this,
          u, n, t, f, c, e, o, s;
        this._element.parentNode && this._element.parentNode.nodeType === Node.ELEMENT_NODE && i(this._element).hasClass(it.ACTIVE) || i(this._element).hasClass(it.DISABLED) || (t = i(this._element).closest(ft.NAV_LIST_GROUP)[0], f = r.getSelectorFromElement(this._element), t && (c = t.nodeName === "UL" || t.nodeName === "OL" ? ft.ACTIVE_UL : ft.ACTIVE, n = i.makeArray(i(t).find(c)), n = n[n.length - 1]), e = i.Event(ki.HIDE, {
          relatedTarget: this._element
        }), o = i.Event(ki.SHOW, {
          relatedTarget: n
        }), n && i(n).trigger(e), i(this._element).trigger(o), o.isDefaultPrevented() || e.isDefaultPrevented()) || (f && (u = document.querySelector(f)), this._activate(this._element, t), s = function () {
          var t = i.Event(ki.HIDDEN, {
              relatedTarget: h._element
            }),
            r = i.Event(ki.SHOWN, {
              relatedTarget: n
            });
          i(n).trigger(t);
          i(h._element).trigger(r)
        }, u ? this._activate(u, u.parentNode, s) : s())
      }, t.dispose = function () {
        i.removeData(this._element, hr);
        this._element = null
      }, t._activate = function (n, t, u) {
        var s = this,
          h = t && (t.nodeName === "UL" || t.nodeName === "OL") ? i(t).find(ft.ACTIVE_UL) : i(t).children(ft.ACTIVE),
          f = h[0],
          c = u && f && i(f).hasClass(it.FADE),
          e = function () {
            return s._transitionComplete(n, f, u)
          },
          o;
        f && c ? (o = r.getTransitionDurationFromElement(f), i(f).removeClass(it.SHOW).one(r.TRANSITION_END, e).emulateTransitionEnd(o)) : e()
      }, t._transitionComplete = function (n, t, u) {
        var f, e, o;
        t && (i(t).removeClass(it.ACTIVE), f = i(t.parentNode).find(ft.DROPDOWN_ACTIVE_CHILD)[0], f && i(f).removeClass(it.ACTIVE), t.getAttribute("role") === "tab" && t.setAttribute("aria-selected", !1));
        i(n).addClass(it.ACTIVE);
        n.getAttribute("role") === "tab" && n.setAttribute("aria-selected", !0);
        r.reflow(n);
        i(n).addClass(it.SHOW);
        n.parentNode && i(n.parentNode).hasClass(it.DROPDOWN_MENU) && (e = i(n).closest(ft.DROPDOWN)[0], e && (o = [].slice.call(e.querySelectorAll(ft.DROPDOWN_TOGGLE)), i(o).addClass(it.ACTIVE)), n.setAttribute("aria-expanded", !0));
        u && u()
      }, n._jQueryInterface = function (t) {
        return this.each(function () {
          var u = i(this),
            r = u.data(hr);
          if (r || (r = new n(this), u.data(hr, r)), typeof t == "string") {
            if (typeof r[t] == "undefined") throw new TypeError('No method named "' + t + '"');
            r[t]()
          }
        })
      }, p(n, null, [{
        key: "VERSION",
        get: function () {
          return uo
        }
      }]), n
    }();
  i(document).on(ki.CLICK_DATA_API, ft.DATA_TOGGLE, function (n) {
    n.preventDefault();
    di._jQueryInterface.call(i(this), "show")
  });
  i.fn[wi] = di._jQueryInterface;
  i.fn[wi].Constructor = di;
  i.fn[wi].noConflict = function () {
    return i.fn[wi] = fo, di._jQueryInterface
  };
  var ri = "toast",
    eo = "4.2.1",
    cr = "bs.toast",
    gi = "." + cr,
    oo = i.fn[ri],
    ui = {
      CLICK_DISMISS: "click.dismiss" + gi,
      HIDE: "hide" + gi,
      HIDDEN: "hidden" + gi,
      SHOW: "show" + gi,
      SHOWN: "shown" + gi
    },
    rt = {
      FADE: "fade",
      HIDE: "hide",
      SHOW: "show",
      SHOWING: "showing"
    },
    so = {
      animation: "boolean",
      autohide: "boolean",
      delay: "number"
    },
    ho = {
      animation: !0,
      autohide: !0,
      delay: 500
    },
    co = {
      DATA_DISMISS: '[data-dismiss="toast"]'
    },
    lr = function () {
      function t(n, t) {
        this._element = n;
        this._config = this._getConfig(t);
        this._timeout = null;
        this._setListeners()
      }
      var n = t.prototype;
      return n.show = function () {
        var n = this,
          t, u;
        i(this._element).trigger(ui.SHOW);
        this._config.animation && this._element.classList.add(rt.FADE);
        t = function () {
          n._element.classList.remove(rt.SHOWING);
          n._element.classList.add(rt.SHOW);
          i(n._element).trigger(ui.SHOWN);
          n._config.autohide && n.hide()
        };
        this._element.classList.remove(rt.HIDE);
        this._element.classList.add(rt.SHOWING);
        this._config.animation ? (u = r.getTransitionDurationFromElement(this._element), i(this._element).one(r.TRANSITION_END, t).emulateTransitionEnd(u)) : t()
      }, n.hide = function (n) {
        var t = this;
        this._element.classList.contains(rt.SHOW) && (i(this._element).trigger(ui.HIDE), n ? this._close() : this._timeout = setTimeout(function () {
          t._close()
        }, this._config.delay))
      }, n.dispose = function () {
        clearTimeout(this._timeout);
        this._timeout = null;
        this._element.classList.contains(rt.SHOW) && this._element.classList.remove(rt.SHOW);
        i(this._element).off(ui.CLICK_DISMISS);
        i.removeData(this._element, cr);
        this._element = null;
        this._config = null
      }, n._getConfig = function (n) {
        return n = o({}, ho, i(this._element).data(), typeof n == "object" && n ? n : {}), r.typeCheckConfig(ri, n, this.constructor.DefaultType), n
      }, n._setListeners = function () {
        var n = this;
        i(this._element).on(ui.CLICK_DISMISS, co.DATA_DISMISS, function () {
          return n.hide(!0)
        })
      }, n._close = function () {
        var n = this,
          t = function () {
            n._element.classList.add(rt.HIDE);
            i(n._element).trigger(ui.HIDDEN)
          },
          u;
        this._element.classList.remove(rt.SHOW);
        this._config.animation ? (u = r.getTransitionDurationFromElement(this._element), i(this._element).one(r.TRANSITION_END, t).emulateTransitionEnd(u)) : t()
      }, t._jQueryInterface = function (n) {
        return this.each(function () {
          var u = i(this),
            r = u.data(cr),
            f = typeof n == "object" && n;
          if (r || (r = new t(this, f), u.data(cr, r)), typeof n == "string") {
            if (typeof r[n] == "undefined") throw new TypeError('No method named "' + n + '"');
            r[n](this)
          }
        })
      }, p(t, null, [{
        key: "VERSION",
        get: function () {
          return eo
        }
      }, {
        key: "DefaultType",
        get: function () {
          return so
        }
      }]), t
    }();
  i.fn[ri] = lr._jQueryInterface;
  i.fn[ri].Constructor = lr;
  i.fn[ri].noConflict = function () {
      return i.fn[ri] = oo, lr._jQueryInterface
    },
    function () {
      if (typeof i == "undefined") throw new TypeError("Bootstrap's JavaScript requires jQuery. jQuery must be included before Bootstrap's JavaScript.");
      var n = i.fn.jquery.split(" ")[0].split("."),
        t = 9;
      if (n[0] < 2 && n[1] < t || n[0] === 1 && n[1] === t && n[2] < 1 || n[0] >= 4) throw new Error("Bootstrap's JavaScript requires at least jQuery v1.9.1 but less than v4.0.0");
    }();
  n.Util = r;
  n.Alert = wt;
  n.Button = oi;
  n.Carousel = kt;
  n.Collapse = li;
  n.Dropdown = et;
  n.Modal = yi;
  n.Popover = er;
  n.Scrollspy = pi;
  n.Tab = di;
  n.Toast = lr;
  n.Tooltip = yt;
  Object.defineProperty(n, "__esModule", {
    value: !0
  })
}),
function (n) {
  typeof define == "function" && define.amd ? define(["jquery"], function (t) {
    return n(t)
  }) : typeof module == "object" && typeof module.exports == "object" ? exports = n(require("jquery")) : n(jQuery)
}(function (n) {
  function o(n) {
    var i = 7.5625,
      t = 2.75;
    return n < 1 / t ? i * n * n : n < 2 / t ? i * (n -= 1.5 / t) * n + .75 : n < 2.5 / t ? i * (n -= 2.25 / t) * n + .9375 : i * (n -= 2.625 / t) * n + .984375
  }
  n.easing.jswing = n.easing.swing;
  var t = Math.pow,
    u = Math.sqrt,
    i = Math.sin,
    s = Math.cos,
    r = Math.PI,
    f = 1.70158,
    e = f * 1.525,
    h = f + 1,
    c = 2 * r / 3,
    l = 2 * r / 4.5;
  n.extend(n.easing, {
    def: "easeOutQuad",
    swing: function (t) {
      return n.easing[n.easing.def](t)
    },
    easeInQuad: function (n) {
      return n * n
    },
    easeOutQuad: function (n) {
      return 1 - (1 - n) * (1 - n)
    },
    easeInOutQuad: function (n) {
      return n < .5 ? 2 * n * n : 1 - t(-2 * n + 2, 2) / 2
    },
    easeInCubic: function (n) {
      return n * n * n
    },
    easeOutCubic: function (n) {
      return 1 - t(1 - n, 3)
    },
    easeInOutCubic: function (n) {
      return n < .5 ? 4 * n * n * n : 1 - t(-2 * n + 2, 3) / 2
    },
    easeInQuart: function (n) {
      return n * n * n * n
    },
    easeOutQuart: function (n) {
      return 1 - t(1 - n, 4)
    },
    easeInOutQuart: function (n) {
      return n < .5 ? 8 * n * n * n * n : 1 - t(-2 * n + 2, 4) / 2
    },
    easeInQuint: function (n) {
      return n * n * n * n * n
    },
    easeOutQuint: function (n) {
      return 1 - t(1 - n, 5)
    },
    easeInOutQuint: function (n) {
      return n < .5 ? 16 * n * n * n * n * n : 1 - t(-2 * n + 2, 5) / 2
    },
    easeInSine: function (n) {
      return 1 - s(n * r / 2)
    },
    easeOutSine: function (n) {
      return i(n * r / 2)
    },
    easeInOutSine: function (n) {
      return -(s(r * n) - 1) / 2
    },
    easeInExpo: function (n) {
      return n === 0 ? 0 : t(2, 10 * n - 10)
    },
    easeOutExpo: function (n) {
      return n === 1 ? 1 : 1 - t(2, -10 * n)
    },
    easeInOutExpo: function (n) {
      return n === 0 ? 0 : n === 1 ? 1 : n < .5 ? t(2, 20 * n - 10) / 2 : (2 - t(2, -20 * n + 10)) / 2
    },
    easeInCirc: function (n) {
      return 1 - u(1 - t(n, 2))
    },
    easeOutCirc: function (n) {
      return u(1 - t(n - 1, 2))
    },
    easeInOutCirc: function (n) {
      return n < .5 ? (1 - u(1 - t(2 * n, 2))) / 2 : (u(1 - t(-2 * n + 2, 2)) + 1) / 2
    },
    easeInElastic: function (n) {
      return n === 0 ? 0 : n === 1 ? 1 : -t(2, 10 * n - 10) * i((n * 10 - 10.75) * c)
    },
    easeOutElastic: function (n) {
      return n === 0 ? 0 : n === 1 ? 1 : t(2, -10 * n) * i((n * 10 - .75) * c) + 1
    },
    easeInOutElastic: function (n) {
      return n === 0 ? 0 : n === 1 ? 1 : n < .5 ? -(t(2, 20 * n - 10) * i((20 * n - 11.125) * l)) / 2 : t(2, -20 * n + 10) * i((20 * n - 11.125) * l) / 2 + 1
    },
    easeInBack: function (n) {
      return h * n * n * n - f * n * n
    },
    easeOutBack: function (n) {
      return 1 + h * t(n - 1, 3) + f * t(n - 1, 2)
    },
    easeInOutBack: function (n) {
      return n < .5 ? t(2 * n, 2) * ((e + 1) * 2 * n - e) / 2 : (t(2 * n - 2, 2) * ((e + 1) * (n * 2 - 2) + e) + 2) / 2
    },
    easeInBounce: function (n) {
      return 1 - o(1 - n)
    },
    easeOutBounce: o,
    easeInOutBounce: function (n) {
      return n < .5 ? (1 - o(1 - 2 * n)) / 2 : (1 + o(2 * n - 1)) / 2
    }
  })
});
! function () {
  "use strict";

  function t(r) {
    return "undefined" == typeof this || Object.getPrototypeOf(this) !== t.prototype ? new t(r) : (n = this, n.version = "3.3.6", n.tools = new i, n.isSupported() ? (n.tools.extend(n.defaults, r || {}), n.defaults.container = f(n.defaults), n.store = {
      elements: {},
      containers: []
    }, n.sequences = {}, n.history = [], n.uid = 0, n.initialized = !1) : "undefined" != typeof console && null !== console, n)
  }

  function f(t) {
    if (t && t.container) {
      if ("string" == typeof t.container) return window.document.documentElement.querySelector(t.container);
      if (n.tools.isNode(t.container)) return t.container
    }
    return n.defaults.container
  }

  function y(t, i) {
    return "string" == typeof t ? Array.prototype.slice.call(i.querySelectorAll(t)) : n.tools.isNode(t) ? [t] : n.tools.isNodeList(t) ? Array.prototype.slice.call(t) : []
  }

  function e() {
    return ++n.uid
  }

  function p(t, i, r) {
    i.container && (i.container = r);
    t.config = t.config ? n.tools.extendClone(t.config, i) : n.tools.extendClone(n.defaults, i);
    t.config.axis = "top" === t.config.origin || "bottom" === t.config.origin ? "Y" : "X"
  }

  function w(n) {
    var t = window.getComputedStyle(n.domEl);
    n.styles || (n.styles = {
      transition: {},
      transform: {},
      computed: {}
    }, n.styles.inline = n.domEl.getAttribute("style") || "", n.styles.inline += "; visibility: visible; ", n.styles.computed.opacity = t.opacity, n.styles.computed.transition = t.transition && "all 0s ease 0s" !== t.transition ? t.transition + ", " : "");
    n.styles.transition.instant = o(n, 0);
    n.styles.transition.delayed = o(n, n.config.delay);
    n.styles.transform.initial = " -webkit-transform:";
    n.styles.transform.target = " -webkit-transform:";
    s(n);
    n.styles.transform.initial += "transform:";
    n.styles.transform.target += "transform:";
    s(n)
  }

  function o(n, t) {
    var i = n.config;
    return "-webkit-transition: " + n.styles.computed.transition + "-webkit-transform " + i.duration / 1e3 + "s " + i.easing + " " + t / 1e3 + "s, opacity " + i.duration / 1e3 + "s " + i.easing + " " + t / 1e3 + "s; transition: " + n.styles.computed.transition + "transform " + i.duration / 1e3 + "s " + i.easing + " " + t / 1e3 + "s, opacity " + i.duration / 1e3 + "s " + i.easing + " " + t / 1e3 + "s; "
  }

  function s(n) {
    var r, t = n.config,
      i = n.styles.transform;
    r = "top" === t.origin || "left" === t.origin ? /^-/.test(t.distance) ? t.distance.substr(1) : "-" + t.distance : t.distance;
    parseInt(t.distance) && (i.initial += " translate" + t.axis + "(" + r + ")", i.target += " translate" + t.axis + "(0)");
    t.scale && (i.initial += " scale(" + t.scale + ")", i.target += " scale(1)");
    t.rotate.x && (i.initial += " rotateX(" + t.rotate.x + "deg)", i.target += " rotateX(0)");
    t.rotate.y && (i.initial += " rotateY(" + t.rotate.y + "deg)", i.target += " rotateY(0)");
    t.rotate.z && (i.initial += " rotateZ(" + t.rotate.z + "deg)", i.target += " rotateZ(0)");
    i.initial += "; opacity: " + t.opacity + ";";
    i.target += "; opacity: " + n.styles.computed.opacity + ";"
  }

  function b(t) {
    var i = t.config.container;
    i && n.store.containers.indexOf(i) === -1 && n.store.containers.push(t.config.container);
    n.store.elements[t.id] = t
  }

  function k(t, i, r) {
    var u = {
      target: t,
      config: i,
      interval: r
    };
    n.history.push(u)
  }

  function h() {
    if (n.isSupported()) {
      c();
      for (var t = 0; t < n.store.containers.length; t++) n.store.containers[t].addEventListener("scroll", r), n.store.containers[t].addEventListener("resize", r);
      n.initialized || (window.addEventListener("scroll", r), window.addEventListener("resize", r), n.initialized = !0)
    }
    return n
  }

  function r() {
    v(c)
  }

  function d() {
    var t, r, f, i;
    n.tools.forOwn(n.sequences, function (e) {
      i = n.sequences[e];
      t = !1;
      for (var o = 0; o < i.elemIds.length; o++) f = i.elemIds[o], r = n.store.elements[f], u(r) && !t && (t = !0);
      i.active = t
    })
  }

  function c() {
    var i, t;
    d();
    n.tools.forOwn(n.store.elements, function (r) {
      t = n.store.elements[r];
      i = tt(t);
      nt(t) ? (t.config.beforeReveal(t.domEl), i ? t.domEl.setAttribute("style", t.styles.inline + t.styles.transform.target + t.styles.transition.delayed) : t.domEl.setAttribute("style", t.styles.inline + t.styles.transform.target + t.styles.transition.instant), l("reveal", t, i), t.revealing = !0, t.seen = !0, t.sequence && g(t, i)) : it(t) && (t.config.beforeReset(t.domEl), t.domEl.setAttribute("style", t.styles.inline + t.styles.transform.initial + t.styles.transition.instant), l("reset", t), t.revealing = !1)
    })
  }

  function g(t, i) {
    var f = 0,
      e = 0,
      u = n.sequences[t.sequence.id];
    u.blocked = !0;
    i && "onload" === t.config.useDelay && (e = t.config.delay);
    t.sequence.timer && (f = Math.abs(t.sequence.timer.started - new Date), window.clearTimeout(t.sequence.timer));
    t.sequence.timer = {
      started: new Date
    };
    t.sequence.timer.clock = window.setTimeout(function () {
      u.blocked = !1;
      t.sequence.timer = null;
      r()
    }, Math.abs(u.interval) + e - f)
  }

  function l(n, t, i) {
    var f = 0,
      r = 0,
      u = "after";
    switch (n) {
      case "reveal":
        r = t.config.duration;
        i && (r += t.config.delay);
        u += "Reveal";
        break;
      case "reset":
        r = t.config.duration;
        u += "Reset"
    }
    t.timer && (f = Math.abs(t.timer.started - new Date), window.clearTimeout(t.timer.clock));
    t.timer = {
      started: new Date
    };
    t.timer.clock = window.setTimeout(function () {
      t.config[u](t.domEl);
      t.timer = null
    }, r - f)
  }

  function nt(t) {
    if (t.sequence) {
      var i = n.sequences[t.sequence.id];
      return i.active && !i.blocked && !t.revealing && !t.disabled
    }
    return u(t) && !t.revealing && !t.disabled
  }

  function tt(t) {
    var i = t.config.useDelay;
    return "always" === i || "onload" === i && !n.initialized || "once" === i && !t.seen
  }

  function it(t) {
    if (t.sequence) {
      var i = n.sequences[t.sequence.id];
      return !i.active && t.config.reset && t.revealing && !t.disabled
    }
    return !u(t) && t.config.reset && t.revealing && !t.disabled
  }

  function rt(n) {
    return {
      width: n.clientWidth,
      height: n.clientHeight
    }
  }

  function ut(n) {
    if (n && n !== window.document.documentElement) {
      var t = a(n);
      return {
        x: n.scrollLeft + t.left,
        y: n.scrollTop + t.top
      }
    }
    return {
      x: window.pageXOffset,
      y: window.pageYOffset
    }
  }

  function a(n) {
    var t = 0,
      i = 0,
      r = n.offsetHeight,
      u = n.offsetWidth;
    do isNaN(n.offsetTop) || (t += n.offsetTop), isNaN(n.offsetLeft) || (i += n.offsetLeft), n = n.offsetParent; while (n);
    return {
      top: t,
      left: i,
      height: r,
      width: u
    }
  }

  function u(n) {
    function h() {
      var t = o + u * r,
        h = s + f * r,
        c = l - u * r,
        a = v - f * r,
        y = i.y + n.config.viewOffset.top,
        p = i.x + n.config.viewOffset.left,
        w = i.y - n.config.viewOffset.bottom + e.height,
        b = i.x - n.config.viewOffset.right + e.width;
      return t < w && c > y && h < b && a > p
    }

    function c() {
      return "fixed" === window.getComputedStyle(n.domEl).position
    }
    var t = a(n.domEl),
      e = rt(n.config.container),
      i = ut(n.config.container),
      r = n.config.viewFactor,
      u = t.height,
      f = t.width,
      o = t.top,
      s = t.left,
      l = o + u,
      v = s + f;
    return h() || c()
  }

  function i() {}
  var n, v;
  t.prototype.defaults = {
    origin: "bottom",
    distance: "20px",
    duration: 500,
    delay: 0,
    rotate: {
      x: 0,
      y: 0,
      z: 0
    },
    opacity: 0,
    scale: .9,
    easing: "cubic-bezier(0.6, 0.2, 0.1, 1)",
    container: window.document.documentElement,
    mobile: !0,
    reset: !1,
    useDelay: "always",
    viewFactor: .2,
    viewOffset: {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
    },
    beforeReveal: function () {},
    beforeReset: function () {},
    afterReveal: function () {},
    afterReset: function () {}
  };
  t.prototype.isSupported = function () {
    var n = document.documentElement.style;
    return "WebkitTransition" in n && "WebkitTransform" in n || "transition" in n && "transform" in n
  };
  t.prototype.reveal = function (t, i, r, u) {
    var a, s, o, v, c, d, l;
    if (void 0 !== i && "number" == typeof i ? (r = i, i = {}) : void 0 !== i && null !== i || (i = {}), a = f(i), s = y(t, a), !s.length) return n;
    for (r && "number" == typeof r && (d = e(), c = n.sequences[d] = {
        id: d,
        interval: r,
        elemIds: [],
        active: !1
      }), l = 0; l < s.length; l++) v = s[l].getAttribute("data-sr-id"), v ? o = n.store.elements[v] : (o = {
      id: e(),
      domEl: s[l],
      seen: !1,
      revealing: !1
    }, o.domEl.setAttribute("data-sr-id", o.id)), c && (o.sequence = {
      id: c.id,
      index: c.elemIds.length
    }, c.elemIds.push(o.id)), p(o, i, a), w(o), b(o), n.tools.isMobile() && !o.config.mobile || !n.isSupported() ? (o.domEl.setAttribute("style", o.styles.inline), o.disabled = !0) : o.revealing || o.domEl.setAttribute("style", o.styles.inline + o.styles.transform.initial);
    return !u && n.isSupported() && (k(t, i, r), n.initTimeout && window.clearTimeout(n.initTimeout), n.initTimeout = window.setTimeout(h, 0)), n
  };
  t.prototype.sync = function () {
    var t, i;
    if (n.history.length && n.isSupported()) {
      for (t = 0; t < n.history.length; t++) i = n.history[t], n.reveal(i.target, i.config, i.interval, !0);
      h()
    }
    return n
  };
  i.prototype.isObject = function (n) {
    return null !== n && "object" == typeof n && n.constructor === Object
  };
  i.prototype.isNode = function (n) {
    return "object" == typeof Node ? n instanceof window.Node : n && "object" == typeof n && "number" == typeof n.nodeType && "string" == typeof n.nodeName
  };
  i.prototype.isNodeList = function (n) {
    var t = Object.prototype.toString.call(n);
    return "object" == typeof NodeList ? n instanceof window.NodeList : n && "object" == typeof n && /^\[object (HTMLCollection|NodeList|Object)\]$/.test(t) && "number" == typeof n.length && (0 === n.length || this.isNode(n[0]))
  };
  i.prototype.forOwn = function (n, t) {
    if (!this.isObject(n)) throw new TypeError('Expected "object", but received "' + typeof n + '".');
    for (var i in n) n.hasOwnProperty(i) && t(i)
  };
  i.prototype.extend = function (n, t) {
    return this.forOwn(t, function (i) {
      this.isObject(t[i]) ? (n[i] && this.isObject(n[i]) || (n[i] = {}), this.extend(n[i], t[i])) : n[i] = t[i]
    }.bind(this)), n
  };
  i.prototype.extendClone = function (n, t) {
    return this.extend(this.extend({}, n), t)
  };
  i.prototype.isMobile = function () {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent)
  };
  v = window.requestAnimationFrame || window.webkitRequestAnimationFrame || window.mozRequestAnimationFrame || function (n) {
    window.setTimeout(n, 1e3 / 60)
  };
  "function" == typeof define && "object" == typeof define.amd && define.amd ? define(function () {
    return t
  }) : "undefined" != typeof module && module.exports ? module.exports = t : window.ScrollReveal = t
}();
/*! Magnific Popup - v1.1.0 - 2016-02-20
 * http://dimsemenov.com/plugins/magnific-popup/
 * Copyright (c) 2016 Dmitry Semenov; */
(function (n) {
  typeof define == "function" && define.amd ? define(["jquery"], n) : typeof exports == "object" ? n(require("jquery")) : n(window.jQuery || window.Zepto)
})(function (n) {
  var o = "Close",
    pt = "BeforeClose",
    ti = "AfterClose",
    ii = "BeforeAppend",
    it = "MarkupParse",
    rt = "Open",
    wt = "Change",
    ut = "mfp",
    u = "." + ut,
    p = "mfp-ready",
    bt = "mfp-removing",
    ft = "mfp-prevent-close",
    t, w = function () {},
    et = !!window.jQuery,
    ot, s = n(window),
    f, b, h, kt, r = function (n, i) {
      t.ev.on(ut + n + u, i)
    },
    l = function (t, i, r, u) {
      var f = document.createElement("div");
      return f.className = "mfp-" + t, r && (f.innerHTML = r), u ? i && i.appendChild(f) : (f = n(f), i && f.appendTo(i)), f
    },
    i = function (i, r) {
      t.ev.triggerHandler(ut + i, r);
      t.st.callbacks && (i = i.charAt(0).toLowerCase() + i.slice(1), t.st.callbacks[i] && t.st.callbacks[i].apply(t, n.isArray(r) ? r : [r]))
    },
    st = function (i) {
      return i === kt && t.currTemplate.closeBtn || (t.currTemplate.closeBtn = n(t.st.closeMarkup.replace("%title%", t.st.tClose)), kt = i), t.currTemplate.closeBtn
    },
    ht = function () {
      n.magnificPopup.instance || (t = new w, t.init(), n.magnificPopup.instance = t)
    },
    ri = function () {
      var n = document.createElement("p").style,
        t = ["ms", "O", "Moz", "Webkit"];
      if (n.transition !== undefined) return !0;
      while (t.length)
        if (t.pop() + "Transition" in n) return !0;
      return !1
    },
    k, a, d, g, ct, e, gt, at, ni, nt, yt, tt;
  w.prototype = {
    constructor: w,
    init: function () {
      var i = navigator.appVersion;
      t.isLowIE = t.isIE8 = document.all && !document.addEventListener;
      t.isAndroid = /android/gi.test(i);
      t.isIOS = /iphone|ipad|ipod/gi.test(i);
      t.supportsTransition = ri();
      t.probablyMobile = t.isAndroid || t.isIOS || /(Opera Mini)|Kindle|webOS|BlackBerry|(Opera Mobi)|(Windows Phone)|IEMobile/i.test(navigator.userAgent);
      f = n(document);
      t.popupsCache = {}
    },
    open: function (e) {
      var o, w, c, b, a, k, v, d, y;
      if (e.isObj === !1) {
        for (t.items = e.items.toArray(), t.index = 0, w = e.items, o = 0; o < w.length; o++)
          if (c = w[o], c.parsed && (c = c.el[0]), c === e.el[0]) {
            t.index = o;
            break
          }
      } else t.items = n.isArray(e.items) ? e.items : [e.items], t.index = e.index || 0;
      if (t.isOpen) {
        t.updateItemHTML();
        return
      }
      for (t.types = [], h = "", t.ev = e.mainEl && e.mainEl.length ? e.mainEl.eq(0) : f, e.key ? (t.popupsCache[e.key] || (t.popupsCache[e.key] = {}), t.currTemplate = t.popupsCache[e.key]) : t.currTemplate = {}, t.st = n.extend(!0, {}, n.magnificPopup.defaults, e), t.fixedContentPos = t.st.fixedContentPos === "auto" ? !t.probablyMobile : t.st.fixedContentPos, t.st.modal && (t.st.closeOnContentClick = !1, t.st.closeOnBgClick = !1, t.st.showCloseBtn = !1, t.st.enableEscapeKey = !1), t.bgOverlay || (t.bgOverlay = l("bg").on("click" + u, function () {
          t.close()
        }), t.wrap = l("wrap").attr("tabindex", -1).on("click" + u, function (n) {
          t._checkIfClose(n.target) && t.close()
        }), t.container = l("container", t.wrap)), t.contentContainer = l("content"), t.st.preloader && (t.preloader = l("preloader", t.container, t.st.tLoading)), b = n.magnificPopup.modules, o = 0; o < b.length; o++) a = b[o], a = a.charAt(0).toUpperCase() + a.slice(1), t["init" + a].call(t);
      if (i("BeforeOpen"), t.st.showCloseBtn && (t.st.closeBtnInside ? (r(it, function (n, t, i, r) {
          i.close_replaceWith = st(r.type)
        }), h += " mfp-close-btn-in") : t.wrap.append(st())), t.st.alignTop && (h += " mfp-align-top"), t.fixedContentPos ? t.wrap.css({
          overflow: t.st.overflowY,
          overflowX: "hidden",
          overflowY: t.st.overflowY
        }) : t.wrap.css({
          top: s.scrollTop(),
          position: "absolute"
        }), t.st.fixedBgPos !== !1 && (t.st.fixedBgPos !== "auto" || t.fixedContentPos) || t.bgOverlay.css({
          height: f.height(),
          position: "absolute"
        }), t.st.enableEscapeKey) f.on("keyup" + u, function (n) {
        n.keyCode === 27 && t.close()
      });
      s.on("resize" + u, function () {
        t.updateSize()
      });
      return t.st.closeOnContentClick || (h += " mfp-auto-cursor"), h && t.wrap.addClass(h), k = t.wH = s.height(), v = {}, t.fixedContentPos && t._hasScrollBar(k) && (d = t._getScrollbarSize(), d && (v.marginRight = d)), t.fixedContentPos && (t.isIE7 ? n("body, html").css("overflow", "hidden") : v.overflow = "hidden"), y = t.st.mainClass, t.isIE7 && (y += " mfp-ie7"), y && t._addClassToMFP(y), t.updateItemHTML(), i("BuildControls"), n("html").css(v), t.bgOverlay.add(t.wrap).prependTo(t.st.prependTo || n(document.body)), t._lastFocusedEl = document.activeElement, setTimeout(function () {
        t.content ? (t._addClassToMFP(p), t._setFocus()) : t.bgOverlay.addClass(p);
        f.on("focusin" + u, t._onFocusIn)
      }, 16), t.isOpen = !0, t.updateSize(k), i(rt), e
    },
    close: function () {
      t.isOpen && (i(pt), t.isOpen = !1, t.st.removalDelay && !t.isLowIE && t.supportsTransition ? (t._addClassToMFP(bt), setTimeout(function () {
        t._close()
      }, t.st.removalDelay)) : t._close())
    },
    _close: function () {
      var r, e;
      i(o);
      r = bt + " " + p + " ";
      t.bgOverlay.detach();
      t.wrap.detach();
      t.container.empty();
      t.st.mainClass && (r += t.st.mainClass + " ");
      t._removeClassFromMFP(r);
      t.fixedContentPos && (e = {
        marginRight: ""
      }, t.isIE7 ? n("body, html").css("overflow", "") : e.overflow = "", n("html").css(e));
      f.off("keyup" + u + " focusin" + u);
      t.ev.off(u);
      t.wrap.attr("class", "mfp-wrap").removeAttr("style");
      t.bgOverlay.attr("class", "mfp-bg");
      t.container.attr("class", "mfp-container");
      t.st.showCloseBtn && (!t.st.closeBtnInside || t.currTemplate[t.currItem.type] === !0) && t.currTemplate.closeBtn && t.currTemplate.closeBtn.detach();
      t.st.autoFocusLast && t._lastFocusedEl && n(t._lastFocusedEl).focus();
      t.currItem = null;
      t.content = null;
      t.currTemplate = null;
      t.prevHeight = 0;
      i(ti)
    },
    updateSize: function (n) {
      if (t.isIOS) {
        var u = document.documentElement.clientWidth / window.innerWidth,
          r = window.innerHeight * u;
        t.wrap.css("height", r);
        t.wH = r
      } else t.wH = n || s.height();
      t.fixedContentPos || t.wrap.css("height", t.wH);
      i("Resize")
    },
    updateItemHTML: function () {
      var u = t.items[t.index],
        r, f, e;
      t.contentContainer.detach();
      t.content && t.content.detach();
      u.parsed || (u = t.parseEl(t.index));
      r = u.type;
      i("BeforeChange", [t.currItem ? t.currItem.type : "", r]);
      t.currItem = u;
      t.currTemplate[r] || (f = t.st[r] ? t.st[r].markup : !1, i("FirstMarkupParse", f), t.currTemplate[r] = f ? n(f) : !0);
      b && b !== u.type && t.container.removeClass("mfp-" + b + "-holder");
      e = t["get" + r.charAt(0).toUpperCase() + r.slice(1)](u, t.currTemplate[r]);
      t.appendContent(e, r);
      u.preloaded = !0;
      i(wt, u);
      b = u.type;
      t.container.prepend(t.contentContainer);
      i("AfterChange")
    },
    appendContent: function (n, r) {
      t.content = n;
      n ? t.st.showCloseBtn && t.st.closeBtnInside && t.currTemplate[r] === !0 ? t.content.find(".mfp-close").length || t.content.append(st()) : t.content = n : t.content = "";
      i(ii);
      t.container.addClass("mfp-" + r + "-holder");
      t.contentContainer.append(t.content)
    },
    parseEl: function (r) {
      var u = t.items[r],
        o, e, f;
      if (u.tagName ? u = {
          el: n(u)
        } : (o = u.type, u = {
          data: u,
          src: u.src
        }), u.el) {
        for (e = t.types, f = 0; f < e.length; f++)
          if (u.el.hasClass("mfp-" + e[f])) {
            o = e[f];
            break
          } u.src = u.el.attr("data-mfp-src");
        u.src || (u.src = u.el.attr("href"))
      }
      return u.type = o || t.st.type || "inline", u.index = r, u.parsed = !0, t.items[r] = u, i("ElementParse", u), t.items[r]
    },
    addGroup: function (n, i) {
      var u = function (r) {
          r.mfpEl = this;
          t._openClick(r, n, i)
        },
        r;
      if (i || (i = {}), r = "click.magnificPopup", i.mainEl = n, i.items) {
        i.isObj = !0;
        n.off(r).on(r, u)
      } else if (i.isObj = !1, i.delegate) n.off(r).on(r, i.delegate, u);
      else {
        i.items = n;
        n.off(r).on(r, u)
      }
    },
    _openClick: function (i, r, u) {
      var e = u.midClick !== undefined ? u.midClick : n.magnificPopup.defaults.midClick,
        f;
      if (e || !(i.which === 2 || i.ctrlKey || i.metaKey || i.altKey || i.shiftKey)) {
        if (f = u.disableOn !== undefined ? u.disableOn : n.magnificPopup.defaults.disableOn, f)
          if (n.isFunction(f)) {
            if (!f.call(t)) return !0
          } else if (s.width() < f) return !0;
        i.type && (i.preventDefault(), t.isOpen && i.stopPropagation());
        u.el = n(i.mfpEl);
        u.delegate && (u.items = r.find(u.delegate));
        t.open(u)
      }
    },
    updateStatus: function (n, r) {
      if (t.preloader) {
        ot !== n && t.container.removeClass("mfp-s-" + ot);
        r || n !== "loading" || (r = t.st.tLoading);
        var u = {
          status: n,
          text: r
        };
        i("UpdateStatus", u);
        n = u.status;
        r = u.text;
        t.preloader.html(r);
        t.preloader.find("a").on("click", function (n) {
          n.stopImmediatePropagation()
        });
        t.container.addClass("mfp-s-" + n);
        ot = n
      }
    },
    _checkIfClose: function (i) {
      if (!n(i).hasClass(ft)) {
        var r = t.st.closeOnContentClick,
          u = t.st.closeOnBgClick;
        if (r && u || !t.content || n(i).hasClass("mfp-close") || t.preloader && i === t.preloader[0]) return !0;
        if (i === t.content[0] || n.contains(t.content[0], i)) {
          if (r) return !0
        } else if (u && n.contains(document, i)) return !0;
        return !1
      }
    },
    _addClassToMFP: function (n) {
      t.bgOverlay.addClass(n);
      t.wrap.addClass(n)
    },
    _removeClassFromMFP: function (n) {
      this.bgOverlay.removeClass(n);
      t.wrap.removeClass(n)
    },
    _hasScrollBar: function (n) {
      return (t.isIE7 ? f.height() : document.body.scrollHeight) > (n || s.height())
    },
    _setFocus: function () {
      (t.st.focus ? t.content.find(t.st.focus).eq(0) : t.wrap).focus()
    },
    _onFocusIn: function (i) {
      if (i.target !== t.wrap[0] && !n.contains(t.wrap[0], i.target)) return t._setFocus(), !1
    },
    _parseMarkup: function (t, r, f) {
      var e;
      f.data && (r = n.extend(f.data, r));
      i(it, [t, r, f]);
      n.each(r, function (i, r) {
        var f, o;
        if (r === undefined || r === !1) return !0;
        e = i.split("_");
        e.length > 1 ? (f = t.find(u + "-" + e[0]), f.length > 0 && (o = e[1], o === "replaceWith" ? f[0] !== r[0] && f.replaceWith(r) : o === "img" ? f.is("img") ? f.attr("src", r) : f.replaceWith(n("<img>").attr("src", r).attr("class", f.attr("class"))) : f.attr(e[1], r))) : t.find(u + "-" + i).html(r)
      })
    },
    _getScrollbarSize: function () {
      if (t.scrollbarSize === undefined) {
        var n = document.createElement("div");
        n.style.cssText = "width: 99px; height: 99px; overflow: scroll; position: absolute; top: -9999px;";
        document.body.appendChild(n);
        t.scrollbarSize = n.offsetWidth - n.clientWidth;
        document.body.removeChild(n)
      }
      return t.scrollbarSize
    }
  };
  n.magnificPopup = {
    instance: null,
    proto: w.prototype,
    modules: [],
    open: function (t, i) {
      return ht(), t = t ? n.extend(!0, {}, t) : {}, t.isObj = !0, t.index = i || 0, this.instance.open(t)
    },
    close: function () {
      return n.magnificPopup.instance && n.magnificPopup.instance.close()
    },
    registerModule: function (t, i) {
      i.options && (n.magnificPopup.defaults[t] = i.options);
      n.extend(this.proto, i.proto);
      this.modules.push(t)
    },
    defaults: {
      disableOn: 0,
      key: null,
      midClick: !1,
      mainClass: "",
      preloader: !0,
      focus: "",
      closeOnContentClick: !1,
      closeOnBgClick: !0,
      closeBtnInside: !0,
      showCloseBtn: !0,
      enableEscapeKey: !0,
      modal: !1,
      alignTop: !1,
      removalDelay: 0,
      prependTo: null,
      fixedContentPos: "auto",
      fixedBgPos: "auto",
      overflowY: "auto",
      closeMarkup: '<button title="%title%" type="button" class="mfp-close">&#215;<\/button>',
      tClose: "Close (Esc)",
      tLoading: "Loading...",
      autoFocusLast: !0
    }
  };
  n.fn.magnificPopup = function (i) {
    var r, u, f, e;
    return ht(), r = n(this), typeof i == "string" ? i === "open" ? (f = et ? r.data("magnificPopup") : r[0].magnificPopup, e = parseInt(arguments[1], 10) || 0, f.items ? u = f.items[e] : (u = r, f.delegate && (u = u.find(f.delegate)), u = u.eq(e)), t._openClick({
      mfpEl: u
    }, r, f)) : t.isOpen && t[i].apply(t, Array.prototype.slice.call(arguments, 1)) : (i = n.extend(!0, {}, i), et ? r.data("magnificPopup", i) : r[0].magnificPopup = i, t.addGroup(r, i)), r
  };
  k = "inline";
  ct = function () {
    g && (d.after(g.addClass(a)).detach(), g = null)
  };
  n.magnificPopup.registerModule(k, {
    options: {
      hiddenClass: "hide",
      markup: "",
      tNotFound: "Content not found"
    },
    proto: {
      initInline: function () {
        t.types.push(k);
        r(o + "." + k, function () {
          ct()
        })
      },
      getInline: function (i, r) {
        var f, u, e;
        return (ct(), i.src) ? (f = t.st.inline, u = n(i.src), u.length ? (e = u[0].parentNode, e && e.tagName && (d || (a = f.hiddenClass, d = l(a), a = "mfp-" + a), g = u.after(d).detach().removeClass(a)), t.updateStatus("ready")) : (t.updateStatus("error", f.tNotFound), u = n("<div>")), i.inlineElement = u, u) : (t.updateStatus("ready"), t._parseMarkup(r, {}, i), r)
      }
    }
  });
  var v = "ajax",
    y, lt = function () {
      y && n(document.body).removeClass(y)
    },
    dt = function () {
      lt();
      t.req && t.req.abort()
    };
  n.magnificPopup.registerModule(v, {
    options: {
      settings: null,
      cursor: "mfp-ajax-cur",
      tError: '<a href="%url%">The content<\/a> could not be loaded.'
    },
    proto: {
      initAjax: function () {
        t.types.push(v);
        y = t.st.ajax.cursor;
        r(o + "." + v, dt);
        r("BeforeChange." + v, dt)
      },
      getAjax: function (r) {
        y && n(document.body).addClass(y);
        t.updateStatus("loading");
        var u = n.extend({
          url: r.src,
          success: function (u, f, e) {
            var o = {
              data: u,
              xhr: e
            };
            i("ParseAjax", o);
            t.appendContent(n(o.data), v);
            r.finished = !0;
            lt();
            t._setFocus();
            setTimeout(function () {
              t.wrap.addClass(p)
            }, 16);
            t.updateStatus("ready");
            i("AjaxContentAdded")
          },
          error: function () {
            lt();
            r.finished = r.loadError = !0;
            t.updateStatus("error", t.st.ajax.tError.replace("%url%", r.src))
          }
        }, t.st.ajax.settings);
        return t.req = n.ajax(u), ""
      }
    }
  });
  gt = function (i) {
    if (i.data && i.data.title !== undefined) return i.data.title;
    var r = t.st.image.titleSrc;
    if (r) {
      if (n.isFunction(r)) return r.call(t, i);
      if (i.el) return i.el.attr(r) || ""
    }
    return ""
  };
  n.magnificPopup.registerModule("image", {
    options: {
      markup: '<div class="mfp-figure"><div class="mfp-close"><\/div><figure><div class="mfp-img"><\/div><figcaption><div class="mfp-bottom-bar"><div class="mfp-title"><\/div><div class="mfp-counter"><\/div><\/div><\/figcaption><\/figure><\/div>',
      cursor: "mfp-zoom-out-cur",
      titleSrc: "title",
      verticalFit: !0,
      tError: '<a href="%url%">The image<\/a> could not be loaded.'
    },
    proto: {
      initImage: function () {
        var i = t.st.image,
          f = ".image";
        t.types.push("image");
        r(rt + f, function () {
          t.currItem.type === "image" && i.cursor && n(document.body).addClass(i.cursor)
        });
        r(o + f, function () {
          i.cursor && n(document.body).removeClass(i.cursor);
          s.off("resize" + u)
        });
        r("Resize" + f, t.resizeImage);
        t.isLowIE && r("AfterChange", t.resizeImage)
      },
      resizeImage: function () {
        var n = t.currItem,
          i;
        n && n.img && t.st.image.verticalFit && (i = 0, t.isLowIE && (i = parseInt(n.img.css("padding-top"), 10) + parseInt(n.img.css("padding-bottom"), 10)), n.img.css("max-height", t.wH - i))
      },
      _onImageHasSize: function (n) {
        n.img && (n.hasSize = !0, e && clearInterval(e), n.isCheckingImgSize = !1, i("ImageHasSize", n), n.imgHidden && (t.content && t.content.removeClass("mfp-loading"), n.imgHidden = !1))
      },
      findImageSize: function (n) {
        var i = 0,
          u = n.img[0],
          r = function (f) {
            e && clearInterval(e);
            e = setInterval(function () {
              if (u.naturalWidth > 0) {
                t._onImageHasSize(n);
                return
              }
              i > 200 && clearInterval(e);
              i++;
              i === 3 ? r(10) : i === 40 ? r(50) : i === 100 && r(500)
            }, f)
          };
        r(1)
      },
      getImage: function (r, u) {
        var o = 0,
          s = function () {
            r && (r.img[0].complete ? (r.img.off(".mfploader"), r === t.currItem && (t._onImageHasSize(r), t.updateStatus("ready")), r.hasSize = !0, r.loaded = !0, i("ImageLoadComplete")) : (o++, o < 200 ? setTimeout(s, 100) : h()))
          },
          h = function () {
            r && (r.img.off(".mfploader"), r === t.currItem && (t._onImageHasSize(r), t.updateStatus("error", c.tError.replace("%url%", r.src))), r.hasSize = !0, r.loaded = !0, r.loadError = !0)
          },
          c = t.st.image,
          l = u.find(".mfp-img"),
          f;
        return (l.length && (f = document.createElement("img"), f.className = "mfp-img", r.el && r.el.find("img").length && (f.alt = r.el.find("img").attr("alt")), r.img = n(f).on("load.mfploader", s).on("error.mfploader", h), f.src = r.src, l.is("img") && (r.img = r.img.clone()), f = r.img[0], f.naturalWidth > 0 ? r.hasSize = !0 : f.width || (r.hasSize = !1)), t._parseMarkup(u, {
          title: gt(r),
          img_replaceWith: r.img
        }, r), t.resizeImage(), r.hasSize) ? (e && clearInterval(e), r.loadError ? (u.addClass("mfp-loading"), t.updateStatus("error", c.tError.replace("%url%", r.src))) : (u.removeClass("mfp-loading"), t.updateStatus("ready")), u) : (t.updateStatus("loading"), r.loading = !0, r.hasSize || (r.imgHidden = !0, u.addClass("mfp-loading"), t.findImageSize(r)), u)
      }
    }
  });
  ni = function () {
    return at === undefined && (at = document.createElement("p").style.MozTransform !== undefined), at
  };
  n.magnificPopup.registerModule("zoom", {
    options: {
      enabled: !1,
      easing: "ease-in-out",
      duration: 300,
      opener: function (n) {
        return n.is("img") ? n : n.find("img")
      }
    },
    proto: {
      initZoom: function () {
        var f = t.st.zoom,
          s = ".zoom",
          u;
        if (f.enabled && t.supportsTransition) {
          var c = f.duration,
            l = function (n) {
              var r = n.clone().removeAttr("style").removeAttr("class").addClass("mfp-animated-image"),
                u = "all " + f.duration / 1e3 + "s " + f.easing,
                t = {
                  position: "fixed",
                  zIndex: 9999,
                  left: 0,
                  top: 0,
                  "-webkit-backface-visibility": "hidden"
                },
                i = "transition";
              return t["-webkit-" + i] = t["-moz-" + i] = t["-o-" + i] = t[i] = u, r.css(t), r
            },
            h = function () {
              t.content.css("visibility", "visible")
            },
            e, n;
          r("BuildControls" + s, function () {
            if (t._allowZoom()) {
              if (clearTimeout(e), t.content.css("visibility", "hidden"), u = t._getItemToZoom(), !u) {
                h();
                return
              }
              n = l(u);
              n.css(t._getOffset());
              t.wrap.append(n);
              e = setTimeout(function () {
                n.css(t._getOffset(!0));
                e = setTimeout(function () {
                  h();
                  setTimeout(function () {
                    n.remove();
                    u = n = null;
                    i("ZoomAnimationEnded")
                  }, 16)
                }, c)
              }, 16)
            }
          });
          r(pt + s, function () {
            if (t._allowZoom()) {
              if (clearTimeout(e), t.st.removalDelay = c, !u) {
                if (u = t._getItemToZoom(), !u) return;
                n = l(u)
              }
              n.css(t._getOffset(!0));
              t.wrap.append(n);
              t.content.css("visibility", "hidden");
              setTimeout(function () {
                n.css(t._getOffset())
              }, 16)
            }
          });
          r(o + s, function () {
            t._allowZoom() && (h(), n && n.remove(), u = null)
          })
        }
      },
      _allowZoom: function () {
        return t.currItem.type === "image"
      },
      _getItemToZoom: function () {
        return t.currItem.hasSize ? t.currItem.img : !1
      },
      _getOffset: function (i) {
        var r, u;
        r = i ? t.currItem.img : t.st.zoom.opener(t.currItem.el || t.currItem);
        var f = r.offset(),
          e = parseInt(r.css("padding-top"), 10),
          o = parseInt(r.css("padding-bottom"), 10);
        return f.top -= n(window).scrollTop() - e, u = {
          width: r.width(),
          height: (et ? r.innerHeight() : r[0].offsetHeight) - o - e
        }, ni() ? u["-moz-transform"] = u.transform = "translate(" + f.left + "px," + f.top + "px)" : (u.left = f.left, u.top = f.top), u
      }
    }
  });
  var c = "iframe",
    ui = "//about:blank",
    vt = function (n) {
      if (t.currTemplate[c]) {
        var i = t.currTemplate[c].find("iframe");
        i.length && (n || (i[0].src = ui), t.isIE8 && i.css("display", n ? "block" : "none"))
      }
    };
  n.magnificPopup.registerModule(c, {
    options: {
      markup: '<div class="mfp-iframe-scaler"><div class="mfp-close"><\/div><iframe class="mfp-iframe" src="//about:blank" frameborder="0" allowfullscreen><\/iframe><\/div>',
      srcAction: "iframe_src",
      patterns: {
        youtube: {
          index: "youtube.com",
          id: "v=",
          src: "//www.youtube.com/embed/%id%?autoplay=1"
        },
        vimeo: {
          index: "vimeo.com/",
          id: "/",
          src: "//player.vimeo.com/video/%id%?autoplay=1"
        },
        gmaps: {
          index: "//maps.google.",
          src: "%id%&output=embed"
        }
      }
    },
    proto: {
      initIframe: function () {
        t.types.push(c);
        r("BeforeChange", function (n, t, i) {
          t !== i && (t === c ? vt() : i === c && vt(!0))
        });
        r(o + "." + c, function () {
          vt()
        })
      },
      getIframe: function (i, r) {
        var u = i.src,
          f = t.st.iframe,
          e;
        return n.each(f.patterns, function () {
          if (u.indexOf(this.index) > -1) return this.id && (u = typeof this.id == "string" ? u.substr(u.lastIndexOf(this.id) + this.id.length, u.length) : this.id.call(this, u)), u = this.src.replace("%id%", u), !1
        }), e = {}, f.srcAction && (e[f.srcAction] = u), t._parseMarkup(r, e, i), t.updateStatus("ready"), r
      }
    }
  });
  nt = function (n) {
    var i = t.items.length;
    return n > i - 1 ? n - i : n < 0 ? i + n : n
  };
  yt = function (n, t, i) {
    return n.replace(/%curr%/gi, t + 1).replace(/%total%/gi, i)
  };
  n.magnificPopup.registerModule("gallery", {
    options: {
      enabled: !1,
      arrowMarkup: '<button title="%title%" type="button" class="mfp-arrow mfp-arrow-%dir%"><\/button>',
      preload: [0, 2],
      navigateByImgClick: !0,
      arrows: !0,
      tPrev: "Previous (Left arrow key)",
      tNext: "Next (Right arrow key)",
      tCounter: "%curr% of %total%"
    },
    proto: {
      initGallery: function () {
        var u = t.st.gallery,
          i = ".mfp-gallery";
        if (t.direction = !0, !u || !u.enabled) return !1;
        h += " mfp-gallery";
        r(rt + i, function () {
          if (u.navigateByImgClick) t.wrap.on("click" + i, ".mfp-img", function () {
            if (t.items.length > 1) return t.next(), !1
          });
          f.on("keydown" + i, function (n) {
            n.keyCode === 37 ? t.prev() : n.keyCode === 39 && t.next()
          })
        });
        r("UpdateStatus" + i, function (n, i) {
          i.text && (i.text = yt(i.text, t.currItem.index, t.items.length))
        });
        r(it + i, function (n, i, r, f) {
          var e = t.items.length;
          r.counter = e > 1 ? yt(u.tCounter, f.index, e) : ""
        });
        r("BuildControls" + i, function () {
          if (t.items.length > 1 && u.arrows && !t.arrowLeft) {
            var i = u.arrowMarkup,
              r = t.arrowLeft = n(i.replace(/%title%/gi, u.tPrev).replace(/%dir%/gi, "left")).addClass(ft),
              f = t.arrowRight = n(i.replace(/%title%/gi, u.tNext).replace(/%dir%/gi, "right")).addClass(ft);
            r.click(function () {
              t.prev()
            });
            f.click(function () {
              t.next()
            });
            t.container.append(r.add(f))
          }
        });
        r(wt + i, function () {
          t._preloadTimeout && clearTimeout(t._preloadTimeout);
          t._preloadTimeout = setTimeout(function () {
            t.preloadNearbyImages();
            t._preloadTimeout = null
          }, 16)
        });
        r(o + i, function () {
          f.off(i);
          t.wrap.off("click" + i);
          t.arrowRight = t.arrowLeft = null
        })
      },
      next: function () {
        t.direction = !0;
        t.index = nt(t.index + 1);
        t.updateItemHTML()
      },
      prev: function () {
        t.direction = !1;
        t.index = nt(t.index - 1);
        t.updateItemHTML()
      },
      goTo: function (n) {
        t.direction = n >= t.index;
        t.index = n;
        t.updateItemHTML()
      },
      preloadNearbyImages: function () {
        for (var i = t.st.gallery.preload, r = Math.min(i[0], t.items.length), u = Math.min(i[1], t.items.length), n = 1; n <= (t.direction ? u : r); n++) t._preloadItem(t.index + n);
        for (n = 1; n <= (t.direction ? r : u); n++) t._preloadItem(t.index - n)
      },
      _preloadItem: function (r) {
        if (r = nt(r), !t.items[r].preloaded) {
          var u = t.items[r];
          u.parsed || (u = t.parseEl(r));
          i("LazyLoad", u);
          u.type === "image" && (u.img = n('<img class="mfp-img" />').on("load.mfploader", function () {
            u.hasSize = !0
          }).on("error.mfploader", function () {
            u.hasSize = !0;
            u.loadError = !0;
            i("LazyLoadError", u)
          }).attr("src", u.src));
          u.preloaded = !0
        }
      }
    }
  });
  tt = "retina";
  n.magnificPopup.registerModule(tt, {
    options: {
      replaceSrc: function (n) {
        return n.src.replace(/\.\w+$/, function (n) {
          return "@2x" + n
        })
      },
      ratio: 1
    },
    proto: {
      initRetina: function () {
        if (window.devicePixelRatio > 1) {
          var i = t.st.retina,
            n = i.ratio;
          n = isNaN(n) ? n() : n;
          n > 1 && (r("ImageHasSize." + tt, function (t, i) {
            i.img.css({
              "max-width": i.img[0].naturalWidth / n,
              width: "100%"
            })
          }), r("ElementParse." + tt, function (t, r) {
            r.src = i.replaceSrc(r, n)
          }))
        }
      }
    }
  });
  ht()
}),
function (n) {
  "use strict";
  n('a.js-scroll-trigger[href*="#"]:not([href="#"])').click(function () {
    if (location.pathname.replace(/^\//, "") == this.pathname.replace(/^\//, "") && location.hostname == this.hostname) {
      var t = n(this.hash);
      if (t = t.length ? t : n("[name=" + this.hash.slice(1) + "]"), t.length) return n("html, body").animate({
        scrollTop: t.offset().top - 48
      }, 1e3, "easeInOutExpo"), !1
    }
  });
  n(".js-scroll-trigger").click(function () {
    n(".navbar-collapse").collapse("hide")
  });
  n("body").scrollspy({
    target: "#mainNav",
    offset: 48
  });
  n(window).scroll(function () {
    n("#mainNav").is(".always-shrinked") || (n("#mainNav").offset().top > 100 ? n("#mainNav").addClass("navbar-shrink") : n("#mainNav").removeClass("navbar-shrink"))
  });
  window.sr = ScrollReveal();
  sr.reveal(".sr-icons", {
    duration: 600,
    scale: .3,
    distance: "0px"
  }, 200);
  sr.reveal(".sr-button", {
    duration: 1e3,
    delay: 200
  });
  sr.reveal(".sr-contact", {
    duration: 600,
    scale: .3,
    distance: "0px"
  }, 300);
  n(".popup-gallery").magnificPopup({
    delegate: "a",
    type: "image",
    tLoading: "Loading image #%curr%...",
    mainClass: "mfp-img-mobile",
    gallery: {
      enabled: !0,
      navigateByImgClick: !0,
      preload: [0, 1]
    },
    image: {
      tError: '<a href="%url%">The image #%curr%<\/a> could not be loaded.'
    }
  })
}(jQuery);
$(function () {
  $(".localizeDate").each(function () {
    var t = $(this).text(),
      n = new Date(t),
      i = n.toLocaleDateString() + " " + n.toLocaleTimeString();
    $(this).text(i)
  })
});