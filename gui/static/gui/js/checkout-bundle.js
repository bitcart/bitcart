/*!
 * clipboard.js v1.7.1
 * https://zenorocha.github.io/clipboard.js
 *
 * Licensed MIT © Zeno Rocha
 */
function openPaymentMethodDialog() {
    var n = $("#vexPopupDialog").html();
    vex.open({
        unsafeContent: n
    })
}

function closePaymentMethodDialog(n) {
    return vex.closeAll(), changeCurrency(n)
}

function decode(encoded) {
    return decodeURIComponent(encoded.replace(/\+/g,  " "));
}

function resetTabsSlider() {
    $("#tabsSlider").removeClass("slide-copy");
    $("#tabsSlider").removeClass("slide-altcoins");
    $("#scan-tab").removeClass("active");
    $("#copy-tab").removeClass("active");
    $("#altcoins-tab").removeClass("active");
    $("#copy").hide();
    $("#copy").removeClass("active");
    $("#scan").hide();
    $("#scan").removeClass("active");
    $("#altcoins").hide();
    $("#altcoins").removeClass("active");
    closePaymentMethodDialog(null)
}

function changeCurrency(n) {
    return n !== null && srvModel.paymentMethodId !== n && ($(".payment__currencies").hide(), $(".payment__spinner").show(), checkoutCtrl.scanDisplayQr = "", srvModel.paymentMethodId = n, fetchStatus()), !1
}

function onDataCallback(n) {
    var t = n.status,
        i;
    (t === "complete" || t === "confirmed" || t === "paid") && ($(".modal-dialog").hasClass("expired") && ($(".modal-dialog").removeClass("expired"), $("#expired").removeClass("active")), $(".modal-dialog").addClass("paid"), resetTabsSlider(), $("#paid").addClass("active"));
    (t === "expired" || t === "invalid") && ($(".modal-dialog").hasClass("paid") && ($(".modal-dialog").removeClass("paid"), $("#paid").removeClass("active")), $(".timer-row").removeClass("expiring-soon"), $(".timer-row__spinner").html(""), $("#emailAddressView").removeClass("active"), $(".modal-dialog").addClass("expired"), $("#expired").addClass("active"), resetTabsSlider());
    checkoutCtrl.srvModel.status !== t && window.parent.postMessage({
        invoiceId: srvModel.invoiceId,
        status: t
    }, "*");
    n.paymentMethodId === srvModel.paymentMethodId && checkoutCtrl.scanDisplayQr === "" && (checkoutCtrl.scanDisplayQr = n.invoiceBitcoinUrlQR);
    n.paymentMethodId === srvModel.paymentMethodId && ($(".payment__currencies").show(), $(".payment__spinner").hide());
    n.isLightning && checkoutCtrl.lndModel === null && (i = {
        toggle: 0
    }, checkoutCtrl.lndModel = i);
    n.isLightning || (checkoutCtrl.lndModel = null);
    checkoutCtrl.srvModel = n
}

function fetchStatus() {
    $.ajax({
        url: window.location.pathname + "status?invoiceId=" + srvModel.invoiceId + "&paymentMethodId=" + srvModel.paymentMethodId,
        type: "GET",
        cache: !1
    }).done(function (n) {
        onDataCallback(n)
    }).fail(function () {})
}

function lndToggleBolt11() {
    checkoutCtrl.lndModel.toggle = 0;
    checkoutCtrl.scanDisplayQr = checkoutCtrl.srvModel.invoiceBitcoinUrlQR
}

function lndToggleNode() {
    checkoutCtrl.lndModel.toggle = 1;
    checkoutCtrl.scanDisplayQr = checkoutCtrl.srvModel.peerInfo
}
var urlParams, ChangellyComponent, CoinSwitchComponent;
(function (n) {
    if (typeof exports == "object" && typeof module != "undefined") module.exports = n();
    else if (typeof define == "function" && define.amd) define([], n);
    else {
        var t;
        t = typeof window != "undefined" ? window : typeof global != "undefined" ? global : typeof self != "undefined" ? self : this;
        t.Clipboard = n()
    }
})(function () {
    var n;
    return function t(n, i, r) {
        function u(f, o) {
            var h, c, s;
            if (!i[f]) {
                if (!n[f]) {
                    if (h = typeof require == "function" && require, !o && h) return h(f, !0);
                    if (e) return e(f, !0);
                    c = new Error("Cannot find module '" + f + "'");
                    throw c.code = "MODULE_NOT_FOUND", c;
                }
                s = i[f] = {
                    exports: {}
                };
                n[f][0].call(s.exports, function (t) {
                    var i = n[f][1][t];
                    return u(i ? i : t)
                }, s, s.exports, t, n, i, r)
            }
            return i[f].exports
        }
        for (var e = typeof require == "function" && require, f = 0; f < r.length; f++) u(r[f]);
        return u
    }({
        1: [function (n, t) {
            function u(n, t) {
                while (n && n.nodeType !== r) {
                    if (typeof n.matches == "function" && n.matches(t)) return n;
                    n = n.parentNode
                }
            }
            var r = 9,
                i;
            typeof Element == "undefined" || Element.prototype.matches || (i = Element.prototype, i.matches = i.matchesSelector || i.mozMatchesSelector || i.msMatchesSelector || i.oMatchesSelector || i.webkitMatchesSelector);
            t.exports = u
        }, {}],
        2: [function (n, t) {
            function r(n, t, i, r, f) {
                var e = u.apply(this, arguments);
                return n.addEventListener(i, e, f), {
                    destroy: function () {
                        n.removeEventListener(i, e, f)
                    }
                }
            }

            function u(n, t, r, u) {
                return function (r) {
                    r.delegateTarget = i(r.target, t);
                    r.delegateTarget && u.call(n, r)
                }
            }
            var i = n("./closest");
            t.exports = r
        }, {
            "./closest": 1
        }],
        3: [function (n, t, i) {
            i.node = function (n) {
                return n !== undefined && n instanceof HTMLElement && n.nodeType === 1
            };
            i.nodeList = function (n) {
                var t = Object.prototype.toString.call(n);
                return n !== undefined && (t === "[object NodeList]" || t === "[object HTMLCollection]") && "length" in n && (n.length === 0 || i.node(n[0]))
            };
            i.string = function (n) {
                return typeof n == "string" || n instanceof String
            };
            i.fn = function (n) {
                var t = Object.prototype.toString.call(n);
                return t === "[object Function]"
            }
        }, {}],
        4: [function (n, t) {
            function u(n, t, r) {
                if (!n && !t && !r) throw new Error("Missing required arguments");
                if (!i.string(t)) throw new TypeError("Second argument must be a String");
                if (!i.fn(r)) throw new TypeError("Third argument must be a Function");
                if (i.node(n)) return f(n, t, r);
                if (i.nodeList(n)) return e(n, t, r);
                if (i.string(n)) return o(n, t, r);
                throw new TypeError("First argument must be a String, HTMLElement, HTMLCollection, or NodeList");
            }

            function f(n, t, i) {
                return n.addEventListener(t, i), {
                    destroy: function () {
                        n.removeEventListener(t, i)
                    }
                }
            }

            function e(n, t, i) {
                return Array.prototype.forEach.call(n, function (n) {
                    n.addEventListener(t, i)
                }), {
                    destroy: function () {
                        Array.prototype.forEach.call(n, function (n) {
                            n.removeEventListener(t, i)
                        })
                    }
                }
            }

            function o(n, t, i) {
                return r(document.body, n, t, i)
            }
            var i = n("./is"),
                r = n("delegate");
            t.exports = u
        }, {
            "./is": 3,
            delegate: 2
        }],
        5: [function (n, t) {
            function i(n) {
                var t, r, i, u;
                return n.nodeName === "SELECT" ? (n.focus(), t = n.value) : n.nodeName === "INPUT" || n.nodeName === "TEXTAREA" ? (r = n.hasAttribute("readonly"), r || n.setAttribute("readonly", ""), n.select(), n.setSelectionRange(0, n.value.length), r || n.removeAttribute("readonly"), t = n.value) : (n.hasAttribute("contenteditable") && n.focus(), i = window.getSelection(), u = document.createRange(), u.selectNodeContents(n), i.removeAllRanges(), i.addRange(u), t = i.toString()), t
            }
            t.exports = i
        }, {}],
        6: [function (n, t) {
            function i() {}
            i.prototype = {
                on: function (n, t, i) {
                    var r = this.e || (this.e = {});
                    return (r[n] || (r[n] = [])).push({
                        fn: t,
                        ctx: i
                    }), this
                },
                once: function (n, t, i) {
                    function r() {
                        u.off(n, r);
                        t.apply(i, arguments)
                    }
                    var u = this;
                    r._ = t;
                    return this.on(n, r, i)
                },
                emit: function (n) {
                    var r = [].slice.call(arguments, 1),
                        i = ((this.e || (this.e = {}))[n] || []).slice(),
                        t = 0,
                        u = i.length;
                    for (t; t < u; t++) i[t].fn.apply(i[t].ctx, r);
                    return this
                },
                off: function (n, t) {
                    var u = this.e || (this.e = {}),
                        r = u[n],
                        f = [],
                        i, e;
                    if (r && t)
                        for (i = 0, e = r.length; i < e; i++) r[i].fn !== t && r[i].fn._ !== t && f.push(r[i]);
                    return f.length ? u[n] = f : delete u[n], this
                }
            };
            t.exports = i
        }, {}],
        7: [function (t, i, r) {
            (function (u, f) {
                if (typeof n == "function" && n.amd) n(["module", "select"], f);
                else if (typeof r != "undefined") f(i, t("select"));
                else {
                    var e = {
                        exports: {}
                    };
                    f(e, u.select);
                    u.clipboardAction = e.exports
                }
            })(this, function (n, t) {
                "use strict";

                function r(n) {
                    return n && n.__esModule ? n : {
                        "default": n
                    }
                }

                function f(n, t) {
                    if (!(n instanceof t)) throw new TypeError("Cannot call a class as a function");
                }
                var i = r(t),
                    u = typeof Symbol == "function" && typeof Symbol.iterator == "symbol" ? function (n) {
                        return typeof n
                    } : function (n) {
                        return n && typeof Symbol == "function" && n.constructor === Symbol && n !== Symbol.prototype ? "symbol" : typeof n
                    },
                    e = function () {
                        function n(n, t) {
                            for (var i, r = 0; r < t.length; r++) i = t[r], i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(n, i.key, i)
                        }
                        return function (t, i, r) {
                            return i && n(t.prototype, i), r && n(t, r), t
                        }
                    }(),
                    o = function () {
                        function n(t) {
                            f(this, n);
                            this.resolveOptions(t);
                            this.initSelection()
                        }
                        return e(n, [{
                            key: "resolveOptions",
                            value: function () {
                                var n = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};
                                this.action = n.action;
                                this.container = n.container;
                                this.emitter = n.emitter;
                                this.target = n.target;
                                this.text = n.text;
                                this.trigger = n.trigger;
                                this.selectedText = ""
                            }
                        }, {
                            key: "initSelection",
                            value: function () {
                                this.text ? this.selectFake() : this.target && this.selectTarget()
                            }
                        }, {
                            key: "selectFake",
                            value: function () {
                                var t = this,
                                    r = document.documentElement.getAttribute("dir") == "rtl",
                                    n;
                                this.removeFake();
                                this.fakeHandlerCallback = function () {
                                    return t.removeFake()
                                };
                                this.fakeHandler = this.container.addEventListener("click", this.fakeHandlerCallback) || !0;
                                this.fakeElem = document.createElement("textarea");
                                this.fakeElem.style.fontSize = "12pt";
                                this.fakeElem.style.border = "0";
                                this.fakeElem.style.padding = "0";
                                this.fakeElem.style.margin = "0";
                                this.fakeElem.style.position = "absolute";
                                this.fakeElem.style[r ? "right" : "left"] = "-9999px";
                                n = window.pageYOffset || document.documentElement.scrollTop;
                                this.fakeElem.style.top = n + "px";
                                this.fakeElem.setAttribute("readonly", "");
                                this.fakeElem.value = this.text;
                                this.container.appendChild(this.fakeElem);
                                this.selectedText = i.default(this.fakeElem);
                                this.copyText()
                            }
                        }, {
                            key: "removeFake",
                            value: function () {
                                this.fakeHandler && (this.container.removeEventListener("click", this.fakeHandlerCallback), this.fakeHandler = null, this.fakeHandlerCallback = null);
                                this.fakeElem && (this.container.removeChild(this.fakeElem), this.fakeElem = null)
                            }
                        }, {
                            key: "selectTarget",
                            value: function () {
                                this.selectedText = i.default(this.target);
                                this.copyText()
                            }
                        }, {
                            key: "copyText",
                            value: function () {
                                var n = void 0;
                                try {
                                    n = document.execCommand(this.action)
                                } catch (t) {
                                    n = !1
                                }
                                this.handleResult(n)
                            }
                        }, {
                            key: "handleResult",
                            value: function (n) {
                                this.emitter.emit(n ? "success" : "error", {
                                    action: this.action,
                                    text: this.selectedText,
                                    trigger: this.trigger,
                                    clearSelection: this.clearSelection.bind(this)
                                })
                            }
                        }, {
                            key: "clearSelection",
                            value: function () {
                                this.trigger && this.trigger.focus();
                                window.getSelection().removeAllRanges()
                            }
                        }, {
                            key: "destroy",
                            value: function () {
                                this.removeFake()
                            }
                        }, {
                            key: "action",
                            set: function () {
                                var n = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : "copy";
                                if (this._action = n, this._action !== "copy" && this._action !== "cut") throw new Error('Invalid "action" value, use either "copy" or "cut"');
                            },
                            get: function () {
                                return this._action
                            }
                        }, {
                            key: "target",
                            set: function (n) {
                                if (n !== undefined)
                                    if (n && (typeof n == "undefined" ? "undefined" : u(n)) === "object" && n.nodeType === 1) {
                                        if (this.action === "copy" && n.hasAttribute("disabled")) throw new Error('Invalid "target" attribute. Please use "readonly" instead of "disabled" attribute');
                                        if (this.action === "cut" && (n.hasAttribute("readonly") || n.hasAttribute("disabled"))) throw new Error('Invalid "target" attribute. You can\'t cut text from elements with "readonly" or "disabled" attributes');
                                        this._target = n
                                    } else throw new Error('Invalid "target" value, use a valid Element');
                            },
                            get: function () {
                                return this._target
                            }
                        }]), n
                    }();
                n.exports = o
            })
        }, {
            select: 5
        }],
        8: [function (t, i, r) {
            (function (u, f) {
                if (typeof n == "function" && n.amd) n(["module", "./clipboard-action", "tiny-emitter", "good-listener"], f);
                else if (typeof r != "undefined") f(i, t("./clipboard-action"), t("tiny-emitter"), t("good-listener"));
                else {
                    var e = {
                        exports: {}
                    };
                    f(e, u.clipboardAction, u.tinyEmitter, u.goodListener);
                    u.clipboard = e.exports
                }
            })(this, function (n, t, i, r) {
                "use strict";

                function u(n) {
                    return n && n.__esModule ? n : {
                        "default": n
                    }
                }

                function c(n, t) {
                    if (!(n instanceof t)) throw new TypeError("Cannot call a class as a function");
                }

                function a(n, t) {
                    if (!n) throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
                    return t && (typeof t == "object" || typeof t == "function") ? t : n
                }

                function v(n, t) {
                    if (typeof t != "function" && t !== null) throw new TypeError("Super expression must either be null or a function, not " + typeof t);
                    n.prototype = Object.create(t && t.prototype, {
                        constructor: {
                            value: n,
                            enumerable: !1,
                            writable: !0,
                            configurable: !0
                        }
                    });
                    t && (Object.setPrototypeOf ? Object.setPrototypeOf(n, t) : n.__proto__ = t)
                }

                function f(n, t) {
                    var i = "data-clipboard-" + n;
                    if (t.hasAttribute(i)) return t.getAttribute(i)
                }
                var e = u(t),
                    o = u(i),
                    s = u(r),
                    h = typeof Symbol == "function" && typeof Symbol.iterator == "symbol" ? function (n) {
                        return typeof n
                    } : function (n) {
                        return n && typeof Symbol == "function" && n.constructor === Symbol && n !== Symbol.prototype ? "symbol" : typeof n
                    },
                    l = function () {
                        function n(n, t) {
                            for (var i, r = 0; r < t.length; r++) i = t[r], i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(n, i.key, i)
                        }
                        return function (t, i, r) {
                            return i && n(t.prototype, i), r && n(t, r), t
                        }
                    }(),
                    y = function (n) {
                        function t(n, i) {
                            c(this, t);
                            var r = a(this, (t.__proto__ || Object.getPrototypeOf(t)).call(this));
                            return r.resolveOptions(i), r.listenClick(n), r
                        }
                        return v(t, n), l(t, [{
                            key: "resolveOptions",
                            value: function () {
                                var n = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};
                                this.action = typeof n.action == "function" ? n.action : this.defaultAction;
                                this.target = typeof n.target == "function" ? n.target : this.defaultTarget;
                                this.text = typeof n.text == "function" ? n.text : this.defaultText;
                                this.container = h(n.container) === "object" ? n.container : document.body
                            }
                        }, {
                            key: "listenClick",
                            value: function (n) {
                                var t = this;
                                this.listener = s.default(n, "click", function (n) {
                                    return t.onClick(n)
                                })
                            }
                        }, {
                            key: "onClick",
                            value: function (n) {
                                var t = n.delegateTarget || n.currentTarget;
                                this.clipboardAction && (this.clipboardAction = null);
                                this.clipboardAction = new e.default({
                                    action: this.action(t),
                                    target: this.target(t),
                                    text: this.text(t),
                                    container: this.container,
                                    trigger: t,
                                    emitter: this
                                })
                            }
                        }, {
                            key: "defaultAction",
                            value: function (n) {
                                return f("action", n)
                            }
                        }, {
                            key: "defaultTarget",
                            value: function (n) {
                                var t = f("target", n);
                                if (t) return document.querySelector(t)
                            }
                        }, {
                            key: "defaultText",
                            value: function (n) {
                                return f("text", n)
                            }
                        }, {
                            key: "destroy",
                            value: function () {
                                this.listener.destroy();
                                this.clipboardAction && (this.clipboardAction.destroy(), this.clipboardAction = null)
                            }
                        }], [{
                            key: "isSupported",
                            value: function () {
                                var n = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : ["copy", "cut"],
                                    i = typeof n == "string" ? [n] : n,
                                    t = !!document.queryCommandSupported;
                                return i.forEach(function (n) {
                                    t = t && !!document.queryCommandSupported(n)
                                }), t
                            }
                        }]), t
                    }(o.default);
                n.exports = y
            })
        }, {
            "./clipboard-action": 7,
            "good-listener": 4,
            "tiny-emitter": 6
        }]
    }, {}, [8])(8)
});
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
/*!
 * Vue.js v2.5.13
 * (c) 2014-2017 Evan You
 * Released under the MIT License.
 */
! function (n, t) {
    "object" == typeof exports && "undefined" != typeof module ? module.exports = t() : "function" == typeof define && define.amd ? define(t) : n.Vue = t()
}(this, function () {
    "use strict";

    function t(n) {
        return void 0 === n || null === n
    }

    function n(n) {
        return void 0 !== n && null !== n
    }

    function u(n) {
        return !0 === n
    }

    function vi(n) {
        return "string" == typeof n || "number" == typeof n || "symbol" == typeof n || "boolean" == typeof n
    }

    function h(n) {
        return null !== n && "object" == typeof n
    }

    function v(n) {
        return "[object Object]" === rl.call(n)
    }

    function so(n) {
        var t = parseFloat(String(n));
        return t >= 0 && Math.floor(t) === t && isFinite(n)
    }

    function ty(n) {
        return null == n ? "" : "object" == typeof n ? JSON.stringify(n, null, 2) : String(n)
    }

    function yi(n) {
        var t = parseFloat(n);
        return isNaN(t) ? n : t
    }

    function e(n, t) {
        for (var i = Object.create(null), u = n.split(","), r = 0; r < u.length; r++) i[u[r]] = !0;
        return t ? function (n) {
            return i[n.toLowerCase()]
        } : function (n) {
            return i[n]
        }
    }

    function ht(n, t) {
        if (n.length) {
            var i = n.indexOf(t);
            if (i > -1) return n.splice(i, 1)
        }
    }

    function c(n, t) {
        return yp.call(n, t)
    }

    function k(n) {
        var t = Object.create(null);
        return function (i) {
            return t[i] || (t[i] = n(i))
        }
    }

    function iy(n, t) {
        function i(i) {
            var r = arguments.length;
            return r ? r > 1 ? n.apply(t, arguments) : n.call(t, i) : n.call(t)
        }
        return i._length = n.length, i
    }

    function fu(n, t) {
        t = t || 0;
        for (var i = n.length - t, r = new Array(i); i--;) r[i] = n[i + t];
        return r
    }

    function i(n, t) {
        for (var i in t) n[i] = t[i];
        return n
    }

    function ho(n) {
        for (var r = {}, t = 0; t < n.length; t++) n[t] && i(r, n[t]);
        return r
    }

    function o() {}

    function vt(n, t) {
        var i, r, u, f, e, o;
        if (n === t) return !0;
        if (i = h(n), r = h(t), !i || !r) return !i && !r && String(n) === String(t);
        try {
            return (u = Array.isArray(n), f = Array.isArray(t), u && f) ? n.length === t.length && n.every(function (n, i) {
                return vt(n, t[i])
            }) : u || f ? !1 : (e = Object.keys(n), o = Object.keys(t), e.length === o.length && e.every(function (i) {
                return vt(n[i], t[i])
            }))
        } catch (n) {
            return !1
        }
    }

    function co(n, t) {
        for (var i = 0; i < n.length; i++)
            if (vt(n[i], t)) return i;
        return -1
    }

    function rr(n) {
        var t = !1;
        return function () {
            t || (t = !0, n.apply(this, arguments))
        }
    }

    function ry(n) {
        var t = (n + "").charCodeAt(0);
        return 36 === t || 95 === t
    }

    function eu(n, t, i, r) {
        Object.defineProperty(n, t, {
            value: i,
            enumerable: !!r,
            writable: !0,
            configurable: !0
        })
    }

    function ii(n) {
        return "function" == typeof n && /native code/.test(n.toString())
    }

    function ri(n) {
        return new a(void 0, void 0, void 0, String(n))
    }

    function lo(n, t) {
        var r = n.componentOptions,
            i = new a(n.tag, n.data, n.children, n.text, n.elm, n.context, r, n.asyncFactory);
        return i.ns = n.ns, i.isStatic = n.isStatic, i.key = n.key, i.isComment = n.isComment, i.fnContext = n.fnContext, i.fnOptions = n.fnOptions, i.fnScopeId = n.fnScopeId, i.isCloned = !0, t && (n.children && (i.children = ur(n.children, !0)), r && r.children && (r.children = ur(r.children, !0))), i
    }

    function ur(n, t) {
        for (var r = n.length, u = new Array(r), i = 0; i < r; i++) u[i] = lo(n[i], t);
        return u
    }

    function uy(n, t) {
        n.__proto__ = t
    }

    function fy(n, t, i) {
        for (var u, r = 0, f = i.length; r < f; r++) u = i[r], eu(n, u, t[u])
    }

    function ui(n, t) {
        if (h(n) && !(n instanceof a)) {
            var i;
            return c(n, "__ob__") && n.__ob__ instanceof yr ? i = n.__ob__ : rt.shouldConvert && !di() && (Array.isArray(n) || v(n)) && Object.isExtensible(n) && !n._isVue && (i = new yr(n)), t && i && i.vmCount++, i
        }
    }

    function yt(n, t, i, r, u) {
        var h = new s,
            f = Object.getOwnPropertyDescriptor(n, t);
        if (!f || !1 !== f.configurable) {
            var e = f && f.get,
                c = f && f.set,
                o = !u && ui(i);
            Object.defineProperty(n, t, {
                enumerable: !0,
                configurable: !0,
                get: function () {
                    var t = e ? e.call(n) : i;
                    return s.target && (h.depend(), o && (o.dep.depend(), Array.isArray(t) && vo(t))), t
                },
                set: function (t) {
                    var r = e ? e.call(n) : i;
                    t === r || t != t && r != r || (c ? c.call(n, t) : i = t, o = !u && ui(t), h.notify())
                }
            })
        }
    }

    function ou(n, t, i) {
        if (Array.isArray(n) && so(t)) return n.length = Math.max(n.length, t), n.splice(t, 1, i), i;
        if (t in n && !(t in Object.prototype)) return n[t] = i, i;
        var r = n.__ob__;
        return n._isVue || r && r.vmCount ? i : r ? (yt(r.value, t, i), r.dep.notify(), i) : (n[t] = i, i)
    }

    function ao(n, t) {
        if (Array.isArray(n) && so(t)) n.splice(t, 1);
        else {
            var i = n.__ob__;
            n._isVue || i && i.vmCount || c(n, t) && (delete n[t], i && i.dep.notify())
        }
    }

    function vo(n) {
        for (var t = void 0, i = 0, r = n.length; i < r; i++)(t = n[i]) && t.__ob__ && t.__ob__.dep.depend(), Array.isArray(t) && vo(t)
    }

    function su(n, t) {
        if (!t) return n;
        for (var i, u, r, e = Object.keys(t), f = 0; f < e.length; f++) u = n[i = e[f]], r = t[i], c(n, i) ? v(u) && v(r) && su(u, r) : ou(n, i, r);
        return n
    }

    function hu(n, t, i) {
        return i ? function () {
            var r = "function" == typeof t ? t.call(i, i) : t,
                u = "function" == typeof n ? n.call(i, i) : n;
            return r ? su(r, u) : u
        } : t ? n ? function () {
            return su("function" == typeof t ? t.call(this, this) : t, "function" == typeof n ? n.call(this, this) : n)
        } : t : n
    }

    function ey(n, t) {
        return t ? n ? n.concat(t) : Array.isArray(t) ? t : [t] : n
    }

    function oy(n, t) {
        var r = Object.create(n || null);
        return t ? i(r, t) : r
    }

    function pt(n, t, r) {
        function s(i) {
            var u = nt[i] || uw;
            o[i] = u(n[i], t[i], r, i)
        }
        var e, f, h, u, o;
        if ("function" == typeof t && (t = t.options), function (n) {
                var t = n.props,
                    u, i, r, f;
                if (t) {
                    if (r = {}, Array.isArray(t))
                        for (u = t.length; u--;) "string" == typeof (i = t[u]) && (r[it(i)] = {
                            type: null
                        });
                    else if (v(t))
                        for (f in t) i = t[f], r[it(f)] = v(i) ? i : {
                            type: i
                        };
                    n.props = r
                }
            }(t), function (n) {
                var t = n.inject,
                    e, r, u, f;
                if (t)
                    if (e = n.inject = {}, Array.isArray(t))
                        for (r = 0; r < t.length; r++) e[t[r]] = {
                            from: t[r]
                        };
                    else if (v(t))
                    for (u in t) f = t[u], e[u] = v(f) ? i({
                        from: u
                    }, f) : {
                        from: f
                    }
            }(t), function (n) {
                var t = n.directives,
                    r, i;
                if (t)
                    for (r in t) i = t[r], "function" == typeof i && (t[r] = {
                        bind: i,
                        update: i
                    })
            }(t), e = t.extends, e && (n = pt(n, e, r)), t.mixins)
            for (f = 0, h = t.mixins.length; f < h; f++) n = pt(n, t.mixins[f], r);
        o = {};
        for (u in n) s(u);
        for (u in t) c(n, u) || s(u);
        return o
    }

    function cu(n, t, i) {
        var r, u, f;
        if ("string" == typeof i) return (r = n[t], c(r, i)) ? r[i] : (u = it(i), c(r, u)) ? r[u] : (f = wp(u), c(r, f)) ? r[f] : r[i] || r[u] || r[f]
    }

    function lu(n, t, i, r) {
        var f = t[n],
            o = !c(i, n),
            u = i[n],
            e;
        return (yo(Boolean, f.type) && (o && !c(f, "default") ? u = !1 : yo(String, f.type) || "" !== u && u !== gf(n) || (u = !0)), void 0 === u) && (u = function (n, t, i) {
            if (c(t, "default")) {
                var r = t.default;
                return n && n.$options.propsData && void 0 === n.$options.propsData[i] && void 0 !== n._props[i] ? n._props[i] : "function" == typeof r && "Function" !== pi(t.type) ? r.call(n) : r
            }
        }(r, f, n), e = rt.shouldConvert, rt.shouldConvert = !0, ui(u), rt.shouldConvert = e), u
    }

    function pi(n) {
        var t = n && n.toString().match(/^\s*function (\w+)/);
        return t ? t[1] : ""
    }

    function yo(n, t) {
        if (!Array.isArray(t)) return pi(t) === pi(n);
        for (var i = 0, r = t.length; i < r; i++)
            if (pi(t[i]) === pi(n)) return !0;
        return !1
    }

    function ct(n, t, i) {
        var r, u, f;
        if (t)
            for (r = t; r = r.$parent;)
                if (u = r.$options.errorCaptured, u)
                    for (f = 0; f < u.length; f++) try {
                        if (!1 === u[f].call(r, n, t, i)) return
                    } catch (n) {
                        po(n, r, "errorCaptured hook")
                    }
        po(n, t, i)
    }

    function po(n, t, i) {
        if (w.errorHandler) try {
            return w.errorHandler.call(null, n, t, i)
        } catch (n) {
            wo(n, null, "config.errorHandler")
        }
        wo(n, t, i)
    }

    function wo(n) {
        if (!l && !ol || "undefined" == typeof console) throw n;
        console.error(n)
    }

    function fr() {
        var t, n;
        for (ee = !1, t = fe.slice(0), fe.length = 0, n = 0; n < t.length; n++) t[n]()
    }

    function au(n, t) {
        var i;
        if (fe.push(function () {
                if (n) try {
                    n.call(t)
                } catch (n) {
                    ct(n, t, "nextTick")
                } else i && i(t)
            }), ee || (ee = !0, oe ? gi() : ue()), !n && "undefined" != typeof Promise) return new Promise(function (n) {
            i = n
        })
    }

    function bo(n) {
        vu(n, bl);
        bl.clear()
    }

    function vu(n, t) {
        var i, u, f = Array.isArray(n),
            r;
        if ((f || h(n)) && !Object.isFrozen(n)) {
            if (n.__ob__) {
                if (r = n.__ob__.dep.id, t.has(r)) return;
                t.add(r)
            }
            if (f)
                for (i = n.length; i--;) vu(n[i], t);
            else
                for (i = (u = Object.keys(n)).length; i--;) vu(n[u[i]], t)
        }
    }

    function yu(n) {
        function t() {
            var u = arguments,
                i = t.fns,
                r, n;
            if (!Array.isArray(i)) return i.apply(null, arguments);
            for (r = i.slice(), n = 0; n < r.length; n++) r[n].apply(null, u)
        }
        return t.fns = n, t
    }

    function ko(n, i, r, u) {
        var f, e, s, o;
        for (f in n) e = n[f], s = i[f], o = kl(f), t(e) || (t(s) ? (t(e.fns) && (e = n[f] = yu(e)), r(o.name, e, o.once, o.capture, o.passive, o.params)) : e !== s && (s.fns = e, n[f] = s));
        for (f in i) t(n[f]) && u((o = kl(f)).name, i[f], o.capture)
    }

    function lt(i, r, f) {
        function s() {
            f.apply(this, arguments);
            ht(e.fns, s)
        }
        i instanceof a && (i = i.data.hook || (i.data.hook = {}));
        var e, o = i[r];
        t(o) ? e = yu([s]) : n(o.fns) && u(o.merged) ? (e = o).fns.push(s) : e = yu([o, s]);
        e.merged = !0;
        i[r] = e
    }

    function go(t, i, r, u, f) {
        if (n(i)) {
            if (c(i, r)) return t[r] = i[r], f || delete i[r], !0;
            if (c(i, u)) return t[r] = i[u], f || delete i[u], !0
        }
        return !1
    }

    function wi(t) {
        return n(t) && n(t.text) && function (n) {
            return !1 === n
        }(t.isComment)
    }

    function ns(i, r) {
        for (var f, h, o, e = [], s = 0; s < i.length; s++) t(f = i[s]) || "boolean" == typeof f || (o = e[h = e.length - 1], Array.isArray(f) ? f.length > 0 && (wi((f = ns(f, (r || "") + "_" + s))[0]) && wi(o) && (e[h] = ri(o.text + f[0].text), f.shift()), e.push.apply(e, f)) : vi(f) ? wi(o) ? e[h] = ri(o.text + f) : "" !== f && e.push(ri(f)) : wi(f) && wi(o) ? e[h] = ri(o.text + f.text) : (u(i._isVList) && n(f.tag) && t(f.key) && n(r) && (f.key = "__vlist" + r + "_" + s + "__"), e.push(f)));
        return e
    }

    function pu(n, t) {
        return (n.__esModule || ll && "Module" === n[Symbol.toStringTag]) && (n = n.default), h(n) ? t.extend(n) : n
    }

    function er(n) {
        return n.isComment && n.asyncFactory
    }

    function ts(t) {
        var r, i;
        if (Array.isArray(t))
            for (r = 0; r < t.length; r++)
                if (i = t[r], n(i) && (n(i.componentOptions) || er(i))) return i
    }

    function sy(n, t, i) {
        i ? nr.$once(n, t) : nr.$on(n, t)
    }

    function hy(n, t) {
        nr.$off(n, t)
    }

    function is(n, t, i) {
        nr = n;
        ko(t, i || {}, sy, hy);
        nr = void 0
    }

    function wu(n, t) {
        var i = {},
            f, h, r, u, o, e, s;
        if (!n) return i;
        for (f = 0, h = n.length; f < h; f++) r = n[f], u = r.data, (u && u.attrs && u.attrs.slot && delete u.attrs.slot, (r.context === t || r.fnContext === t) && u && null != u.slot) ? (o = u.slot, e = i[o] || (i[o] = []), "template" === r.tag ? e.push.apply(e, r.children || []) : e.push(r)) : (i.default || (i.default = [])).push(r);
        for (s in i) i[s].every(cy) && delete i[s];
        return i
    }

    function cy(n) {
        return n.isComment && !n.asyncFactory || " " === n.text
    }

    function rs(n, t) {
        t = t || {};
        for (var i = 0; i < n.length; i++) Array.isArray(n[i]) ? rs(n[i], t) : t[n[i].key] = n[i].fn;
        return t
    }

    function us(n) {
        for (; n && (n = n.$parent);)
            if (n._inactive) return !0;
        return !1
    }

    function bu(n, t) {
        if (t) {
            if (n._directInactive = !1, us(n)) return
        } else if (n._directInactive) return;
        if (n._inactive || null === n._inactive) {
            n._inactive = !1;
            for (var i = 0; i < n.$children.length; i++) bu(n.$children[i]);
            d(n, "activated")
        }
    }

    function fs(n, t) {
        if (!(t && (n._directInactive = !0, us(n)) || n._inactive)) {
            n._inactive = !0;
            for (var i = 0; i < n.$children.length; i++) fs(n.$children[i]);
            d(n, "deactivated")
        }
    }

    function d(n, t) {
        var i = n.$options[t],
            r, u;
        if (i)
            for (r = 0, u = i.length; r < u; r++) try {
                i[r].call(n)
            } catch (i) {
                ct(i, n, t + " hook")
            }
        n._hasHookEvent && n.$emit("hook:" + t)
    }

    function ly() {
        var n, t, i, r;
        for (le = !0, et.sort(function (n, t) {
                return n.id - t.id
            }), li = 0; li < et.length; li++) t = (n = et[li]).id, pr[t] = null, n.run();
        i = he.slice();
        r = et.slice();
        li = et.length = he.length = 0;
        pr = {};
        ce = le = !1,
            function (n) {
                for (var t = 0; t < n.length; t++) n[t]._inactive = !0, bu(n[t], !0)
            }(i),
            function (n) {
                for (var r = n.length, i, t; r--;) i = n[r], t = i.vm, t._watcher === i && t._isMounted && d(t, "updated")
            }(r);
        vr && w.devtools && vr.emit("flush")
    }

    function ku(n, t, i) {
        ot.get = function () {
            return this[t][i]
        };
        ot.set = function (n) {
            this[t][i] = n
        };
        Object.defineProperty(n, i, ot)
    }

    function ay(n) {
        n._watchers = [];
        var t = n.$options;
        t.props && function (n, t) {
            var u = n.$options.propsData || {},
                f = n._props = {},
                e = n.$options._propKeys = [],
                o = !n.$parent,
                i, r;
            rt.shouldConvert = o;
            i = function (i) {
                e.push(i);
                var r = lu(i, t, u, n);
                yt(f, i, r);
                i in n || ku(n, "_props", i)
            };
            for (r in t) i(r);
            rt.shouldConvert = !0
        }(n, t.props);
        t.methods && function (n, t) {
            n.$options.props;
            for (var i in t) n[i] = null == t[i] ? o : iy(t[i], n)
        }(n, t.methods);
        t.data ? function (n) {
            var t = n.$options.data,
                i;
            t = n._data = "function" == typeof t ? function (n, t) {
                try {
                    return n.call(t, t)
                } catch (n) {
                    return ct(n, t, "data()"), {}
                }
            }(t, n) : t || {};
            v(t) || (t = {});
            for (var r = Object.keys(t), u = n.$options.props, f = (n.$options.methods, r.length); f--;) i = r[f], u && c(u, i) || ry(i) || ku(n, "_data", i);
            ui(t, !0)
        }(n) : ui(n._data = {}, !0);
        t.computed && function (n, t) {
            var f = n._computedWatchers = Object.create(null),
                e = di(),
                i, r, u;
            for (i in t) r = t[i], u = "function" == typeof r ? r : r.get, e || (f[i] = new tt(n, u || o, o, dl)), i in n || es(n, i, r)
        }(n, t.computed);
        t.watch && t.watch !== ne && function (n, t) {
            var r, i, u;
            for (r in t)
                if (i = t[r], Array.isArray(i))
                    for (u = 0; u < i.length; u++) du(n, r, i[u]);
                else du(n, r, i)
        }(n, t.watch)
    }

    function es(n, t, i) {
        var r = !di();
        "function" == typeof i ? (ot.get = r ? os(t) : i, ot.set = o) : (ot.get = i.get ? r && !1 !== i.cache ? os(t) : i.get : o, ot.set = i.set ? i.set : o);
        Object.defineProperty(n, t, ot)
    }

    function os(n) {
        return function () {
            var t = this._computedWatchers && this._computedWatchers[n];
            if (t) return t.dirty && t.evaluate(), s.target && t.depend(), t.value
        }
    }

    function du(n, t, i, r) {
        return v(i) && (r = i, i = i.handler), "string" == typeof i && (i = n[i]), n.$watch(t, i, r)
    }

    function ss(n, t) {
        var u;
        if (n) {
            for (var f = Object.create(null), o = ll ? Reflect.ownKeys(n).filter(function (t) {
                    return Object.getOwnPropertyDescriptor(n, t).enumerable
                }) : Object.keys(n), e = 0; e < o.length; e++) {
                for (var r = o[e], s = n[r].from, i = t; i;) {
                    if (i._provided && s in i._provided) {
                        f[r] = i._provided[s];
                        break
                    }
                    i = i.$parent
                }!i && "default" in n[r] && (u = n[r].default, f[r] = "function" == typeof u ? u.call(t) : u)
            }
            return f
        }
    }

    function vy(t, i) {
        var u, r, f, e, o;
        if (Array.isArray(t) || "string" == typeof t)
            for (u = new Array(t.length), r = 0, f = t.length; r < f; r++) u[r] = i(t[r], r);
        else if ("number" == typeof t)
            for (u = new Array(t), r = 0; r < t; r++) u[r] = i(r + 1, r);
        else if (h(t))
            for (e = Object.keys(t), u = new Array(e.length), r = 0, f = e.length; r < f; r++) o = e[r], u[r] = i(t[o], o, r);
        return n(u) && (u._isVList = !0), u
    }

    function yy(n, t, r, u) {
        var f, s = this.$scopedSlots[n],
            e, o;
        return s ? (r = r || {}, u && (r = i(i({}, u), r)), f = s(r) || t) : (e = this.$slots[n], e && (e._rendered = !0), f = e || t), o = r && r.slot, o ? this.$createElement("template", {
            slot: o
        }, f) : f
    }

    function py(n) {
        return cu(this.$options, "filters", n) || ul
    }

    function wy(n, t, i, r) {
        var u = w.keyCodes[t] || i;
        return u ? Array.isArray(u) ? -1 === u.indexOf(n) : u !== n : r ? gf(r) !== t : void 0
    }

    function by(n, t, i, r, u) {
        var f, e, o;
        if (i && h(i)) {
            Array.isArray(i) && (i = ho(i));
            e = function (e) {
                if ("class" === e || "style" === e || vp(e)) f = n;
                else {
                    var o = n.attrs && n.attrs.type;
                    f = r || w.mustUseProp(t, o, e) ? n.domProps || (n.domProps = {}) : n.attrs || (n.attrs = {})
                }
                e in f || (f[e] = i[e], !u) || ((n.on || (n.on = {}))["update:" + e] = function (n) {
                    i[e] = n
                })
            };
            for (o in i) e(o)
        }
        return n
    }

    function ky(n, t) {
        var r = this._staticTrees || (this._staticTrees = []),
            i = r[n];
        return i && !t ? Array.isArray(i) ? ur(i) : lo(i) : (i = r[n] = this.$options.staticRenderFns[n].call(this._renderProxy, null, this), hs(i, "__static__" + n, !1), i)
    }

    function dy(n, t, i) {
        return hs(n, "__once__" + t + (i ? "_" + i : ""), !0), n
    }

    function hs(n, t, i) {
        if (Array.isArray(n))
            for (var r = 0; r < n.length; r++) n[r] && "string" != typeof n[r] && cs(n[r], t + "_" + r, i);
        else cs(n, t, i)
    }

    function cs(n, t, i) {
        n.isStatic = !0;
        n.key = t;
        n.isOnce = i
    }

    function gy(n, t) {
        var u, r, f, e;
        if (t && v(t)) {
            u = n.on = n.on ? i({}, n.on) : {};
            for (r in t) f = u[r], e = t[r], u[r] = f ? [].concat(f, e) : e
        }
        return n
    }

    function ls(n) {
        n._o = dy;
        n._n = yi;
        n._s = ty;
        n._l = vy;
        n._t = yy;
        n._q = vt;
        n._i = co;
        n._m = ky;
        n._f = py;
        n._k = wy;
        n._b = by;
        n._v = ri;
        n._e = gt;
        n._u = rs;
        n._g = gy
    }

    function as(n, t, i, r, f) {
        var e = f.options;
        this.data = n;
        this.props = t;
        this.children = i;
        this.parent = r;
        this.listeners = n.on || p;
        this.injections = ss(e.inject, r);
        this.slots = function () {
            return wu(i, r)
        };
        var o = Object.create(r),
            s = u(e._compiled),
            h = !s;
        s && (this.$options = e, this.$slots = this.slots(), this.$scopedSlots = n.scopedSlots || p);
        this._c = e._scopeId ? function (n, t, i, u) {
            var f = or(o, n, t, i, u, h);
            return f && (f.fnScopeId = e._scopeId, f.fnContext = r), f
        } : function (n, t, i, r) {
            return or(o, n, t, i, r, h)
        }
    }

    function vs(n, t) {
        for (var i in t) n[it(i)] = t[i]
    }

    function ys(i, r, f, e, o) {
        var c, s, l, w, v, y;
        if (!t(i) && (c = f.$options._base, h(i) && (i = c.extend(i)), "function" == typeof i)) return t(i.cid) && (s = i, void 0 === (i = function (i, r, f) {
            if (u(i.error) && n(i.errorComp)) return i.errorComp;
            if (n(i.resolved)) return i.resolved;
            if (u(i.loading) && n(i.loadingComp)) return i.loadingComp;
            if (!n(i.contexts)) {
                var l = i.contexts = [f],
                    a = !0,
                    s = function () {
                        for (var n = 0, t = l.length; n < t; n++) l[n].$forceUpdate()
                    },
                    c = rr(function (n) {
                        i.resolved = pu(n, r);
                        a || s()
                    }),
                    o = rr(function () {
                        n(i.errorComp) && (i.error = !0, s())
                    }),
                    e = i(c, o);
                return h(e) && ("function" == typeof e.then ? t(i.resolved) && e.then(c, o) : n(e.component) && "function" == typeof e.component.then && (e.component.then(c, o), n(e.error) && (i.errorComp = pu(e.error, r)), n(e.loading) && (i.loadingComp = pu(e.loading, r), 0 === e.delay ? i.loading = !0 : setTimeout(function () {
                    t(i.resolved) && t(i.error) && (i.loading = !0, s())
                }, e.delay || 200)), n(e.timeout) && setTimeout(function () {
                    t(i.resolved) && o(null)
                }, e.timeout))), a = !1, i.loading ? i.loadingComp : i.resolved
            }
            i.contexts.push(f)
        }(s, c, f))) ? function (n, t, i, r, u) {
            var f = gt();
            return f.asyncFactory = n, f.asyncMeta = {
                data: t,
                context: i,
                children: r,
                tag: u
            }, f
        }(s, r, f, e, o) : (r = r || {}, gu(i), n(r.model) && function (t, i) {
            var f = t.model && t.model.prop || "value",
                u = t.model && t.model.event || "input",
                r;
            (i.props || (i.props = {}))[f] = i.model.value;
            r = i.on || (i.on = {});
            r[u] = n(r[u]) ? [i.model.callback].concat(r[u]) : i.model.callback
        }(i.options, r), l = function (i, r) {
            var o = r.options.props,
                u, e;
            if (!t(o)) {
                var f = {},
                    s = i.attrs,
                    h = i.props;
                if (n(s) || n(h))
                    for (u in o) e = gf(u), go(f, h, u, e, !0) || go(f, s, u, e, !1);
                return f
            }
        }(r, i), u(i.options.functional)) ? function (t, i, r, u, f) {
            var s = t.options,
                o = {},
                h = s.props,
                c, l, e;
            if (n(h))
                for (c in h) o[c] = lu(c, h, i || p);
            else n(r.attrs) && vs(o, r.attrs), n(r.props) && vs(o, r.props);
            return l = new as(r, o, f, u, t), e = s.render.call(null, l._c, l), e instanceof a && (e.fnContext = u, e.fnOptions = s, r.slot && ((e.data || (e.data = {})).slot = r.slot)), e
        }(i, l, r, f, e) : (w = r.on, (r.on = r.nativeOn, u(i.options.abstract)) && (v = r.slot, r = {}, v && (r.slot = v)), ! function (n) {
            var t;
            for (n.hook || (n.hook = {}), t = 0; t < gl.length; t++) {
                var i = gl[t],
                    r = n.hook[i],
                    u = ae[i];
                n.hook[i] = r ? function (n, t) {
                    return function (i, r, u, f) {
                        n(i, r, u, f);
                        t(i, r, u, f)
                    }
                }(u, r) : u
            }
        }(r), y = i.options.name || o, new a("vue-component-" + i.cid + (y ? "-" + y : ""), r, void 0, void 0, void 0, f, {
            Ctor: i,
            propsData: l,
            listeners: w,
            tag: o,
            children: e
        }, s))
    }

    function or(t, i, r, f, e, o) {
        return (Array.isArray(r) || vi(r)) && (e = f, f = r, r = void 0), u(o) && (e = na),
            function (t, i, r, u, f) {
                var e, o, s;
                return n(r) && n(r.__ob__) ? gt() : (n(r) && n(r.is) && (i = r.is), !i) ? gt() : (Array.isArray(u) && "function" == typeof u[0] && ((r = r || {}).scopedSlots = {
                    "default": u[0]
                }, u.length = 0), f === na ? u = function (n) {
                    return vi(n) ? [ri(n)] : Array.isArray(n) ? ns(n) : void 0
                }(u) : f === ew && (u = function (n) {
                    for (var t = 0; t < n.length; t++)
                        if (Array.isArray(n[t])) return Array.prototype.concat.apply([], n);
                    return n
                }(u)), "string" == typeof i ? (o = t.$vnode && t.$vnode.ns || w.getTagNamespace(i), e = w.isReservedTag(i) ? new a(w.parsePlatformTagName(i), r, u, void 0, void 0, t) : n(s = cu(t.$options, "components", i)) ? ys(s, r, t, u, i) : new a(i, r, u, void 0, void 0, t)) : e = ys(i, r, t, u), n(e) ? (o && ps(e, o), e) : gt())
            }(t, i, r, f, e)
    }

    function ps(i, r, f) {
        var e, s, o;
        if (i.ns = r, "foreignObject" === i.tag && (r = void 0, f = !0), n(i.children))
            for (e = 0, s = i.children.length; e < s; e++) o = i.children[e], n(o.tag) && (t(o.ns) || u(f)) && ps(o, r, f)
    }

    function gu(n) {
        var t = n.options,
            r, u;
        return n.super && (r = gu(n.super), r !== n.superOptions && (n.superOptions = r, u = function (n) {
            var i, r = n.options,
                f = n.extendOptions,
                u = n.sealedOptions;
            for (var t in r) r[t] !== u[t] && (i || (i = {}), i[t] = function (n, t, i) {
                var u, r;
                if (Array.isArray(n)) {
                    for (u = [], i = Array.isArray(i) ? i : [i], t = Array.isArray(t) ? t : [t], r = 0; r < n.length; r++)(t.indexOf(n[r]) >= 0 || i.indexOf(n[r]) < 0) && u.push(n[r]);
                    return u
                }
                return n
            }(r[t], f[t], u[t]));
            return i
        }(n), u && i(n.extendOptions, u), (t = n.options = pt(r, n.extendOptions)).name && (t.components[t.name] = n))), t
    }

    function r(n) {
        this._init(n)
    }

    function np(n) {
        n.cid = 0;
        var t = 1;
        n.extend = function (n) {
            var o, r;
            n = n || {};
            var u = this,
                f = u.cid,
                e = n._Ctor || (n._Ctor = {});
            return e[f] ? e[f] : (o = n.name || u.options.name, r = function (n) {
                this._init(n)
            }, r.prototype = Object.create(u.prototype), r.prototype.constructor = r, r.cid = t++, r.options = pt(u.options, n), r.super = u, r.options.props && function (n) {
                var t = n.options.props;
                for (var i in t) ku(n.prototype, "_props", i)
            }(r), r.options.computed && function (n) {
                var t = n.options.computed;
                for (var i in t) es(n.prototype, i, t[i])
            }(r), r.extend = u.extend, r.mixin = u.mixin, r.use = u.use, lr.forEach(function (n) {
                r[n] = u[n]
            }), o && (r.options.components[o] = r), r.superOptions = u.options, r.extendOptions = n, r.sealedOptions = i({}, r.options), e[f] = r, r)
        }
    }

    function ws(n) {
        return n && (n.Ctor.options.name || n.tag)
    }

    function sr(n, t) {
        return Array.isArray(n) ? n.indexOf(t) > -1 : "string" == typeof n ? n.split(",").indexOf(t) > -1 : !! function (n) {
            return "[object RegExp]" === rl.call(n)
        }(n) && n.test(t)
    }

    function bs(n, t) {
        var i = n.cache,
            e = n.keys,
            o = n._vnode,
            r, u, f;
        for (r in i) u = i[r], u && (f = ws(u.componentOptions), f && !t(f) && nf(i, r, e, o))
    }

    function nf(n, t, i, r) {
        var u = n[t];
        !u || r && u.tag === r.tag || u.componentInstance.$destroy();
        n[t] = null;
        ht(i, t)
    }

    function tp(t) {
        for (var i = t.data, r = t, u = t; n(u.componentInstance);)(u = u.componentInstance._vnode) && u.data && (i = ks(u.data, i));
        for (; n(r = r.parent);) r && r.data && (i = ks(i, r.data));
        return function (t, i) {
            return n(t) || n(i) ? tf(t, rf(i)) : ""
        }(i.staticClass, i.class)
    }

    function ks(t, i) {
        return {
            staticClass: tf(t.staticClass, i.staticClass),
            "class": n(t.class) ? [t.class, i.class] : i.class
        }
    }

    function tf(n, t) {
        return n ? t ? n + " " + t : n : t || ""
    }

    function rf(t) {
        return Array.isArray(t) ? function (t) {
            for (var r, i = "", u = 0, f = t.length; u < f; u++) n(r = rf(t[u])) && "" !== r && (i && (i += " "), i += r);
            return i
        }(t) : h(t) ? function (n) {
            var t = "";
            for (var i in n) n[i] && (t && (t += " "), t += i);
            return t
        }(t) : "string" == typeof t ? t : ""
    }

    function ds(n) {
        return ea(n) ? "svg" : "math" === n ? "math" : void 0
    }

    function uf(n) {
        if ("string" == typeof n) {
            var t = document.querySelector(n);
            return t || document.createElement("div")
        }
        return n
    }

    function fi(n, t) {
        var i = n.data.ref;
        if (i) {
            var f = n.context,
                u = n.componentInstance || n.elm,
                r = f.$refs;
            t ? Array.isArray(r[i]) ? ht(r[i], u) : r[i] === u && (r[i] = void 0) : n.data.refInFor ? Array.isArray(r[i]) ? r[i].indexOf(u) < 0 && r[i].push(u) : r[i] = [u] : r[i] = u
        }
    }

    function wt(i, r) {
        return i.key === r.key && (i.tag === r.tag && i.isComment === r.isComment && n(i.data) === n(r.data) && function (t, i) {
            if ("input" !== t.tag) return !0;
            var r, u = n(r = t.data) && n(r = r.attrs) && r.type,
                f = n(r = i.data) && n(r = r.attrs) && r.type;
            return u === f || de(u) && de(f)
        }(i, r) || u(i.isAsyncPlaceholder) && i.asyncFactory === r.asyncFactory && t(r.asyncFactory.error))
    }

    function ip(t, i, r) {
        for (var f, e = {}, u = i; u <= r; ++u) n(f = t[u].key) && (e[f] = u);
        return e
    }

    function ff(n, t) {
        (n.data.directives || t.data.directives) && function (n, t) {
            var r, e, i, c = n === ti,
                l = t === ti,
                o = gs(n.data.directives, n.context),
                s = gs(t.data.directives, t.context),
                u = [],
                f = [],
                h;
            for (r in s) e = o[r], i = s[r], e ? (i.oldValue = e.value, bi(i, "update", t, n), i.def && i.def.componentUpdated && f.push(i)) : (bi(i, "bind", t, n), i.def && i.def.inserted && u.push(i));
            if (u.length && (h = function () {
                    for (var i = 0; i < u.length; i++) bi(u[i], "inserted", t, n)
                }, c ? lt(t, "insert", h) : h()), f.length && lt(t, "postpatch", function () {
                    for (var i = 0; i < f.length; i++) bi(f[i], "componentUpdated", t, n)
                }), !c)
                for (r in o) s[r] || bi(o[r], "unbind", n, n, l)
        }(n, t)
    }

    function gs(n, t) {
        var u = Object.create(null),
            r, i;
        if (!n) return u;
        for (r = 0; r < n.length; r++)(i = n[r]).modifiers || (i.modifiers = ww), u[function (n) {
            return n.rawName || n.name + "." + Object.keys(n.modifiers || {}).join(".")
        }(i)] = i, i.def = cu(t.$options, "directives", i.name);
        return u
    }

    function bi(n, t, i, r, u) {
        var f = n.def && n.def[t];
        if (f) try {
            f(i.elm, n, i, r, u)
        } catch (r) {
            ct(r, i.context, "directive " + n.name + " " + t + " hook")
        }
    }

    function nh(r, u) {
        var c = u.componentOptions;
        if (!(n(c) && !1 === c.Ctor.options.inheritAttrs || t(r.data.attrs) && t(u.data.attrs))) {
            var f, s, o = u.elm,
                h = r.data.attrs || {},
                e = u.data.attrs || {};
            n(e.__ob__) && (e = u.data.attrs = i({}, e));
            for (f in e) s = e[f], h[f] !== s && th(o, f, s);
            (hi || hl) && e.value !== h.value && th(o, "value", e.value);
            for (f in h) t(e[f]) && (be(f) ? o.removeAttributeNS(we, fa(f)) : ua(f) || o.removeAttribute(f))
        }
    }

    function th(n, t, i) {
        if (cw(t)) dr(i) ? n.removeAttribute(t) : (i = "allowfullscreen" === t && "EMBED" === n.tagName ? "true" : t, n.setAttribute(t, i));
        else if (ua(t)) n.setAttribute(t, dr(i) || "false" === i ? "false" : "true");
        else if (be(t)) dr(i) ? n.removeAttributeNS(we, fa(t)) : n.setAttributeNS(we, t, i);
        else if (dr(i)) n.removeAttribute(t);
        else {
            if (hi && !ci && "TEXTAREA" === n.tagName && "placeholder" === t && !n.__ieph) {
                var r = function (t) {
                    t.stopImmediatePropagation();
                    n.removeEventListener("input", r)
                };
                n.addEventListener("input", r);
                n.__ieph = !0
            }
            n.setAttribute(t, i)
        }
    }

    function ih(i, r) {
        var f = r.elm,
            s = r.data,
            e = i.data,
            u, o;
        t(s.staticClass) && t(s.class) && (t(e) || t(e.staticClass) && t(e.class)) || (u = tp(r), o = f._transitionClasses, n(o) && (u = tf(u, rf(o))), u !== f._prevClass && (f.setAttribute("class", u), f._prevClass = u))
    }

    function ef(n) {
        function w() {
            (f || (f = [])).push(n.slice(e, t).trim());
            e = t + 1
        }
        for (var i, u, r, f, h = !1, c = !1, l = !1, a = !1, v = 0, y = 0, p = 0, e = 0, o, s, t = 0; t < n.length; t++)
            if (u = i, i = n.charCodeAt(t), h) 39 === i && 92 !== u && (h = !1);
            else if (c) 34 === i && 92 !== u && (c = !1);
        else if (l) 96 === i && 92 !== u && (l = !1);
        else if (a) 47 === i && 92 !== u && (a = !1);
        else if (124 !== i || 124 === n.charCodeAt(t + 1) || 124 === n.charCodeAt(t - 1) || v || y || p) {
            switch (i) {
                case 34:
                    c = !0;
                    break;
                case 39:
                    h = !0;
                    break;
                case 96:
                    l = !0;
                    break;
                case 40:
                    p++;
                    break;
                case 41:
                    p--;
                    break;
                case 91:
                    y++;
                    break;
                case 93:
                    y--;
                    break;
                case 123:
                    v++;
                    break;
                case 125:
                    v--
            }
            if (47 === i) {
                for (o = t - 1, s = void 0; o >= 0 && " " === (s = n.charAt(o)); o--);
                s && gw.test(s) || (a = !0)
            }
        } else void 0 === r ? (e = t + 1, r = n.slice(0, t).trim()) : w();
        if (void 0 === r ? r = n.slice(0, t).trim() : 0 !== e && w(), f)
            for (t = 0; t < f.length; t++) r = function (n, t) {
                var i = t.indexOf("("),
                    r, u;
                return i < 0 ? '_f("' + t + '")(' + n + ")" : (r = t.slice(0, i), u = t.slice(i + 1), '_f("' + r + '")(' + n + "," + u)
            }(r, f[t]);
        return r
    }

    function rh(n) {
        console.error("[Vue compiler]: " + n)
    }

    function ki(n, t) {
        return n ? n.map(function (n) {
            return n[t]
        }).filter(function (n) {
            return n
        }) : []
    }

    function bt(n, t, i) {
        (n.props || (n.props = [])).push({
            name: t,
            value: i
        });
        n.plain = !1
    }

    function of (n, t, i) {
        (n.attrs || (n.attrs = [])).push({
            name: t,
            value: i
        });
        n.plain = !1
    }

    function sf(n, t, i) {
        n.attrsMap[t] = i;
        n.attrsList.push({
            name: t,
            value: i
        })
    }

    function rp(n, t, i, r, u, f) {
        (n.directives || (n.directives = [])).push({
            name: t,
            rawName: i,
            value: r,
            arg: u,
            modifiers: f
        });
        n.plain = !1
    }

    function kt(n, t, i, r, u) {
        var o, f, e;
        (r = r || p).capture && (delete r.capture, t = "!" + t);
        r.once && (delete r.once, t = "~" + t);
        r.passive && (delete r.passive, t = "&" + t);
        "click" === t && (r.right ? (t = "contextmenu", delete r.right) : r.middle && (t = "mouseup"));
        r.native ? (delete r.native, o = n.nativeEvents || (n.nativeEvents = {})) : o = n.events || (n.events = {});
        f = {
            value: i
        };
        r !== p && (f.modifiers = r);
        e = o[t];
        Array.isArray(e) ? u ? e.unshift(f) : e.push(f) : o[t] = e ? u ? [f, e] : [e, f] : f;
        n.plain = !1
    }

    function y(n, t, i) {
        var u = f(n, ":" + t) || f(n, "v-bind:" + t),
            r;
        return null != u ? ef(u) : !1 !== i && (r = f(n, t), null != r) ? JSON.stringify(r) : void 0
    }

    function f(n, t, i) {
        var f;
        if (null != (f = n.attrsMap[t]))
            for (var u = n.attrsList, r = 0, e = u.length; r < e; r++)
                if (u[r].name === t) {
                    u.splice(r, 1);
                    break
                } return i && delete n.attrsMap[t], f
    }

    function uh(n, t, i) {
        var u = i || {},
            r = "$$v",
            f;
        u.trim && (r = "(typeof $$v === 'string'? $$v.trim(): $$v)");
        u.number && (r = "_n(" + r + ")");
        f = ei(t, r);
        n.model = {
            value: "(" + t + ")",
            expression: '"' + t + '"',
            callback: "function ($$v) {" + f + "}"
        }
    }

    function ei(n, t) {
        var i = function (n) {
            if (ye = n.length, n.indexOf("[") < 0 || n.lastIndexOf("]") < ye - 1) return (at = n.lastIndexOf(".")) > -1 ? {
                exp: n.slice(0, at),
                key: '"' + n.slice(at + 1) + '"'
            } : {
                exp: n,
                key: null
            };
            for (ia = n, at = br = pe = 0; !cf();) fh(wr = hf()) ? eh(wr) : 91 === wr && function (n) {
                var t = 1;
                for (br = at; !cf();)
                    if (n = hf(), fh(n)) eh(n);
                    else if (91 === n && t++, 93 === n && t--, 0 === t) {
                    pe = at;
                    break
                }
            }(wr);
            return {
                exp: n.slice(0, br),
                key: n.slice(br + 1, pe)
            }
        }(n);
        return null === i.key ? n + "=" + t : "$set(" + i.exp + ", " + i.key + ", " + t + ")"
    }

    function hf() {
        return ia.charCodeAt(++at)
    }

    function cf() {
        return at >= ye
    }

    function fh(n) {
        return 34 === n || 39 === n
    }

    function eh(n) {
        for (var t = n; !cf() && (n = hf()) !== t;);
    }

    function up(n, t, i, r, u) {
        t = function (n) {
            return n._withTask || (n._withTask = function () {
                oe = !0;
                var t = n.apply(null, arguments);
                return oe = !1, t
            })
        }(t);
        i && (t = function (n, t, i) {
            var r = tr;
            return function u() {
                null !== n.apply(null, arguments) && oh(t, u, i, r)
            }
        }(t, n, r));
        tr.addEventListener(n, t, cl ? {
            capture: r,
            passive: u
        } : r)
    }

    function oh(n, t, i, r) {
        (r || tr).removeEventListener(n, t._withTask || t, i)
    }

    function sh(i, r) {
        if (!t(i.data.on) || !t(r.data.on)) {
            var u = r.data.on || {},
                f = i.data.on || {};
            tr = r.elm,
                function (t) {
                    if (n(t[nu])) {
                        var i = hi ? "change" : "input";
                        t[i] = [].concat(t[nu], t[i] || []);
                        delete t[nu]
                    }
                    n(t[ge]) && (t.change = [].concat(t[ge], t.change || []), delete t[ge])
                }(u);
            ko(u, f, up, oh, r.context);
            tr = void 0
        }
    }

    function hh(r, u) {
        var h;
        if (!t(r.data.domProps) || !t(u.data.domProps)) {
            var f, o, e = u.elm,
                c = r.data.domProps || {},
                s = u.data.domProps || {};
            n(s.__ob__) && (s = u.data.domProps = i({}, s));
            for (f in c) t(s[f]) && (e[f] = "");
            for (f in s) {
                if (o = s[f], "textContent" === f || "innerHTML" === f) {
                    if (u.children && (u.children.length = 0), o === c[f]) continue;
                    1 === e.childNodes.length && e.removeChild(e.childNodes[0])
                }
                "value" === f ? (e._value = o, h = t(o) ? "" : String(o), function (t, i) {
                    return !t.composing && ("OPTION" === t.tagName || function (n, t) {
                        var i = !0;
                        try {
                            i = document.activeElement !== n
                        } catch (n) {}
                        return i && n.value !== t
                    }(t, i) || function (t, i) {
                        var u = t.value,
                            r = t._vModifiers;
                        if (n(r)) {
                            if (r.lazy) return !1;
                            if (r.number) return yi(u) !== yi(i);
                            if (r.trim) return u.trim() !== i.trim()
                        }
                        return u !== i
                    }(t, i))
                }(e, h) && (e.value = h)) : e[f] = o
            }
        }
    }

    function lf(n) {
        var t = ch(n.style);
        return n.staticStyle ? i(n.staticStyle, t) : t
    }

    function ch(n) {
        return Array.isArray(n) ? ho(n) : "string" == typeof n ? oa(n) : n
    }

    function lh(r, u) {
        var c = u.data,
            e = r.data,
            o;
        if (!(t(c.staticStyle) && t(c.style) && t(e.staticStyle) && t(e.style))) {
            var s, f, l = u.elm,
                v = e.staticStyle,
                y = e.normalizedStyle || e.style || {},
                a = v || y,
                h = ch(u.data.style) || {};
            u.data.normalizedStyle = n(h.__ob__) ? i({}, h) : h;
            o = function (n, t) {
                var r, e = {},
                    u, f;
                if (t)
                    for (u = n; u.componentInstance;)(u = u.componentInstance._vnode) && u.data && (r = lf(u.data)) && i(e, r);
                for ((r = lf(n.data)) && i(e, r), f = n; f = f.parent;) f.data && (r = lf(f.data)) && i(e, r);
                return e
            }(u, !0);
            for (f in a) t(o[f]) && ha(l, f, "");
            for (f in o)(s = o[f]) !== a[f] && ha(l, f, null == s ? "" : s)
        }
    }

    function ah(n, t) {
        if (t && (t = t.trim()))
            if (n.classList) t.indexOf(" ") > -1 ? t.split(/\s+/).forEach(function (t) {
                return n.classList.add(t)
            }) : n.classList.add(t);
            else {
                var i = " " + (n.getAttribute("class") || "") + " ";
                i.indexOf(" " + t + " ") < 0 && n.setAttribute("class", (i + t).trim())
            }
    }

    function vh(n, t) {
        if (t && (t = t.trim()))
            if (n.classList) t.indexOf(" ") > -1 ? t.split(/\s+/).forEach(function (t) {
                return n.classList.remove(t)
            }) : n.classList.remove(t), n.classList.length || n.removeAttribute("class");
            else {
                for (var i = " " + (n.getAttribute("class") || "") + " ", r = " " + t + " "; i.indexOf(r) >= 0;) i = i.replace(r, " ");
                (i = i.trim()) ? n.setAttribute("class", i): n.removeAttribute("class")
            }
    }

    function yh(n) {
        if (n) {
            if ("object" == typeof n) {
                var t = {};
                return !1 !== n.css && i(t, la(n.name || "v")), i(t, n), t
            }
            return "string" == typeof n ? la(n) : void 0
        }
    }

    function ph(n) {
        ya(function () {
            ya(n)
        })
    }

    function dt(n, t) {
        var i = n._transitionClasses || (n._transitionClasses = []);
        i.indexOf(t) < 0 && (i.push(t), ah(n, t))
    }

    function ut(n, t) {
        n._transitionClasses && ht(n._transitionClasses, t);
        vh(n, t)
    }

    function wh(n, t, i) {
        var r = bh(n, t),
            u = r.type,
            c = r.timeout,
            f = r.propCount;
        if (!u) return i();
        var e = u === ai ? iu : va,
            o = 0,
            s = function () {
                n.removeEventListener(e, h);
                i()
            },
            h = function (t) {
                t.target === n && ++o >= f && s()
            };
        setTimeout(function () {
            o < f && s()
        }, c + 1);
        n.addEventListener(e, h)
    }

    function bh(n, t) {
        var i, r = window.getComputedStyle(n),
            c = r[tu + "Delay"].split(", "),
            s = r[tu + "Duration"].split(", "),
            u = kh(c, s),
            l = r[to + "Delay"].split(", "),
            h = r[to + "Duration"].split(", "),
            f = kh(l, h),
            e = 0,
            o = 0;
        return t === ai ? u > 0 && (i = ai, e = u, o = s.length) : t === no ? f > 0 && (i = no, e = f, o = h.length) : o = (i = (e = Math.max(u, f)) > 0 ? u > f ? ai : no : null) ? i === ai ? s.length : h.length : 0, {
            type: i,
            timeout: e,
            propCount: o,
            hasTransform: i === ai && fb.test(r[tu + "Property"])
        }
    }

    function kh(n, t) {
        for (; n.length < t.length;) n = n.concat(n);
        return Math.max.apply(null, t.map(function (t, i) {
            return dh(t) + dh(n[i])
        }))
    }

    function dh(n) {
        return 1e3 * Number(n.slice(0, -1))
    }

    function af(i, r) {
        var u = i.elm,
            f, e;
        if (n(u._leaveCb) && (u._leaveCb.cancelled = !0, u._leaveCb()), f = yh(i.data.transition), !t(f) && !n(u._enterCb) && 1 === u.nodeType) {
            for (var ht = f.css, ct = f.type, at = f.enterClass, vt = f.enterToClass, yt = f.enterActiveClass, p = f.appearClass, w = f.appearToClass, b = f.appearActiveClass, k = f.beforeEnter, pt = f.enter, d = f.afterEnter, g = f.enterCancelled, wt = f.beforeAppear, c = f.appear, bt = f.afterAppear, kt = f.appearCancelled, v = f.duration, nt = ni, l = ni.$vnode; l && l.parent;) nt = (l = l.parent).context;
            if (e = !nt._isMounted || !i.isRootInsert, !e || c || "" === c) {
                var y = e && p ? p : at,
                    tt = e && b ? b : yt,
                    it = e && w ? w : vt,
                    rt = e ? wt || k : k,
                    s = e && "function" == typeof c ? c : pt,
                    ft = e ? bt || d : d,
                    et = e ? kt || g : g,
                    ot = yi(h(v) ? v.enter : v),
                    a = !1 !== ht && !ci,
                    st = vf(s),
                    o = u._enterCb = rr(function () {
                        a && (ut(u, it), ut(u, tt));
                        o.cancelled ? (a && ut(u, y), et && et(u)) : ft && ft(u);
                        u._enterCb = null
                    });
                i.data.show || lt(i, "insert", function () {
                    var t = u.parentNode,
                        n = t && t._pending && t._pending[i.key];
                    n && n.tag === i.tag && n.elm._leaveCb && n.elm._leaveCb();
                    s && s(u, o)
                });
                rt && rt(u);
                a && (dt(u, y), dt(u, tt), ph(function () {
                    dt(u, it);
                    ut(u, y);
                    o.cancelled || st || (nc(ot) ? setTimeout(o, ot) : wh(u, ct, o))
                }));
                i.data.show && (r && r(), s && s(u, o));
                a || st || o()
            }
        }
    }

    function gh(i, r) {
        function a() {
            e.cancelled || (i.data.show || ((u.parentNode._pending || (u.parentNode._pending = {}))[i.key] = i), p && p(u), o && (dt(u, s), dt(u, y), ph(function () {
                dt(u, v);
                ut(u, s);
                e.cancelled || d || (nc(g) ? setTimeout(e, g) : wh(u, tt, e))
            })), c && c(u, e), o || d || e())
        }
        var u = i.elm,
            f;
        if (n(u._enterCb) && (u._enterCb.cancelled = !0, u._enterCb()), f = yh(i.data.transition), t(f) || 1 !== u.nodeType) return r();
        if (!n(u._leaveCb)) {
            var nt = f.css,
                tt = f.type,
                s = f.leaveClass,
                v = f.leaveToClass,
                y = f.leaveActiveClass,
                p = f.beforeLeave,
                c = f.leave,
                w = f.afterLeave,
                b = f.leaveCancelled,
                k = f.delayLeave,
                l = f.duration,
                o = !1 !== nt && !ci,
                d = vf(c),
                g = yi(h(l) ? l.leave : l),
                e = u._leaveCb = rr(function () {
                    u.parentNode && u.parentNode._pending && (u.parentNode._pending[i.key] = null);
                    o && (ut(u, v), ut(u, y));
                    e.cancelled ? (o && ut(u, s), b && b(u)) : (r(), w && w(u));
                    u._leaveCb = null
                });
            k ? k(a) : a()
        }
    }

    function nc(n) {
        return "number" == typeof n && !isNaN(n)
    }

    function vf(i) {
        if (t(i)) return !1;
        var r = i.fns;
        return n(r) ? vf(Array.isArray(r) ? r[0] : r) : (i._length || i.length) > 1
    }

    function tc(n, t) {
        !0 !== t.data.show && af(t)
    }

    function ic(n, t, i) {
        rc(n, t, i);
        (hi || hl) && setTimeout(function () {
            rc(n, t, i)
        }, 0)
    }

    function rc(n, t) {
        var u = t.value,
            f = n.multiple,
            e, r, i, o;
        if (!f || Array.isArray(u)) {
            for (i = 0, o = n.options.length; i < o; i++)
                if (r = n.options[i], f) e = co(u, hr(r)) > -1, r.selected !== e && (r.selected = e);
                else if (vt(hr(r), u)) return void(n.selectedIndex !== i && (n.selectedIndex = i));
            f || (n.selectedIndex = -1)
        }
    }

    function uc(n, t) {
        return t.every(function (t) {
            return !vt(t, n)
        })
    }

    function hr(n) {
        return "_value" in n ? n._value : n.value
    }

    function fp(n) {
        n.target.composing = !0
    }

    function fc(n) {
        n.target.composing && (n.target.composing = !1, yf(n.target, "input"))
    }

    function yf(n, t) {
        var i = document.createEvent("HTMLEvents");
        i.initEvent(t, !0, !0);
        n.dispatchEvent(i)
    }

    function pf(n) {
        return !n.componentInstance || n.data && n.data.transition ? n : pf(n.componentInstance._vnode)
    }

    function wf(n) {
        var t = n && n.componentOptions;
        return t && t.Ctor.options.abstract ? wf(ts(t.children)) : n
    }

    function ec(n) {
        var t = {},
            f = n.$options,
            i, r, u;
        for (i in f.propsData) t[i] = n[i];
        r = f._parentListeners;
        for (u in r) t[it(u)] = r[u];
        return t
    }

    function oc(n, t) {
        if (/\d-keep-alive$/.test(t.tag)) return n("keep-alive", {
            props: t.componentOptions.propsData
        })
    }

    function ep(n) {
        n.elm._moveCb && n.elm._moveCb();
        n.elm._enterCb && n.elm._enterCb()
    }

    function op(n) {
        n.data.newPos = n.elm.getBoundingClientRect()
    }

    function sp(n) {
        var i = n.data.pos,
            r = n.data.newPos,
            u = i.left - r.left,
            f = i.top - r.top,
            t;
        (u || f) && (n.data.moved = !0, t = n.elm.style, t.transform = t.WebkitTransform = "translate(" + u + "px," + f + "px)", t.transitionDuration = "0s")
    }

    function hp(n, t) {
        var i = t ? tk : nk;
        return n.replace(i, function (n) {
            return gb[n]
        })
    }

    function sc(n, t, i) {
        return {
            type: 1,
            tag: n,
            attrsList: t,
            attrsMap: function (n) {
                for (var i = {}, t = 0, r = n.length; t < r; t++) i[n[t].name] = n[t].value;
                return i
            }(t),
            parent: i,
            children: []
        }
    }

    function cp(n, t) {
        function s(n) {
            n.pre && (e = !1);
            fo(n.tag) && (o = !1);
            for (var i = 0; i < uo.length; i++) uo[i](n, t)
        }
        ev = t.warn || rh;
        fo = t.isPreTag || g;
        eo = t.mustUseProp || g;
        sv = t.getTagNamespace || g;
        io = ki(t.modules, "transformNode");
        ro = ki(t.modules, "preTransformNode");
        uo = ki(t.modules, "postTransformNode");
        ov = t.delimiters;
        var u, i, r = [],
            h = !1 !== t.preserveWhitespace,
            e = !1,
            o = !1;
        return function (n, t) {
            function r(t) {
                i += t;
                n = n.substring(t)
            }

            function h(n, r, f) {
                var o, s, h;
                if (null == r && (r = i), null == f && (f = i), n && (s = n.toLowerCase()), n)
                    for (o = e.length - 1; o >= 0 && e[o].lowerCasedTag !== s; o--);
                else o = 0;
                if (o >= 0) {
                    for (h = e.length - 1; h >= o; h--) t.end && t.end(e[h].tag, r, f);
                    e.length = o;
                    u = o && e[o - 1].tag
                } else "br" === s ? t.start && t.start(n, [], !0, r, f) : "p" === s && (t.start && t.start(n, [], !1, r, f), t.end && t.end(n, r, f))
            }
            for (var f, c, v, y, l, d, p, w, u, e = [], tt = t.expectHTML, it = t.isUnaryTag || g, rt = t.canBeLeftOpenTag || g, i = 0; n;) {
                if (w = n, u && cv(u)) {
                    var b = 0,
                        o = u.toLowerCase(),
                        ut = lv[o] || (lv[o] = new RegExp("([\\s\\S]*?)(<\/" + o + "[^>]*>)", "i")),
                        k = n.replace(ut, function (n, i, r) {
                            return b = r.length, cv(o) || "noscript" === o || (i = i.replace(/<!--([\s\S]*?)-->/g, "$1").replace(/<!\[CDATA\[([\s\S]*?)]]>/g, "$1")), av(o, i) && (i = i.slice(1)), t.chars && t.chars(i), ""
                        });
                    i += n.length - k.length;
                    n = k;
                    h(o, i - b, i)
                } else {
                    if (f = n.indexOf("<"), 0 === f) {
                        if (rv.test(n) && (c = n.indexOf("-->"), c >= 0)) {
                            t.shouldKeepComment && t.comment(n.substring(4, c));
                            r(c + 3);
                            continue
                        }
                        if (uv.test(n) && (v = n.indexOf("]>"), v >= 0)) {
                            r(v + 2);
                            continue
                        }
                        if (y = n.match(db), y) {
                            r(y[0].length);
                            continue
                        }
                        if (l = n.match(iv), l) {
                            d = i;
                            r(l[0].length);
                            h(l[1], d, i);
                            continue
                        }
                        if (p = function () {
                                var f = n.match(tv),
                                    t, u, e;
                                if (f) {
                                    for (t = {
                                            tagName: f[1],
                                            attrs: [],
                                            start: i
                                        }, r(f[0].length); !(u = n.match(kb)) && (e = n.match(bb));) r(e[0].length), t.attrs.push(e);
                                    if (u) return t.unarySlash = u[1], r(u[0].length), t.end = i, t
                                }
                            }(), p) {
                            ! function (n) {
                                var r = n.tagName,
                                    v = n.unarySlash,
                                    i, l, a;
                                tt && ("p" === u && wb(r) && h(u), rt(r) && u === r && h(r));
                                for (var s = it(r) || !!v, c = n.attrs.length, o = new Array(c), f = 0; f < c; f++) i = n.attrs[f], fv && -1 === i[0].indexOf('""') && ("" === i[3] && delete i[3], "" === i[4] && delete i[4], "" === i[5] && delete i[5]), l = i[3] || i[4] || i[5] || "", a = "a" === r && "href" === i[1] ? t.shouldDecodeNewlinesForHref : t.shouldDecodeNewlines, o[f] = {
                                    name: i[1],
                                    value: hp(l, a)
                                };
                                s || (e.push({
                                    tag: r,
                                    lowerCasedTag: r.toLowerCase(),
                                    attrs: o
                                }), u = r);
                                t.start && t.start(r, o, s, n.start, n.end)
                            }(p);
                            av(u, n) && r(1);
                            continue
                        }
                    }
                    var a = void 0,
                        s = void 0,
                        nt = void 0;
                    if (f >= 0) {
                        for (s = n.slice(f); !(iv.test(s) || tv.test(s) || rv.test(s) || uv.test(s) || (nt = s.indexOf("<", 1)) < 0);) f += nt, s = n.slice(f);
                        a = n.substring(0, f);
                        r(f)
                    }
                    f < 0 && (a = n, n = "");
                    t.chars && a && t.chars(a)
                }
                if (n === w) {
                    t.chars && t.chars(n);
                    break
                }
            }
            h()
        }(n, {
            warn: ev,
            expectHTML: t.expectHTML,
            isUnaryTag: t.isUnaryTag,
            canBeLeftOpenTag: t.canBeLeftOpenTag,
            shouldDecodeNewlines: t.shouldDecodeNewlines,
            shouldDecodeNewlinesForHref: t.shouldDecodeNewlinesForHref,
            shouldKeepComment: t.comments,
            start: function (n, h, c) {
                var v = i && i.ns || sv(n),
                    l, a, y;
                for (hi && "svg" === v && (h = function (n) {
                        for (var t, r = [], i = 0; i < n.length; i++) t = n[i], ok.test(t.name) || (t.name = t.name.replace(sk, ""), r.push(t));
                        return r
                    }(h)), l = sc(n, h, i), v && (l.ns = v), function (n) {
                        return "style" === n.tag || "script" === n.tag && (!n.attrsMap.type || "text/javascript" === n.attrsMap.type)
                    }(l) && !di() && (l.forbidden = !0), a = 0; a < ro.length; a++) l = ro[a](l, t) || l;
                (e || (! function (n) {
                    null != f(n, "v-pre") && (n.pre = !0)
                }(l), l.pre && (e = !0)), fo(l.tag) && (o = !0), e ? function (n) {
                    var i = n.attrsList.length,
                        r, t;
                    if (i)
                        for (r = n.attrs = new Array(i), t = 0; t < i; t++) r[t] = {
                            name: n.attrsList[t].name,
                            value: JSON.stringify(n.attrsList[t].value)
                        };
                    else n.pre || (n.plain = !0)
                }(l) : l.processed || (hc(l), function (n) {
                    var t = f(n, "v-if"),
                        i;
                    t ? (n.if = t, oi(n, {
                        exp: t,
                        block: n
                    })) : (null != f(n, "v-else") && (n.else = !0), i = f(n, "v-else-if"), i && (n.elseif = i))
                }(l), function (n) {
                    null != f(n, "v-once") && (n.once = !0)
                }(l), cr(l, t)), u ? r.length || u.if && (l.elseif || l.else) && oi(u, {
                    exp: l.elseif,
                    block: l
                }) : u = l, i && !l.forbidden) && (l.elseif || l.else ? ! function (n, t) {
                    var i = function (n) {
                        for (var t = n.length; t--;) {
                            if (1 === n[t].type) return n[t];
                            n.pop()
                        }
                    }(t.children);
                    i && i.if && oi(i, {
                        exp: n.elseif,
                        block: n
                    })
                }(l, i) : l.slotScope ? (i.plain = !1, y = l.slotTarget || '"default"', (i.scopedSlots || (i.scopedSlots = {}))[y] = l) : (i.children.push(l), l.parent = i));
                c ? s(l) : (i = l, r.push(l))
            },
            end: function () {
                var n = r[r.length - 1],
                    t = n.children[n.children.length - 1];
                t && 3 === t.type && " " === t.text && !o && n.children.pop();
                r.length -= 1;
                i = r[r.length - 1];
                s(n)
            },
            chars: function (n) {
                var t, r;
                i && (!hi || "textarea" !== i.tag || i.attrsMap.placeholder !== n) && (t = i.children, (n = o || n.trim() ? function (n) {
                    return "script" === n.tag || "style" === n.tag
                }(i) ? n : ek(n) : h && t.length ? " " : "") && (!e && " " !== n && (r = function (n, t) {
                    var o = t ? cb(t) : hb,
                        h;
                    if (o.test(n)) {
                        for (var r, s, u, f = [], e = [], i = o.lastIndex = 0; r = o.exec(n);)(s = r.index) > i && (e.push(u = n.slice(i, s)), f.push(JSON.stringify(u))), h = ef(r[1].trim()), f.push("_s(" + h + ")"), e.push({
                            "@binding": h
                        }), i = s + r[0].length;
                        return i < n.length && (e.push(u = n.slice(i)), f.push(JSON.stringify(u))), {
                            expression: f.join("+"),
                            tokens: e
                        }
                    }
                }(n, ov)) ? t.push({
                    type: 2,
                    expression: r.expression,
                    tokens: r.tokens,
                    text: n
                }) : " " === n && t.length && " " === t[t.length - 1].text || t.push({
                    type: 3,
                    text: n
                })))
            },
            comment: function (n) {
                i.children.push({
                    type: 3,
                    text: n,
                    isComment: !0
                })
            }
        }), u
    }

    function cr(n, t) {
        ! function (n) {
            var t = y(n, "key");
            t && (n.key = t)
        }(n);
        n.plain = !n.key && !n.attrsList.length,
            function (n) {
                var t = y(n, "ref");
                t && (n.ref = t, n.refInFor = function (n) {
                    for (var t = n; t;) {
                        if (void 0 !== t.for) return !0;
                        t = t.parent
                    }
                    return !1
                }(n))
            }(n),
            function (n) {
                var i, t;
                "slot" === n.tag ? n.slotName = y(n, "name") : ("template" === n.tag ? (i = f(n, "scope"), n.slotScope = i || f(n, "slot-scope")) : (i = f(n, "slot-scope")) && (n.slotScope = i), t = y(n, "slot"), t && (n.slotTarget = '""' === t ? '"default"' : t, "template" === n.tag || n.slotScope || of (n, "slot", t)))
            }(n),
            function (n) {
                var t;
                (t = y(n, "is")) && (n.component = t);
                null != f(n, "inline-template") && (n.inlineTemplate = !0)
            }(n);
        for (var i = 0; i < io.length; i++) n = io[i](n, t) || n;
        ! function (n) {
            for (var t, c, i, r, e, o = n.attrsList, s, f, u = 0, h = o.length; u < h; u++)(t = c = o[u].name, i = o[u].value, yv.test(t)) ? (n.hasBindings = !0, (r = function (n) {
                var i = n.match(bv),
                    t;
                if (i) return t = {}, i.forEach(function (n) {
                    t[n.slice(1)] = !0
                }), t
            }(t)) && (t = t.replace(bv, "")), wv.test(t)) ? (t = t.replace(wv, ""), i = ef(i), e = !1, r && (r.prop && (e = !0, "innerHtml" === (t = it(t)) && (t = "innerHTML")), r.camel && (t = it(t)), r.sync && kt(n, "update:" + it(t), ei(i, "$event"))), e || !n.component && eo(n.tag, n.attrsMap.type, t) ? bt(n, t, i) : of (n, t, i)) : vv.test(t) ? (t = t.replace(vv, ""), kt(n, t, i, r, !1)) : (s = (t = t.replace(yv, "")).match(fk), f = s && s[1], f && (t = t.slice(0, -(f.length + 1))), rp(n, t, c, i, f, r)) : ( of (n, t, JSON.stringify(i)), !n.component && "muted" === t && eo(n.tag, n.attrsMap.type, t) && bt(n, t, "true"))
        }(n)
    }

    function hc(n) {
        var r, t;
        (r = f(n, "v-for")) && (t = function (n) {
            var u = n.match(rk),
                t, r, i;
            if (u) return t = {}, t.for = u[2].trim(), r = u[1].trim().replace(uk, ""), i = r.match(pv), i ? (t.alias = r.replace(pv, ""), t.iterator1 = i[1].trim(), i[2] && (t.iterator2 = i[2].trim())) : t.alias = r, t
        }(r), t && i(n, t))
    }

    function oi(n, t) {
        n.ifConditions || (n.ifConditions = []);
        n.ifConditions.push(t)
    }

    function bf(n) {
        return sc(n.tag, n.attrsList.slice(), n.parent)
    }

    function kf(n) {
        var t, f, r, i, e, u;
        if (n.static = function (n) {
                return 2 === n.type ? !1 : 3 === n.type ? !0 : !(!n.pre && (n.hasBindings || n.if || n.for || ap(n.tag) || !oo(n.tag) || function (n) {
                    for (; n.parent;) {
                        if ("template" !== (n = n.parent).tag) return !1;
                        if (n.for) return !0
                    }
                    return !1
                }(n) || !Object.keys(n).every(hv)))
            }(n), 1 === n.type) {
            if (!oo(n.tag) && "slot" !== n.tag && null == n.attrsMap["inline-template"]) return;
            for (t = 0, f = n.children.length; t < f; t++) r = n.children[t], kf(r), r.static || (n.static = !1);
            if (n.ifConditions)
                for (i = 1, e = n.ifConditions.length; i < e; i++) u = n.ifConditions[i].block, kf(u), u.static || (n.static = !1)
        }
    }

    function df(n, t) {
        var i, u, r, f;
        if (1 === n.type) {
            if ((n.static || n.once) && (n.staticInFor = t), n.static && n.children.length && (1 !== n.children.length || 3 !== n.children[0].type)) return void(n.staticRoot = !0);
            if (n.staticRoot = !1, n.children)
                for (i = 0, u = n.children.length; i < u; i++) df(n.children[i], t || !!n.for);
            if (n.ifConditions)
                for (r = 1, f = n.ifConditions.length; r < f; r++) df(n.ifConditions[r].block, t)
        }
    }

    function cc(n, t) {
        var r = t ? "nativeOn:{" : "on:{";
        for (var i in n) r += '"' + i + '":' + lc(i, n[i]) + ",";
        return r.slice(0, -1) + "}"
    }

    function lc(n, t) {
        var f, e, i, s;
        if (!t) return "function(){}";
        if (Array.isArray(t)) return "[" + t.map(function (t) {
            return lc(n, t)
        }).join(",") + "]";
        if (f = ak.test(t.value), e = lk.test(t.value), t.modifiers) {
            var o = "",
                r = "",
                u = [];
            for (i in t.modifiers) gv[i] ? (r += gv[i], dv[i] && u.push(i)) : "exact" === i ? (s = t.modifiers, r += st(["ctrl", "shift", "alt", "meta"].filter(function (n) {
                return !s[n]
            }).map(function (n) {
                return "$event." + n + "Key"
            }).join("||"))) : u.push(i);
            return u.length && (o += function (n) {
                return "if(!('button' in $event)&&" + n.map(lp).join("&&") + ")return null;"
            }(u)), r && (o += r), "function($event){" + o + (f ? t.value + "($event)" : e ? "(" + t.value + ")($event)" : t.value) + "}"
        }
        return f || e ? t.value : "function($event){" + t.value + "}"
    }

    function lp(n) {
        var t = parseInt(n, 10),
            i;
        return t ? "$event.keyCode!==" + t : (i = dv[n], "_k($event.keyCode," + JSON.stringify(n) + "," + JSON.stringify(i) + ",$event.key)")
    }

    function ac(n, t) {
        var i = new yk(t);
        return {
            render: "with(this){return " + (n ? ft(n, i) : '_c("div")') + "}",
            staticRenderFns: i.staticRenderFns
        }
    }

    function ft(n, t) {
        var i, u, f, r;
        if (n.staticRoot && !n.staticProcessed) return vc(n, t);
        if (n.once && !n.onceProcessed) return yc(n, t);
        if (n.for && !n.forProcessed) return function (n, t, i, r) {
            var u = n.for,
                f = n.alias,
                e = n.iterator1 ? "," + n.iterator1 : "",
                o = n.iterator2 ? "," + n.iterator2 : "";
            return n.forProcessed = !0, (r || "_l") + "((" + u + "),function(" + f + e + o + "){return " + (i || ft)(n, t) + "})"
        }(n, t);
        if (n.if && !n.ifProcessed) return pc(n, t);
        if ("template" !== n.tag || n.slotTarget) {
            if ("slot" === n.tag) return function (n, t) {
                var e = n.slotName || '"default"',
                    u = si(n, t),
                    i = "_t(" + e + (u ? "," + u : ""),
                    r = n.attrs && "{" + n.attrs.map(function (n) {
                        return it(n.name) + ":" + n.value
                    }).join(",") + "}",
                    f = n.attrsMap["v-bind"];
                return (r || f) && !u && (i += ",null"), r && (i += "," + r), f && (i += (r ? "" : ",null") + "," + f), i + ")"
            }(n, t);
            for (n.component ? i = function (n, t, i) {
                    var r = t.inlineTemplate ? null : si(t, i, !0);
                    return "_c(" + n + "," + bc(t, i) + (r ? "," + r : "") + ")"
                }(n.component, n, t) : (u = n.plain ? void 0 : bc(n, t), f = n.inlineTemplate ? null : si(n, t, !0), i = "_c('" + n.tag + "'" + (u ? "," + u : "") + (f ? "," + f : "") + ")"), r = 0; r < t.transforms.length; r++) i = t.transforms[r](n, i);
            return i
        }
        return si(n, t) || "void 0"
    }

    function vc(n, t) {
        return n.staticProcessed = !0, t.staticRenderFns.push("with(this){return " + ft(n, t) + "}"), "_m(" + (t.staticRenderFns.length - 1) + (n.staticInFor ? ",true" : "") + ")"
    }

    function yc(n, t) {
        if (n.onceProcessed = !0, n.if && !n.ifProcessed) return pc(n, t);
        if (n.staticInFor) {
            for (var r = "", i = n.parent; i;) {
                if (i.for) {
                    r = i.key;
                    break
                }
                i = i.parent
            }
            return r ? "_o(" + ft(n, t) + "," + t.onceId++ + "," + r + ")" : ft(n, t)
        }
        return vc(n, t)
    }

    function pc(n, t, i, r) {
        return n.ifProcessed = !0, wc(n.ifConditions.slice(), t, i, r)
    }

    function wc(n, t, i, r) {
        function f(n) {
            return i ? i(n, t) : n.once ? yc(n, t) : ft(n, t)
        }
        if (!n.length) return r || "_e()";
        var u = n.shift();
        return u.exp ? "(" + u.exp + ")?" + f(u.block) + ":" + wc(n, t, i, r) : "" + f(u.block)
    }

    function bc(n, t) {
        var i = "{",
            f = function (n, t) {
                var u = n.directives,
                    r, h, i, f, e, o, s;
                if (u) {
                    for (e = "directives:[", o = !1, r = 0, h = u.length; r < h; r++) i = u[r], f = !0, s = t.directives[i.name], s && (f = !!s(n, i, t.warn)), f && (o = !0, e += '{name:"' + i.name + '",rawName:"' + i.rawName + '"' + (i.value ? ",value:(" + i.value + "),expression:" + JSON.stringify(i.value) : "") + (i.arg ? ',arg:"' + i.arg + '"' : "") + (i.modifiers ? ",modifiers:" + JSON.stringify(i.modifiers) : "") + "},");
                    if (o) return e.slice(0, -1) + "]"
                }
            }(n, t),
            r, u;
        for (f && (i += f + ","), n.key && (i += "key:" + n.key + ","), n.ref && (i += "ref:" + n.ref + ","), n.refInFor && (i += "refInFor:true,"), n.pre && (i += "pre:true,"), n.component && (i += 'tag:"' + n.tag + '",'), r = 0; r < t.dataGenFns.length; r++) i += t.dataGenFns[r](n);
        return (n.attrs && (i += "attrs:{" + gc(n.attrs) + "},"), n.props && (i += "domProps:{" + gc(n.props) + "},"), n.events && (i += cc(n.events, !1, t.warn) + ","), n.nativeEvents && (i += cc(n.nativeEvents, !0, t.warn) + ","), n.slotTarget && !n.slotScope && (i += "slot:" + n.slotTarget + ","), n.scopedSlots && (i += function (n, t) {
            return "scopedSlots:_u([" + Object.keys(n).map(function (i) {
                return kc(i, n[i], t)
            }).join(",") + "])"
        }(n.scopedSlots, t) + ","), n.model && (i += "model:{value:" + n.model.value + ",callback:" + n.model.callback + ",expression:" + n.model.expression + "},"), n.inlineTemplate) && (u = function (n, t) {
            var r = n.children[0],
                i;
            if (1 === r.type) return i = ac(r, t.options), "inlineTemplate:{render:function(){" + i.render + "},staticRenderFns:[" + i.staticRenderFns.map(function (n) {
                return "function(){" + n + "}"
            }).join(",") + "]}"
        }(n, t), u && (i += u + ",")), i = i.replace(/,$/, "") + "}", n.wrapData && (i = n.wrapData(i)), n.wrapListeners && (i = n.wrapListeners(i)), i
    }

    function kc(n, t, i) {
        return t.for && !t.forProcessed ? function (n, t, i) {
            var r = t.for,
                u = t.alias,
                f = t.iterator1 ? "," + t.iterator1 : "",
                e = t.iterator2 ? "," + t.iterator2 : "";
            return t.forProcessed = !0, "_l((" + r + "),function(" + u + f + e + "){return " + kc(n, t, i) + "})"
        }(n, t, i) : "{key:" + n + ",fn:" + ("function(" + String(t.slotScope) + "){return " + ("template" === t.tag ? t.if ? t.if+"?" + (si(t, i) || "undefined") + ":undefined" : si(t, i) || "undefined" : ft(t, i)) + "}") + "}"
    }

    function si(n, t, i, r, u) {
        var f = n.children,
            e, o, s;
        if (f.length) return (e = f[0], 1 === f.length && e.for && "template" !== e.tag && "slot" !== e.tag) ? (r || ft)(e, t) : (o = i ? function (n, t) {
            for (var i, r = 0, u = 0; u < n.length; u++)
                if (i = n[u], 1 === i.type) {
                    if (dc(i) || i.ifConditions && i.ifConditions.some(function (n) {
                            return dc(n.block)
                        })) {
                        r = 2;
                        break
                    }(t(i) || i.ifConditions && i.ifConditions.some(function (n) {
                        return t(n.block)
                    })) && (r = 1)
                } return r
        }(f, t.maybeComponent) : 0, s = u || function (n, t) {
            return 1 === n.type ? ft(n, t) : 3 === n.type && n.isComment ? function (n) {
                return "_e(" + JSON.stringify(n.text) + ")"
            }(n) : function (n) {
                return "_v(" + (2 === n.type ? n.expression : nl(JSON.stringify(n.text))) + ")"
            }(n)
        }, "[" + f.map(function (n) {
            return s(n, t)
        }).join(",") + "]" + (o ? "," + o : ""))
    }

    function dc(n) {
        return void 0 !== n.for || "template" === n.tag || "slot" === n.tag
    }

    function gc(n) {
        for (var r, i = "", t = 0; t < n.length; t++) r = n[t], i += '"' + r.name + '":' + nl(r.value) + ",";
        return i.slice(0, -1)
    }

    function nl(n) {
        return n.replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029")
    }

    function tl(n, t) {
        try {
            return new Function(n)
        } catch (i) {
            return t.push({
                err: i,
                code: n
            }), o
        }
    }

    function il(n) {
        return uu = uu || document.createElement("div"), uu.innerHTML = n ? '<a href="\n"/>' : '<div a="\n"/>', uu.innerHTML.indexOf("&#10;") > 0
    }
    var p = Object.freeze({}),
        rl = Object.prototype.toString,
        ap = e("slot,component", !0),
        vp = e("key,ref,slot,slot-scope,is"),
        yp = Object.prototype.hasOwnProperty,
        pp = /-(\w)/g,
        it = k(function (n) {
            return n.replace(pp, function (n, t) {
                return t ? t.toUpperCase() : ""
            })
        }),
        wp = k(function (n) {
            return n.charAt(0).toUpperCase() + n.slice(1)
        }),
        bp = /\B([A-Z])/g,
        gf = k(function (n) {
            return n.replace(bp, "-$1").toLowerCase()
        }),
        g = function () {
            return !1
        },
        ul = function (n) {
            return n
        },
        fl = "data-server-rendered",
        lr = ["component", "directive", "filter"],
        el = ["beforeCreate", "created", "beforeMount", "mounted", "beforeUpdate", "updated", "beforeDestroy", "destroyed", "activated", "deactivated", "errorCaptured"],
        w = {
            optionMergeStrategies: Object.create(null),
            silent: !1,
            productionTip: !1,
            devtools: !1,
            performance: !1,
            errorHandler: null,
            warnHandler: null,
            ignoredElements: [],
            keyCodes: Object.create(null),
            isReservedTag: g,
            isReservedAttr: g,
            isUnknownElement: g,
            getTagNamespace: o,
            parsePlatformTagName: ul,
            mustUseProp: g,
            _lifecycleHooks: el
        },
        kp = /[^\w.$]/,
        dp = "__proto__" in {},
        l = "undefined" != typeof window,
        ol = "undefined" != typeof WXEnvironment && !!WXEnvironment.platform,
        sl = ol && WXEnvironment.platform.toLowerCase(),
        b = l && window.navigator.userAgent.toLowerCase(),
        hi = b && /msie|trident/.test(b),
        ci = b && b.indexOf("msie 9.0") > 0,
        hl = b && b.indexOf("edge/") > 0,
        gp = b && b.indexOf("android") > 0 || "android" === sl,
        nw = b && /iphone|ipad|ipod|ios/.test(b) || "ios" === sl,
        ne = (b && /chrome\/\d+/.test(b), {}.watch),
        cl = !1,
        te, nt, se, pl, wl, ot, dl, ve, ta, ka;
    if (l) try {
        te = {};
        Object.defineProperty(te, "passive", {
            get: function () {
                cl = !0
            }
        });
        window.addEventListener("test-passive", null, te)
    } catch (t) {}
    var ie, ar, di = function () {
            return void 0 === ie && (ie = !l && "undefined" != typeof global && "server" === global.process.env.VUE_ENV), ie
        },
        vr = l && window.__VUE_DEVTOOLS_GLOBAL_HOOK__,
        ll = "undefined" != typeof Symbol && ii(Symbol) && "undefined" != typeof Reflect && ii(Reflect.ownKeys);
    ar = "undefined" != typeof Set && ii(Set) ? Set : function () {
        function n() {
            this.set = Object.create(null)
        }
        return n.prototype.has = function (n) {
            return !0 === this.set[n]
        }, n.prototype.add = function (n) {
            this.set[n] = !0
        }, n.prototype.clear = function () {
            this.set = Object.create(null)
        }, n
    }();
    var tw = o,
        iw = 0,
        s = function () {
            this.id = iw++;
            this.subs = []
        };
    s.prototype.addSub = function (n) {
        this.subs.push(n)
    };
    s.prototype.removeSub = function (n) {
        ht(this.subs, n)
    };
    s.prototype.depend = function () {
        s.target && s.target.addDep(this)
    };
    s.prototype.notify = function () {
        for (var t = this.subs.slice(), n = 0, i = t.length; n < i; n++) t[n].update()
    };
    s.target = null;
    var al = [],
        a = function (n, t, i, r, u, f, e, o) {
            this.tag = n;
            this.data = t;
            this.children = i;
            this.text = r;
            this.elm = u;
            this.ns = void 0;
            this.context = f;
            this.fnContext = void 0;
            this.fnOptions = void 0;
            this.fnScopeId = void 0;
            this.key = t && t.key;
            this.componentOptions = e;
            this.componentInstance = void 0;
            this.parent = void 0;
            this.raw = !1;
            this.isStatic = !1;
            this.isRootInsert = !0;
            this.isComment = !1;
            this.isCloned = !1;
            this.isOnce = !1;
            this.asyncFactory = o;
            this.asyncMeta = void 0;
            this.isAsyncPlaceholder = !1
        },
        vl = {
            child: {
                configurable: !0
            }
        };
    vl.child.get = function () {
        return this.componentInstance
    };
    Object.defineProperties(a.prototype, vl);
    var gt = function (n) {
            void 0 === n && (n = "");
            var t = new a;
            return t.text = n, t.isComment = !0, t
        },
        yl = Array.prototype,
        re = Object.create(yl);
    ["push", "pop", "shift", "unshift", "splice", "sort", "reverse"].forEach(function (n) {
        var t = yl[n];
        eu(re, n, function () {
            for (var u, e, f, i = [], r = arguments.length; r--;) i[r] = arguments[r];
            e = t.apply(this, i);
            f = this.__ob__;
            switch (n) {
                case "push":
                case "unshift":
                    u = i;
                    break;
                case "splice":
                    u = i.slice(2)
            }
            return u && f.observeArray(u), f.dep.notify(), e
        })
    });
    var rw = Object.getOwnPropertyNames(re),
        rt = {
            shouldConvert: !0
        },
        yr = function (n) {
            (this.value = n, this.dep = new s, this.vmCount = 0, eu(n, "__ob__", this), Array.isArray(n)) ? ((dp ? uy : fy)(n, re, rw), this.observeArray(n)) : this.walk(n)
        };
    yr.prototype.walk = function (n) {
        for (var i = Object.keys(n), t = 0; t < i.length; t++) yt(n, i[t], n[i[t]])
    };
    yr.prototype.observeArray = function (n) {
        for (var t = 0, i = n.length; t < i; t++) ui(n[t])
    };
    nt = w.optionMergeStrategies;
    nt.data = function (n, t, i) {
        return i ? hu(n, t, i) : t && "function" != typeof t ? n : hu(n, t)
    };
    el.forEach(function (n) {
        nt[n] = ey
    });
    lr.forEach(function (n) {
        nt[n + "s"] = oy
    });
    nt.watch = function (n, t) {
        var u, e, r, f;
        if (n === ne && (n = void 0), t === ne && (t = void 0), !t) return Object.create(n || null);
        if (!n) return t;
        u = {};
        i(u, n);
        for (e in t) r = u[e], f = t[e], r && !Array.isArray(r) && (r = [r]), u[e] = r ? r.concat(f) : Array.isArray(f) ? f : [f];
        return u
    };
    nt.props = nt.methods = nt.inject = nt.computed = function (n, t) {
        if (!n) return t;
        var r = Object.create(null);
        return i(r, n), t && i(r, t), r
    };
    nt.provide = hu;
    var ue, gi, uw = function (n, t) {
            return void 0 === t ? n : t
        },
        fe = [],
        ee = !1,
        oe = !1;
    "undefined" != typeof setImmediate && ii(setImmediate) ? gi = function () {
        setImmediate(fr)
    } : "undefined" != typeof MessageChannel && (ii(MessageChannel) || "[object MessageChannelConstructor]" === MessageChannel.toString()) ? (se = new MessageChannel, pl = se.port2, se.port1.onmessage = fr, gi = function () {
        pl.postMessage(1)
    }) : gi = function () {
        setTimeout(fr, 0)
    };
    "undefined" != typeof Promise && ii(Promise) ? (wl = Promise.resolve(), ue = function () {
        wl.then(fr);
        nw && setTimeout(o)
    }) : ue = gi;
    var nr, bl = new ar,
        kl = k(function (n) {
            var t = "&" === n.charAt(0),
                i = "~" === (n = t ? n.slice(1) : n).charAt(0),
                r = "!" === (n = i ? n.slice(1) : n).charAt(0);
            return n = r ? n.slice(1) : n, {
                name: n,
                once: i,
                capture: r,
                passive: t
            }
        }),
        ni = null,
        et = [],
        he = [],
        pr = {},
        ce = !1,
        le = !1,
        li = 0,
        fw = 0,
        tt = function (n, t, i, r, u) {
            this.vm = n;
            u && (n._watcher = this);
            n._watchers.push(this);
            r ? (this.deep = !!r.deep, this.user = !!r.user, this.lazy = !!r.lazy, this.sync = !!r.sync) : this.deep = this.user = this.lazy = this.sync = !1;
            this.cb = i;
            this.id = ++fw;
            this.active = !0;
            this.dirty = this.lazy;
            this.deps = [];
            this.newDeps = [];
            this.depIds = new ar;
            this.newDepIds = new ar;
            this.expression = "";
            "function" == typeof t ? this.getter = t : (this.getter = function (n) {
                if (!kp.test(n)) {
                    var t = n.split(".");
                    return function (n) {
                        for (var i = 0; i < t.length; i++) {
                            if (!n) return;
                            n = n[t[i]]
                        }
                        return n
                    }
                }
            }(t), this.getter || (this.getter = function () {}));
            this.value = this.lazy ? void 0 : this.get()
        };
    tt.prototype.get = function () {
        ! function (n) {
            s.target && al.push(s.target);
            s.target = n
        }(this);
        var n, t = this.vm;
        try {
            n = this.getter.call(t, t)
        } catch (n) {
            if (!this.user) throw n;
            ct(n, t, 'getter for watcher "' + this.expression + '"')
        } finally {
            this.deep && bo(n);
            s.target = al.pop();
            this.cleanupDeps()
        }
        return n
    };
    tt.prototype.addDep = function (n) {
        var t = n.id;
        this.newDepIds.has(t) || (this.newDepIds.add(t), this.newDeps.push(n), this.depIds.has(t) || n.addSub(this))
    };
    tt.prototype.cleanupDeps = function () {
        for (var i, n, t = this.deps.length; t--;) i = this.deps[t], this.newDepIds.has(i.id) || i.removeSub(this);
        n = this.depIds;
        this.depIds = this.newDepIds;
        this.newDepIds = n;
        this.newDepIds.clear();
        n = this.deps;
        this.deps = this.newDeps;
        this.newDeps = n;
        this.newDeps.length = 0
    };
    tt.prototype.update = function () {
        this.lazy ? this.dirty = !0 : this.sync ? this.run() : function (n) {
            var i = n.id,
                t;
            if (null == pr[i]) {
                if (pr[i] = !0, le) {
                    for (t = et.length - 1; t > li && et[t].id > n.id;) t--;
                    et.splice(t + 1, 0, n)
                } else et.push(n);
                ce || (ce = !0, au(ly))
            }
        }(this)
    };
    tt.prototype.run = function () {
        var n, t;
        if (this.active && (n = this.get(), n !== this.value || h(n) || this.deep))
            if (t = this.value, this.value = n, this.user) try {
                this.cb.call(this.vm, n, t)
            } catch (n) {
                ct(n, this.vm, 'callback for watcher "' + this.expression + '"')
            } else this.cb.call(this.vm, n, t)
    };
    tt.prototype.evaluate = function () {
        this.value = this.get();
        this.dirty = !1
    };
    tt.prototype.depend = function () {
        for (var n = this.deps.length; n--;) this.deps[n].depend()
    };
    tt.prototype.teardown = function () {
        if (this.active) {
            this.vm._isBeingDestroyed || ht(this.vm._watchers, this);
            for (var n = this.deps.length; n--;) this.deps[n].removeSub(this);
            this.active = !1
        }
    };
    ot = {
        enumerable: !0,
        configurable: !0,
        get: o,
        set: o
    };
    dl = {
        lazy: !0
    };
    ls(as.prototype);
    var ae = {
            init: function (t, i, r, u) {
                if (!t.componentInstance || t.componentInstance._isDestroyed)(t.componentInstance = function (t, i, r, u) {
                    var f = {
                            _isComponent: !0,
                            parent: i,
                            _parentVnode: t,
                            _parentElm: r || null,
                            _refElm: u || null
                        },
                        e = t.data.inlineTemplate;
                    return n(e) && (f.render = e.render, f.staticRenderFns = e.staticRenderFns), new t.componentOptions.Ctor(f)
                }(t, ni, r, u)).$mount(i ? t.elm : void 0, i);
                else if (t.data.keepAlive) {
                    var f = t;
                    ae.prepatch(f, f)
                }
            },
            prepatch: function (n, t) {
                var i = t.componentOptions;
                ! function (n, t, i, r, u) {
                    var h = !!(u || n.$options._renderChildren || r.data.scopedSlots || n.$scopedSlots !== p),
                        e, s;
                    if (n.$options._parentVnode = r, n.$vnode = r, n._vnode && (n._vnode.parent = r), n.$options._renderChildren = u, n.$attrs = r.data && r.data.attrs || p, n.$listeners = i || p, t && n.$options.props) {
                        rt.shouldConvert = !1;
                        for (var c = n._props, o = n.$options._propKeys || [], f = 0; f < o.length; f++) e = o[f], c[e] = lu(e, n.$options.props, t, n);
                        rt.shouldConvert = !0;
                        n.$options.propsData = t
                    }
                    i && (s = n.$options._parentListeners, n.$options._parentListeners = i, is(n, i, s));
                    h && (n.$slots = wu(u, r.context), n.$forceUpdate())
                }(t.componentInstance = n.componentInstance, i.propsData, i.listeners, t, i.children)
            },
            insert: function (n) {
                var i = n.context,
                    t = n.componentInstance;
                t._isMounted || (t._isMounted = !0, d(t, "mounted"));
                n.data.keepAlive && (i._isMounted ? function (n) {
                    n._inactive = !1;
                    he.push(n)
                }(t) : bu(t, !0))
            },
            destroy: function (n) {
                var t = n.componentInstance;
                t._isDestroyed || (n.data.keepAlive ? fs(t, !0) : t.$destroy())
            }
        },
        gl = Object.keys(ae),
        ew = 1,
        na = 2,
        ow = 0;
    ! function (n) {
        n.prototype._init = function (n) {
            this._uid = ow++;
            this._isVue = !0;
            n && n._isComponent ? function (n, t) {
                var i = n.$options = Object.create(n.constructor.options),
                    u = t._parentVnode,
                    r;
                i.parent = t.parent;
                i._parentVnode = u;
                i._parentElm = t._parentElm;
                i._refElm = t._refElm;
                r = u.componentOptions;
                i.propsData = r.propsData;
                i._parentListeners = r.listeners;
                i._renderChildren = r.children;
                i._componentTag = r.tag;
                t.render && (i.render = t.render, i.staticRenderFns = t.staticRenderFns)
            }(this, n) : this.$options = pt(gu(this.constructor), n || {}, this);
            this._renderProxy = this;
            this._self = this,
                function (n) {
                    var i = n.$options,
                        t = i.parent;
                    if (t && !i.abstract) {
                        for (; t.$options.abstract && t.$parent;) t = t.$parent;
                        t.$children.push(n)
                    }
                    n.$parent = t;
                    n.$root = t ? t.$root : n;
                    n.$children = [];
                    n.$refs = {};
                    n._watcher = null;
                    n._inactive = null;
                    n._directInactive = !1;
                    n._isMounted = !1;
                    n._isDestroyed = !1;
                    n._isBeingDestroyed = !1
                }(this),
                function (n) {
                    n._events = Object.create(null);
                    n._hasHookEvent = !1;
                    var t = n.$options._parentListeners;
                    t && is(n, t)
                }(this),
                function (n) {
                    var r;
                    n._vnode = null;
                    n._staticTrees = null;
                    var i = n.$options,
                        t = n.$vnode = i._parentVnode,
                        u = t && t.context;
                    n.$slots = wu(i._renderChildren, u);
                    n.$scopedSlots = p;
                    n._c = function (t, i, r, u) {
                        return or(n, t, i, r, u, !1)
                    };
                    n.$createElement = function (t, i, r, u) {
                        return or(n, t, i, r, u, !0)
                    };
                    r = t && t.data;
                    yt(n, "$attrs", r && r.attrs || p, 0, !0);
                    yt(n, "$listeners", i._parentListeners || p, 0, !0)
                }(this);
            d(this, "beforeCreate"),
                function (n) {
                    var t = ss(n.$options.inject, n);
                    t && (rt.shouldConvert = !1, Object.keys(t).forEach(function (i) {
                        yt(n, i, t[i])
                    }), rt.shouldConvert = !0)
                }(this);
            ay(this),
                function (n) {
                    var t = n.$options.provide;
                    t && (n._provided = "function" == typeof t ? t.call(n) : t)
                }(this);
            d(this, "created");
            this.$options.el && this.$mount(this.$options.el)
        }
    }(r),
    function (n) {
        var i = {},
            t;
        i.get = function () {
            return this._data
        };
        t = {};
        t.get = function () {
            return this._props
        };
        Object.defineProperty(n.prototype, "$data", i);
        Object.defineProperty(n.prototype, "$props", t);
        n.prototype.$set = ou;
        n.prototype.$delete = ao;
        n.prototype.$watch = function (n, t, i) {
            if (v(t)) return du(this, n, t, i);
            (i = i || {}).user = !0;
            var r = new tt(this, n, t, i);
            return i.immediate && t.call(this, r.value),
                function () {
                    r.teardown()
                }
        }
    }(r),
    function (n) {
        var t = /^hook:/;
        n.prototype.$on = function (n, i) {
            if (Array.isArray(n))
                for (var r = 0, u = n.length; r < u; r++) this.$on(n[r], i);
            else(this._events[n] || (this._events[n] = [])).push(i), t.test(n) && (this._hasHookEvent = !0);
            return this
        };
        n.prototype.$once = function (n, t) {
            function r() {
                i.$off(n, r);
                t.apply(i, arguments)
            }
            var i = this;
            return r.fn = t, i.$on(n, r), i
        };
        n.prototype.$off = function (n, t) {
            var r, f, i, e, u;
            if (!arguments.length) return this._events = Object.create(null), this;
            if (Array.isArray(n)) {
                for (r = 0, f = n.length; r < f; r++) this.$off(n[r], t);
                return this
            }
            if (i = this._events[n], !i) return this;
            if (!t) return this._events[n] = null, this;
            if (t)
                for (u = i.length; u--;)
                    if ((e = i[u]) === t || e.fn === t) {
                        i.splice(u, 1);
                        break
                    } return this
        };
        n.prototype.$emit = function (n) {
            var i = this,
                t = i._events[n];
            if (t) {
                t = t.length > 1 ? fu(t) : t;
                for (var u = fu(arguments, 1), r = 0, f = t.length; r < f; r++) try {
                    t[r].apply(i, u)
                } catch (t) {
                    ct(t, i, 'event handler for "' + n + '"')
                }
            }
            return i
        }
    }(r),
    function (n) {
        n.prototype._update = function (n, t) {
            this._isMounted && d(this, "beforeUpdate");
            var i = this.$el,
                r = this._vnode,
                u = ni;
            ni = this;
            this._vnode = n;
            r ? this.$el = this.__patch__(r, n) : (this.$el = this.__patch__(this.$el, n, t, !1, this.$options._parentElm, this.$options._refElm), this.$options._parentElm = this.$options._refElm = null);
            ni = u;
            i && (i.__vue__ = null);
            this.$el && (this.$el.__vue__ = this);
            this.$vnode && this.$parent && this.$vnode === this.$parent._vnode && (this.$parent.$el = this.$el)
        };
        n.prototype.$forceUpdate = function () {
            this._watcher && this._watcher.update()
        };
        n.prototype.$destroy = function () {
            var n, t;
            if (!this._isBeingDestroyed) {
                for (d(this, "beforeDestroy"), this._isBeingDestroyed = !0, n = this.$parent, !n || n._isBeingDestroyed || this.$options.abstract || ht(n.$children, this), this._watcher && this._watcher.teardown(), t = this._watchers.length; t--;) this._watchers[t].teardown();
                this._data.__ob__ && this._data.__ob__.vmCount--;
                this._isDestroyed = !0;
                this.__patch__(this._vnode, null);
                d(this, "destroyed");
                this.$off();
                this.$el && (this.$el.__vue__ = null);
                this.$vnode && (this.$vnode.parent = null)
            }
        }
    }(r),
    function (n) {
        ls(n.prototype);
        n.prototype.$nextTick = function (n) {
            return au(n, this)
        };
        n.prototype._render = function () {
            var n = this,
                u = n.$options,
                e = u.render,
                r = u._parentVnode,
                f, i, t;
            if (n._isMounted)
                for (f in n.$slots) i = n.$slots[f], (i._rendered || i[0] && i[0].elm) && (n.$slots[f] = ur(i, !0));
            n.$scopedSlots = r && r.data.scopedSlots || p;
            n.$vnode = r;
            try {
                t = e.call(n._renderProxy, n.$createElement)
            } catch (u) {
                ct(u, n, "render");
                t = n._vnode
            }
            return t instanceof a || (t = gt()), t.parent = r, t
        }
    }(r);
    ve = [String, RegExp, Array];
    ta = {
        KeepAlive: {
            name: "keep-alive",
            abstract: !0,
            props: {
                include: ve,
                exclude: ve,
                max: [String, Number]
            },
            created: function () {
                this.cache = Object.create(null);
                this.keys = []
            },
            destroyed: function () {
                for (var n in this.cache) nf(this.cache, n, this.keys)
            },
            watch: {
                include: function (n) {
                    bs(this, function (t) {
                        return sr(n, t)
                    })
                },
                exclude: function (n) {
                    bs(this, function (t) {
                        return !sr(n, t)
                    })
                }
            },
            render: function () {
                var e = this.$slots.default,
                    n = ts(e),
                    r = n && n.componentOptions;
                if (r) {
                    var u = ws(r),
                        o = this.include,
                        s = this.exclude;
                    if (o && (!u || !sr(o, u)) || s && u && sr(s, u)) return n;
                    var f = this.cache,
                        t = this.keys,
                        i = null == n.key ? r.Ctor.cid + (r.tag ? "::" + r.tag : "") : n.key;
                    f[i] ? (n.componentInstance = f[i].componentInstance, ht(t, i), t.push(i)) : (f[i] = n, t.push(i), this.max && t.length > parseInt(this.max) && nf(f, t[0], t, this._vnode));
                    n.data.keepAlive = !0
                }
                return n || e && e[0]
            }
        }
    };
    ! function (n) {
        var t = {};
        t.get = function () {
            return w
        };
        Object.defineProperty(n, "config", t);
        n.util = {
            warn: tw,
            extend: i,
            mergeOptions: pt,
            defineReactive: yt
        };
        n.set = ou;
        n.delete = ao;
        n.nextTick = au;
        n.options = Object.create(null);
        lr.forEach(function (t) {
            n.options[t + "s"] = Object.create(null)
        });
        n.options._base = n;
        i(n.options.components, ta),
            function (n) {
                n.use = function (n) {
                    var i = this._installedPlugins || (this._installedPlugins = []),
                        t;
                    return i.indexOf(n) > -1 ? this : (t = fu(arguments, 1), t.unshift(this), "function" == typeof n.install ? n.install.apply(n, t) : "function" == typeof n && n.apply(null, t), i.push(n), this)
                }
            }(n),
            function (n) {
                n.mixin = function (n) {
                    return this.options = pt(this.options, n), this
                }
            }(n);
        np(n),
            function (n) {
                lr.forEach(function (t) {
                    n[t] = function (n, i) {
                        return i ? ("component" === t && v(i) && (i.name = i.name || n, i = this.options._base.extend(i)), "directive" === t && "function" == typeof i && (i = {
                            bind: i,
                            update: i
                        }), this.options[t + "s"][n] = i, i) : this.options[t + "s"][n]
                    }
                })
            }(n)
    }(r);
    Object.defineProperty(r.prototype, "$isServer", {
        get: di
    });
    Object.defineProperty(r.prototype, "$ssrContext", {
        get: function () {
            return this.$vnode && this.$vnode.ssrContext
        }
    });
    r.version = "2.5.13";
    var ye, ia, wr, at, br, pe, tr, kr, sw = e("style,class"),
        hw = e("input,textarea,option,select,progress"),
        ra = function (n, t, i) {
            return "value" === i && hw(n) && "button" !== t || "selected" === i && "option" === n || "checked" === i && "input" === n || "muted" === i && "video" === n
        },
        ua = e("contenteditable,draggable,spellcheck"),
        cw = e("allowfullscreen,async,autofocus,autoplay,checked,compact,controls,declare,default,defaultchecked,defaultmuted,defaultselected,defer,disabled,enabled,formnovalidate,hidden,indeterminate,inert,ismap,itemscope,loop,multiple,muted,nohref,noresize,noshade,novalidate,nowrap,open,pauseonexit,readonly,required,reversed,scoped,seamless,selected,sortable,translate,truespeed,typemustmatch,visible"),
        we = "http://www.w3.org/1999/xlink",
        be = function (n) {
            return ":" === n.charAt(5) && "xlink" === n.slice(0, 5)
        },
        fa = function (n) {
            return be(n) ? n.slice(6, n.length) : ""
        },
        dr = function (n) {
            return null == n || !1 === n
        },
        lw = {
            svg: "http://www.w3.org/2000/svg",
            math: "http://www.w3.org/1998/Math/MathML"
        },
        aw = e("html,body,base,head,link,meta,style,title,address,article,aside,footer,header,h1,h2,h3,h4,h5,h6,hgroup,nav,section,div,dd,dl,dt,figcaption,figure,picture,hr,img,li,main,ol,p,pre,ul,a,b,abbr,bdi,bdo,br,cite,code,data,dfn,em,i,kbd,mark,q,rp,rt,rtc,ruby,s,samp,small,span,strong,sub,sup,time,u,var,wbr,area,audio,map,track,video,embed,object,param,source,canvas,script,noscript,del,ins,caption,col,colgroup,table,thead,tbody,td,th,tr,button,datalist,fieldset,form,input,label,legend,meter,optgroup,option,output,progress,select,textarea,details,dialog,menu,menuitem,summary,content,element,shadow,template,blockquote,iframe,tfoot"),
        ea = e("svg,animate,circle,clippath,cursor,defs,desc,ellipse,filter,font-face,foreignObject,g,glyph,image,line,marker,mask,missing-glyph,path,pattern,polygon,polyline,rect,switch,symbol,text,textpath,tspan,use,view", !0),
        ke = function (n) {
            return aw(n) || ea(n)
        },
        gr = Object.create(null),
        de = e("text,number,password,search,email,tel,url"),
        vw = Object.freeze({
            createElement: function (n, t) {
                var i = document.createElement(n);
                return "select" !== n ? i : (t.data && t.data.attrs && void 0 !== t.data.attrs.multiple && i.setAttribute("multiple", "multiple"), i)
            },
            createElementNS: function (n, t) {
                return document.createElementNS(lw[n], t)
            },
            createTextNode: function (n) {
                return document.createTextNode(n)
            },
            createComment: function (n) {
                return document.createComment(n)
            },
            insertBefore: function (n, t, i) {
                n.insertBefore(t, i)
            },
            removeChild: function (n, t) {
                n.removeChild(t)
            },
            appendChild: function (n, t) {
                n.appendChild(t)
            },
            parentNode: function (n) {
                return n.parentNode
            },
            nextSibling: function (n) {
                return n.nextSibling
            },
            tagName: function (n) {
                return n.tagName
            },
            setTextContent: function (n, t) {
                n.textContent = t
            },
            setAttribute: function (n, t, i) {
                n.setAttribute(t, i)
            }
        }),
        yw = {
            create: function (n, t) {
                fi(t)
            },
            update: function (n, t) {
                n.data.ref !== t.data.ref && (fi(n, !0), fi(t))
            },
            destroy: function (n) {
                fi(n, !0)
            }
        },
        ti = new a("", {}, []),
        ir = ["create", "activate", "update", "remove", "destroy"],
        pw = {
            create: ff,
            update: ff,
            destroy: function (n) {
                ff(n, ti)
            }
        },
        ww = Object.create(null),
        bw = [yw, pw],
        kw = {
            create: nh,
            update: nh
        },
        dw = {
            create: ih,
            update: ih
        },
        gw = /[\w).+\-_$\]]/,
        nu = "__r",
        ge = "__c",
        nb = {
            create: sh,
            update: sh
        },
        tb = {
            create: hh,
            update: hh
        },
        oa = k(function (n) {
            var t = {},
                i = /:(.+)/;
            return n.split(/;(?![^(]*\))/g).forEach(function (n) {
                if (n) {
                    var r = n.split(i);
                    r.length > 1 && (t[r[0].trim()] = r[1].trim())
                }
            }), t
        }),
        ib = /^--/,
        sa = /\s*!important$/,
        ha = function (n, t, i) {
            var u, r, f;
            if (ib.test(t)) n.style.setProperty(t, i);
            else if (sa.test(i)) n.style.setProperty(t, i.replace(sa, ""), "important");
            else if (u = rb(t), Array.isArray(i))
                for (r = 0, f = i.length; r < f; r++) n.style[u] = i[r];
            else n.style[u] = i
        },
        ca = ["Webkit", "Moz", "ms"],
        rb = k(function (n) {
            var r, t, i;
            if (kr = kr || document.createElement("div").style, "filter" !== (n = it(n)) && n in kr) return n;
            for (r = n.charAt(0).toUpperCase() + n.slice(1), t = 0; t < ca.length; t++)
                if (i = ca[t] + r, i in kr) return i
        }),
        ub = {
            create: lh,
            update: lh
        },
        la = k(function (n) {
            return {
                enterClass: n + "-enter",
                enterToClass: n + "-enter-to",
                enterActiveClass: n + "-enter-active",
                leaveClass: n + "-leave",
                leaveToClass: n + "-leave-to",
                leaveActiveClass: n + "-leave-active"
            }
        }),
        aa = l && !ci,
        ai = "transition",
        no = "animation",
        tu = "transition",
        iu = "transitionend",
        to = "animation",
        va = "animationend";
    aa && (void 0 === window.ontransitionend && void 0 !== window.onwebkittransitionend && (tu = "WebkitTransition", iu = "webkitTransitionEnd"), void 0 === window.onanimationend && void 0 !== window.onwebkitanimationend && (to = "WebkitAnimation", va = "webkitAnimationEnd"));
    var ya = l ? window.requestAnimationFrame ? window.requestAnimationFrame.bind(window) : setTimeout : function (n) {
            return n()
        },
        fb = /\b(transform|all)(,|$)/,
        eb = function (i) {
            function y(t) {
                var i = r.parentNode(t);
                n(i) && r.removeChild(i, t)
            }

            function s(t, i, e, o, s) {
                if (t.isRootInsert = !s, ! function (t, i, r, e) {
                        var o = t.data,
                            s;
                        if (n(o) && (s = n(t.componentInstance) && o.keepAlive, n(o = o.hook) && n(o = o.init) && o(t, !1, r, e), n(t.componentInstance))) return g(t, i), u(s) && function (t, i, r, u) {
                            for (var e, o = t; o.componentInstance;)
                                if (o = o.componentInstance._vnode, n(e = o.data) && n(e = e.transition)) {
                                    for (e = 0; e < f.activate.length; ++e) f.activate[e](ti, o);
                                    i.push(o);
                                    break
                                } l(r, t.elm, u)
                        }(t, i, r, e), !0
                    }(t, i, e, o)) {
                    var c = t.data,
                        a = t.children,
                        h = t.tag;
                    n(h) ? (t.elm = t.ns ? r.createElementNS(t.ns, h) : r.createElement(h, t), tt(t), nt(t, a, i), n(c) && w(t, i), l(e, t.elm, o)) : u(t.isComment) ? (t.elm = r.createComment(t.text), l(e, t.elm, o)) : (t.elm = r.createTextNode(t.text), l(e, t.elm, o))
                }
            }

            function g(t, i) {
                n(t.data.pendingInsert) && (i.push.apply(i, t.data.pendingInsert), t.data.pendingInsert = null);
                t.elm = t.componentInstance.$el;
                p(t) ? (w(t, i), tt(t)) : (fi(t), i.push(t))
            }

            function l(t, i, u) {
                n(t) && (n(u) ? u.parentNode === t && r.insertBefore(t, i, u) : r.appendChild(t, i))
            }

            function nt(n, t, i) {
                if (Array.isArray(t))
                    for (var u = 0; u < t.length; ++u) s(t[u], i, n.elm, null, !0);
                else vi(n.text) && r.appendChild(n.elm, r.createTextNode(String(n.text)))
            }

            function p(t) {
                for (; t.componentInstance;) t = t.componentInstance._vnode;
                return n(t.tag)
            }

            function w(t, i) {
                for (var r = 0; r < f.create.length; ++r) f.create[r](ti, t);
                n(o = t.data.hook) && (n(o.create) && o.create(ti, t), n(o.insert) && i.push(t))
            }

            function tt(t) {
                var i, u;
                if (n(i = t.fnScopeId)) r.setAttribute(t.elm, i, "");
                else
                    for (u = t; u;) n(i = u.context) && n(i = i.$options._scopeId) && r.setAttribute(t.elm, i, ""), u = u.parent;
                n(i = ni) && i !== t.context && i !== t.fnContext && n(i = i.$options._scopeId) && r.setAttribute(t.elm, i, "")
            }

            function it(n, t, i, r, u, f) {
                for (; r <= u; ++r) s(i[r], f, n, t)
            }

            function v(t) {
                var i, r, u = t.data;
                if (n(u))
                    for (n(i = u.hook) && n(i = i.destroy) && i(t), i = 0; i < f.destroy.length; ++i) f.destroy[i](t);
                if (n(i = t.children))
                    for (r = 0; r < t.children.length; ++r) v(t.children[r])
            }

            function b(t, i, r, u) {
                for (; r <= u; ++r) {
                    var f = i[r];
                    n(f) && (n(f.tag) ? (rt(f), v(f)) : y(f.elm))
                }
            }

            function rt(t, i) {
                if (n(i) || n(t.data)) {
                    var r, u = f.remove.length + 1;
                    for (n(i) ? i.listeners += u : i = function (n, t) {
                            function i() {
                                0 == --i.listeners && y(n)
                            }
                            return i.listeners = t, i
                        }(t.elm, u), n(r = t.componentInstance) && n(r = r._vnode) && n(r.data) && rt(r, i), r = 0; r < f.remove.length; ++r) f.remove[r](t, i);
                    n(r = t.data.hook) && n(r = r.remove) ? r(t, i) : i()
                } else y(t.elm)
            }

            function et(i, u, f, e, o) {
                for (var d, g, nt, y = 0, w = 0, v = u.length - 1, l = u[0], a = u[v], p = f.length - 1, c = f[0], k = f[p], tt = !o; y <= v && w <= p;) t(l) ? l = u[++y] : t(a) ? a = u[--v] : wt(l, c) ? (h(l, c, e), l = u[++y], c = f[++w]) : wt(a, k) ? (h(a, k, e), a = u[--v], k = f[--p]) : wt(l, k) ? (h(l, k, e), tt && r.insertBefore(i, l.elm, r.nextSibling(a.elm)), l = u[++y], k = f[--p]) : wt(a, c) ? (h(a, c, e), tt && r.insertBefore(i, a.elm, l.elm), a = u[--v], c = f[++w]) : (t(d) && (d = ip(u, y, v)), t(g = n(c.key) ? d[c.key] : function (t, i, r, u) {
                    for (var e, f = r; f < u; f++)
                        if (e = i[f], n(e) && wt(t, e)) return f
                }(c, u, y, v)) ? s(c, e, i, l.elm) : wt(nt = u[g], c) ? (h(nt, c, e), u[g] = void 0, tt && r.insertBefore(i, nt.elm, l.elm)) : s(c, e, i, l.elm), c = f[++w]);
                y > v ? it(i, t(f[p + 1]) ? null : f[p + 1].elm, f, w, p, e) : w > p && b(0, u, y, v)
            }

            function h(i, e, o, s) {
                var v, h, c, l, a;
                if (i !== e)
                    if (v = e.elm = i.elm, u(i.isAsyncPlaceholder)) n(e.asyncFactory.resolved) ? k(i.elm, e, o) : e.isAsyncPlaceholder = !0;
                    else if (u(e.isStatic) && u(i.isStatic) && e.key === i.key && (u(e.isCloned) || u(e.isOnce))) e.componentInstance = i.componentInstance;
                else {
                    if (c = e.data, n(c) && n(h = c.hook) && n(h = h.prepatch) && h(i, e), l = i.children, a = e.children, n(c) && p(e)) {
                        for (h = 0; h < f.update.length; ++h) f.update[h](i, e);
                        n(h = c.hook) && n(h = h.update) && h(i, e)
                    }
                    t(e.text) ? n(l) && n(a) ? l !== a && et(v, l, a, o, s) : n(a) ? (n(i.text) && r.setTextContent(v, ""), it(v, null, a, 0, a.length - 1, o)) : n(l) ? b(0, l, 0, l.length - 1) : n(i.text) && r.setTextContent(v, "") : i.text !== e.text && r.setTextContent(v, e.text);
                    n(c) && n(h = c.hook) && n(h = h.postpatch) && h(i, e)
                }
            }

            function ut(t, i, r) {
                if (u(r) && n(t.parent)) t.parent.data.pendingInsert = i;
                else
                    for (var f = 0; f < i.length; ++f) i[f].data.hook.insert(i[f])
            }

            function k(t, i, r, f) {
                var e, y = i.tag,
                    o = i.data,
                    h = i.children,
                    l, v;
                if (f = f || o && o.pre, i.elm = t, u(i.isComment) && n(i.asyncFactory)) return i.isAsyncPlaceholder = !0, !0;
                if (n(o) && (n(e = o.hook) && n(e = e.init) && e(i, !0), n(e = i.componentInstance))) return g(i, r), !0;
                if (n(y)) {
                    if (n(h))
                        if (t.hasChildNodes())
                            if (n(e = o) && n(e = e.domProps) && n(e = e.innerHTML)) {
                                if (e !== t.innerHTML) return !1
                            } else {
                                for (var a = !0, s = t.firstChild, c = 0; c < h.length; c++) {
                                    if (!s || !k(s, h[c], r, f)) {
                                        a = !1;
                                        break
                                    }
                                    s = s.nextSibling
                                }
                                if (!a || s) return !1
                            }
                    else nt(i, h, r);
                    if (n(o)) {
                        l = !1;
                        for (v in o)
                            if (!ft(v)) {
                                l = !0;
                                w(i, r);
                                break
                            }! l && o.class && bo(o.class)
                    }
                } else t.data !== i.text && (t.data = i.text);
                return !0
            }
            for (var c, f = {}, d = i.modules, r = i.nodeOps, ft, o = 0; o < ir.length; ++o)
                for (f[ir[o]] = [], c = 0; c < d.length; ++c) n(d[c][ir[o]]) && f[ir[o]].push(d[c][ir[o]]);
            return ft = e("attrs,class,staticClass,staticStyle,key"),
                function (i, e, o, c, l, y) {
                    var ft, d, et, g, ot, w, st, nt, tt, it, rt;
                    if (!t(e)) {
                        if (ft = !1, d = [], t(i)) ft = !0, s(e, d, l, y);
                        else if (et = n(i.nodeType), !et && wt(i, e)) h(i, e, d, c);
                        else {
                            if (et) {
                                if (1 === i.nodeType && i.hasAttribute(fl) && (i.removeAttribute(fl), o = !0), u(o) && k(i, e, d)) return ut(e, d, !0), i;
                                i = function (n) {
                                    return new a(r.tagName(n).toLowerCase(), {}, [], void 0, n)
                                }(i)
                            }
                            if (g = i.elm, ot = r.parentNode(g), s(e, d, g._leaveCb ? null : ot, r.nextSibling(g)), n(e.parent))
                                for (w = e.parent, st = p(e); w;) {
                                    for (nt = 0; nt < f.destroy.length; ++nt) f.destroy[nt](w);
                                    if (w.elm = e.elm, st) {
                                        for (tt = 0; tt < f.create.length; ++tt) f.create[tt](ti, w);
                                        if (it = w.data.hook.insert, it.merged)
                                            for (rt = 1; rt < it.fns.length; rt++) it.fns[rt]()
                                    } else fi(w);
                                    w = w.parent
                                }
                            n(ot) ? b(0, [i], 0, 0) : n(i.tag) && v(i)
                        }
                        return ut(e, d, ft), e.elm
                    }
                    n(i) && v(i)
                }
        }({
            nodeOps: vw,
            modules: [kw, dw, nb, tb, ub, l ? {
                create: tc,
                activate: tc,
                remove: function (n, t) {
                    !0 !== n.data.show ? gh(n, t) : t()
                }
            } : {}].concat(bw)
        });
    ci && document.addEventListener("selectionchange", function () {
        var n = document.activeElement;
        n && n.vmodel && yf(n, "input")
    });
    var pa = {
            inserted: function (n, t, i, r) {
                "select" === i.tag ? (r.elm && !r.elm._vOptions ? lt(i, "postpatch", function () {
                    pa.componentUpdated(n, t, i)
                }) : ic(n, t, i.context), n._vOptions = [].map.call(n.options, hr)) : ("textarea" === i.tag || de(n.type)) && (n._vModifiers = t.modifiers, t.modifiers.lazy || (n.addEventListener("change", fc), gp || (n.addEventListener("compositionstart", fp), n.addEventListener("compositionend", fc)), ci && (n.vmodel = !0)))
            },
            componentUpdated: function (n, t, i) {
                if ("select" === i.tag) {
                    ic(n, t, i.context);
                    var u = n._vOptions,
                        r = n._vOptions = [].map.call(n.options, hr);
                    r.some(function (n, t) {
                        return !vt(n, u[t])
                    }) && (n.multiple ? t.value.some(function (n) {
                        return uc(n, r)
                    }) : t.value !== t.oldValue && uc(t.value, r)) && yf(n, "change")
                }
            }
        },
        ob = {
            model: pa,
            show: {
                bind: function (n, t, i) {
                    var r = t.value,
                        f = (i = pf(i)).data && i.data.transition,
                        u = n.__vOriginalDisplay = "none" === n.style.display ? "" : n.style.display;
                    r && f ? (i.data.show = !0, af(i, function () {
                        n.style.display = u
                    })) : n.style.display = r ? u : "none"
                },
                update: function (n, t, i) {
                    var r = t.value;
                    r !== t.oldValue && ((i = pf(i)).data && i.data.transition ? (i.data.show = !0, r ? af(i, function () {
                        n.style.display = n.__vOriginalDisplay
                    }) : gh(i, function () {
                        n.style.display = "none"
                    })) : n.style.display = r ? n.__vOriginalDisplay : "none")
                },
                unbind: function (n, t, i, r, u) {
                    u || (n.style.display = n.__vOriginalDisplay)
                }
            }
        },
        wa = {
            name: String,
            appear: Boolean,
            css: Boolean,
            mode: String,
            type: String,
            enterClass: String,
            leaveClass: String,
            enterToClass: String,
            leaveToClass: String,
            enterActiveClass: String,
            leaveActiveClass: String,
            appearClass: String,
            appearActiveClass: String,
            appearToClass: String,
            duration: [Number, String, Object]
        },
        sb = {
            name: "transition",
            props: wa,
            abstract: !0,
            render: function (n) {
                var l = this,
                    e = this.$slots.default,
                    o, u, t, f, h, v, c;
                if (e && (e = e.filter(function (n) {
                        return n.tag || er(n)
                    })).length) {
                    if ((o = this.mode, u = e[0], function (n) {
                            for (; n = n.parent;)
                                if (n.data.transition) return !0
                        }(this.$vnode)) || (t = wf(u), !t)) return u;
                    if (this._leaving) return oc(n, u);
                    f = "__transition-" + this._uid + "-";
                    t.key = null == t.key ? t.isComment ? f + "comment" : f + t.tag : vi(t.key) ? 0 === String(t.key).indexOf(f) ? t.key : f + t.key : t.key;
                    var s = (t.data || (t.data = {})).transition = ec(this),
                        a = this._vnode,
                        r = wf(a);
                    if (t.data.directives && t.data.directives.some(function (n) {
                            return "show" === n.name
                        }) && (t.data.show = !0), r && r.data && ! function (n, t) {
                            return t.key === n.key && t.tag === n.tag
                        }(t, r) && !er(r) && (!r.componentInstance || !r.componentInstance._vnode.isComment)) {
                        if (h = r.data.transition = i({}, s), "out-in" === o) return this._leaving = !0, lt(h, "afterLeave", function () {
                            l._leaving = !1;
                            l.$forceUpdate()
                        }), oc(n, u);
                        if ("in-out" === o) {
                            if (er(t)) return a;
                            c = function () {
                                v()
                            };
                            lt(s, "afterEnter", c);
                            lt(s, "enterCancelled", c);
                            lt(h, "delayLeave", function (n) {
                                v = n
                            })
                        }
                    }
                    return u
                }
            }
        },
        ba = i({
            tag: String,
            moveClass: String
        }, wa);
    delete ba.mode;
    ka = {
        Transition: sb,
        TransitionGroup: {
            props: ba,
            render: function (n) {
                for (var t, i, e = this.tag || this.$vnode.data.tag || "span", o = Object.create(null), r = this.prevChildren = this.children, s = this.$slots.default || [], h = this.children = [], c = ec(this), u = 0; u < s.length; u++) t = s[u], t.tag && null != t.key && 0 !== String(t.key).indexOf("__vlist") && (h.push(t), o[t.key] = t, (t.data || (t.data = {})).transition = c);
                if (r) {
                    for (var l = [], a = [], f = 0; f < r.length; f++) i = r[f], i.data.transition = c, i.data.pos = i.elm.getBoundingClientRect(), o[i.key] ? l.push(i) : a.push(i);
                    this.kept = n(e, null, l);
                    this.removed = a
                }
                return n(e, null, h)
            },
            beforeUpdate: function () {
                this.__patch__(this._vnode, this.kept, !1, !0);
                this._vnode = this.kept
            },
            updated: function () {
                var n = this.prevChildren,
                    t = this.moveClass || (this.name || "v") + "-move";
                n.length && this.hasMove(n[0].elm, t) && (n.forEach(ep), n.forEach(op), n.forEach(sp), this._reflow = document.body.offsetHeight, n.forEach(function (n) {
                    if (n.data.moved) {
                        var i = n.elm,
                            r = i.style;
                        dt(i, t);
                        r.transform = r.WebkitTransform = r.transitionDuration = "";
                        i.addEventListener(iu, i._moveCb = function n(r) {
                            r && !/transform$/.test(r.propertyName) || (i.removeEventListener(iu, n), i._moveCb = null, ut(i, t))
                        })
                    }
                }))
            },
            methods: {
                hasMove: function (n, t) {
                    var i, r;
                    return aa ? this._hasMove ? this._hasMove : (i = n.cloneNode(), n._transitionClasses && n._transitionClasses.forEach(function (n) {
                        vh(i, n)
                    }), ah(i, t), i.style.display = "none", this.$el.appendChild(i), r = bh(i), this.$el.removeChild(i), this._hasMove = r.hasTransform) : !1
                }
            }
        }
    };
    r.config.mustUseProp = ra;
    r.config.isReservedTag = ke;
    r.config.isReservedAttr = sw;
    r.config.getTagNamespace = ds;
    r.config.isUnknownElement = function (n) {
        if (!l) return !0;
        if (ke(n)) return !1;
        if (n = n.toLowerCase(), null != gr[n]) return gr[n];
        var t = document.createElement(n);
        return gr[n] = n.indexOf("-") > -1 ? t.constructor === window.HTMLUnknownElement || t.constructor === window.HTMLElement : /HTMLUnknownElement/.test(t.toString())
    };
    i(r.options.directives, ob);
    i(r.options.components, ka);
    r.prototype.__patch__ = l ? eb : o;
    r.prototype.$mount = function (n, t) {
        return n = n && l ? uf(n) : void 0,
            function (n, t, i) {
                n.$el = t;
                n.$options.render || (n.$options.render = gt);
                d(n, "beforeMount");
                var r;
                return r = function () {
                    n._update(n._render(), i)
                }, new tt(n, r, o, null, !0), i = !1, null == n.$vnode && (n._isMounted = !0, d(n, "mounted")), n
            }(this, n, t)
    };
    r.nextTick(function () {
        w.devtools && vr && vr.emit("init", r)
    }, 0);
    var ru, hb = /\{\{((?:.|\n)+?)\}\}/g,
        da = /[-.*+?^${}()|[\]\/\\]/g,
        cb = k(function (n) {
            var t = n[0].replace(da, "\\$&"),
                i = n[1].replace(da, "\\$&");
            return new RegExp(t + "((?:.|\\n)+?)" + i, "g")
        }),
        lb = {
            staticKeys: ["staticClass"],
            transformNode: function (n, t) {
                var i, r;
                t.warn;
                i = f(n, "class");
                i && (n.staticClass = JSON.stringify(i));
                r = y(n, "class", !1);
                r && (n.classBinding = r)
            },
            genData: function (n) {
                var t = "";
                return n.staticClass && (t += "staticClass:" + n.staticClass + ","), n.classBinding && (t += "class:" + n.classBinding + ","), t
            }
        },
        ab = {
            staticKeys: ["staticStyle"],
            transformNode: function (n, t) {
                var i, r;
                t.warn;
                i = f(n, "style");
                i && (n.staticStyle = JSON.stringify(oa(i)));
                r = y(n, "style", !1);
                r && (n.styleBinding = r)
            },
            genData: function (n) {
                var t = "";
                return n.staticStyle && (t += "staticStyle:" + n.staticStyle + ","), n.styleBinding && (t += "style:(" + n.styleBinding + "),"), t
            }
        },
        vb = function (n) {
            return ru = ru || document.createElement("div"), ru.innerHTML = n, ru.textContent
        },
        yb = e("area,base,br,col,embed,frame,hr,img,input,isindex,keygen,link,meta,param,source,track,wbr"),
        pb = e("colgroup,dd,dt,li,options,p,td,tfoot,th,thead,tr,source"),
        wb = e("address,article,aside,base,blockquote,body,caption,col,colgroup,dd,details,dialog,div,dl,dt,fieldset,figcaption,figure,footer,form,h1,h2,h3,h4,h5,h6,head,header,hgroup,hr,html,legend,li,menuitem,meta,optgroup,option,param,rp,rt,source,style,summary,tbody,td,tfoot,th,thead,title,tr,track"),
        bb = /^\s*([^\s"'<>\/=]+)(?:\s*(=)\s*(?:"([^"]*)"+|'([^']*)'+|([^\s"'=<>`]+)))?/,
        ga = "[a-zA-Z_][\\w\\-\\.]*",
        nv = "((?:" + ga + "\\:)?" + ga + ")",
        tv = new RegExp("^<" + nv),
        kb = /^\s*(\/?)>/,
        iv = new RegExp("^<\\/" + nv + "[^>]*>"),
        db = /^<!DOCTYPE [^>]+>/i,
        rv = /^<!--/,
        uv = /^<!\[/,
        fv = !1;
    "x".replace(/x(.)?/g, function (n, t) {
        fv = "" === t
    });
    var ev, ov, io, ro, uo, fo, eo, sv, hv, oo, uu, cv = e("script,style,textarea", !0),
        lv = {},
        gb = {
            "&lt;": "<",
            "&gt;": ">",
            "&quot;": '"',
            "&amp;": "&",
            "&#10;": "\n",
            "&#9;": "\t"
        },
        nk = /&(?:lt|gt|quot|amp);/g,
        tk = /&(?:lt|gt|quot|amp|#10|#9);/g,
        ik = e("pre,textarea", !0),
        av = function (n, t) {
            return n && ik(n) && "\n" === t[0]
        },
        vv = /^@|^v-on:/,
        yv = /^v-|^@|^:/,
        rk = /(.*?)\s+(?:in|of)\s+(.*)/,
        pv = /,([^,\}\]]*)(?:,([^,\}\]]*))?$/,
        uk = /^\(|\)$/g,
        fk = /:(.*)$/,
        wv = /^:|^v-bind:/,
        bv = /\.[^.]+/g,
        ek = k(vb),
        ok = /^xmlns:NS\d+/,
        sk = /^NS\d+:/,
        kv = [lb, ab, {
            preTransformNode: function (n, t) {
                var e, r, u;
                if ("input" === n.tag && (e = n.attrsMap, e["v-model"] && (e["v-bind:type"] || e[":type"]))) {
                    var o = y(n, "type"),
                        s = f(n, "v-if", !0),
                        h = s ? "&&(" + s + ")" : "",
                        l = null != f(n, "v-else", !0),
                        c = f(n, "v-else-if", !0),
                        i = bf(n);
                    return hc(i), sf(i, "type", "checkbox"), cr(i, t), i.processed = !0, i.if = "(" + o + ")==='checkbox'" + h, oi(i, {
                        exp: i.if,
                        block: i
                    }), r = bf(n), f(r, "v-for", !0), sf(r, "type", "radio"), cr(r, t), oi(i, {
                        exp: "(" + o + ")==='radio'" + h,
                        block: r
                    }), u = bf(n), f(u, "v-for", !0), sf(u, ":type", o), cr(u, t), oi(i, {
                        exp: s,
                        block: u
                    }), l ? i.else = !0 : c && (i.elseif = c), i
                }
            }
        }],
        hk = {
            expectHTML: !0,
            modules: kv,
            directives: {
                model: function (n, t) {
                    var i = t.value,
                        r = t.modifiers,
                        u = n.tag,
                        f = n.attrsMap.type;
                    if (n.component) return uh(n, i, r), !1;
                    if ("select" === u) ! function (n, t, i) {
                        var r = 'var $$selectedVal = Array.prototype.filter.call($event.target.options,function(o){return o.selected}).map(function(o){var val = "_value" in o ? o._value : o.value;return ' + (i && i.number ? "_n(val)" : "val") + "});";
                        r = r + " " + ei(t, "$event.target.multiple ? $$selectedVal : $$selectedVal[0]");
                        kt(n, "change", r, null, !0)
                    }(n, i, r);
                    else if ("input" === u && "checkbox" === f) ! function (n, t, i) {
                        var f = i && i.number,
                            r = y(n, "value") || "null",
                            u = y(n, "true-value") || "true",
                            e = y(n, "false-value") || "false";
                        bt(n, "checked", "Array.isArray(" + t + ")?_i(" + t + "," + r + ")>-1" + ("true" === u ? ":(" + t + ")" : ":_q(" + t + "," + u + ")"));
                        kt(n, "change", "var $$a=" + t + ",$$el=$event.target,$$c=$$el.checked?(" + u + "):(" + e + ");if(Array.isArray($$a)){var $$v=" + (f ? "_n(" + r + ")" : r) + ",$$i=_i($$a,$$v);if($$el.checked){$$i<0&&(" + t + "=$$a.concat([$$v]))}else{$$i>-1&&(" + t + "=$$a.slice(0,$$i).concat($$a.slice($$i+1)))}}else{" + ei(t, "$$c") + "}", null, !0)
                    }(n, i, r);
                    else if ("input" === u && "radio" === f) ! function (n, t, i) {
                        var u = i && i.number,
                            r = y(n, "value") || "null";
                        bt(n, "checked", "_q(" + t + "," + (r = u ? "_n(" + r + ")" : r) + ")");
                        kt(n, "change", ei(t, r), null, !0)
                    }(n, i, r);
                    else if ("input" === u || "textarea" === u) ! function (n, t, i) {
                        var e = n.attrsMap.type,
                            f = i || {},
                            o = f.lazy,
                            s = f.number,
                            h = f.trim,
                            c = !o && "range" !== e,
                            l = o ? "change" : "range" === e ? nu : "input",
                            r = "$event.target.value",
                            u;
                        h && (r = "$event.target.value.trim()");
                        s && (r = "_n(" + r + ")");
                        u = ei(t, r);
                        c && (u = "if($event.target.composing)return;" + u);
                        bt(n, "value", "(" + t + ")");
                        kt(n, l, u, null, !0);
                        (h || s) && kt(n, "blur", "$forceUpdate()")
                    }(n, i, r);
                    else if (!w.isReservedTag(u)) return uh(n, i, r), !1;
                    return !0
                },
                text: function (n, t) {
                    t.value && bt(n, "textContent", "_s(" + t.value + ")")
                },
                html: function (n, t) {
                    t.value && bt(n, "innerHTML", "_s(" + t.value + ")")
                }
            },
            isPreTag: function (n) {
                return "pre" === n
            },
            isUnaryTag: yb,
            mustUseProp: ra,
            canBeLeftOpenTag: pb,
            isReservedTag: ke,
            getTagNamespace: ds,
            staticKeys: function (n) {
                return n.reduce(function (n, t) {
                    return n.concat(t.staticKeys || [])
                }, []).join(",")
            }(kv)
        },
        ck = k(function (n) {
            return e("type,tag,attrsList,attrsMap,plain,parent,children,attrs" + (n ? "," + n : ""))
        }),
        lk = /^\s*([\w$_]+|\([^)]*?\))\s*=>|^function\s*\(/,
        ak = /^\s*[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*|\['.*?']|\[".*?"]|\[\d+]|\[[A-Za-z_$][\w$]*])*\s*$/,
        dv = {
            esc: 27,
            tab: 9,
            enter: 13,
            space: 32,
            up: 38,
            left: 37,
            right: 39,
            down: 40,
            "delete": [8, 46]
        },
        st = function (n) {
            return "if(" + n + ")return null;"
        },
        gv = {
            stop: "$event.stopPropagation();",
            prevent: "$event.preventDefault();",
            self: st("$event.target !== $event.currentTarget"),
            ctrl: st("!$event.ctrlKey"),
            shift: st("!$event.shiftKey"),
            alt: st("!$event.altKey"),
            meta: st("!$event.metaKey"),
            left: st("'button' in $event && $event.button !== 0"),
            middle: st("'button' in $event && $event.button !== 1"),
            right: st("'button' in $event && $event.button !== 2")
        },
        vk = {
            on: function (n, t) {
                n.wrapListeners = function (n) {
                    return "_g(" + n + "," + t.value + ")"
                }
            },
            bind: function (n, t) {
                n.wrapData = function (i) {
                    return "_b(" + i + ",'" + n.tag + "'," + t.value + "," + (t.modifiers && t.modifiers.prop ? "true" : "false") + (t.modifiers && t.modifiers.sync ? ",true" : "") + ")"
                }
            },
            cloak: o
        },
        yk = function (n) {
            this.options = n;
            this.warn = n.warn || rh;
            this.transforms = ki(n.modules, "transformCode");
            this.dataGenFns = ki(n.modules, "genData");
            this.directives = i(i({}, vk), n.directives);
            var t = n.isReservedTag || g;
            this.maybeComponent = function (n) {
                return !t(n.tag)
            };
            this.onceId = 0;
            this.staticRenderFns = []
        },
        ny = (new RegExp("\\b" + "do,if,for,let,new,try,var,case,else,with,await,break,catch,class,const,super,throw,while,yield,delete,export,import,return,switch,default,extends,finally,continue,debugger,function,arguments".split(",").join("\\b|\\b") + "\\b"), new RegExp("\\b" + "delete,typeof,void".split(",").join("\\s*\\([^\\)]*\\)|\\b") + "\\s*\\([^\\)]*\\)"), function (n) {
            return function (t) {
                function r(r, u) {
                    var f = Object.create(t),
                        s = [],
                        h = [],
                        e, o;
                    if (f.warn = function (n, t) {
                            (t ? h : s).push(n)
                        }, u) {
                        u.modules && (f.modules = (t.modules || []).concat(u.modules));
                        u.directives && (f.directives = i(Object.create(t.directives || null), u.directives));
                        for (e in u) "modules" !== e && "directives" !== e && (f[e] = u[e])
                    }
                    return o = n(r, f), o.errors = s, o.tips = h, o
                }
                return {
                    compile: r,
                    compileToFunctions: function (n) {
                        var t = Object.create(null);
                        return function (r, u) {
                            var f;
                            if ((u = i({}, u)).warn, delete u.warn, f = u.delimiters ? String(u.delimiters) + r : r, t[f]) return t[f];
                            var o = n(r, u),
                                e = {},
                                s = [];
                            return e.render = tl(o.render, s), e.staticRenderFns = o.staticRenderFns.map(function (n) {
                                return tl(n, s)
                            }), t[f] = e
                        }
                    }(r)
                }
            }
        }(function (n, t) {
            var i = cp(n.trim(), t),
                r;
            return !1 !== t.optimize && function (n, t) {
                n && (hv = ck(t.staticKeys || ""), oo = t.isReservedTag || g, kf(n), df(n, !1))
            }(i, t), r = ac(i, t), {
                ast: i,
                render: r.render,
                staticRenderFns: r.staticRenderFns
            }
        })(hk).compileToFunctions),
        pk = !!l && il(!1),
        wk = !!l && il(!0),
        bk = k(function (n) {
            var t = uf(n);
            return t && t.innerHTML
        }),
        kk = r.prototype.$mount;
    return r.prototype.$mount = function (n, t) {
        var r, i;
        if ((n = n && uf(n)) === document.body || n === document.documentElement) return this;
        if (r = this.$options, !r.render) {
            if (i = r.template, i)
                if ("string" == typeof i) "#" === i.charAt(0) && (i = bk(i));
                else {
                    if (!i.nodeType) return this;
                    i = i.innerHTML
                }
            else n && (i = function (n) {
                if (n.outerHTML) return n.outerHTML;
                var t = document.createElement("div");
                return t.appendChild(n.cloneNode(!0)), t.innerHTML
            }(n));
            if (i) {
                var u = ny(i, {
                        shouldDecodeNewlines: pk,
                        shouldDecodeNewlinesForHref: wk,
                        delimiters: r.delimiters,
                        comments: r.comments
                    }, this),
                    f = u.render,
                    e = u.staticRenderFns;
                r.render = f;
                r.staticRenderFns = e
            }
        }
        return kk.call(this, n, t)
    }, r.compile = ny, r
}),
function (n, t) {
    typeof exports == "object" && typeof module == "object" ? module.exports = t() : typeof define == "function" && define.amd ? define([], t) : typeof exports == "object" ? exports.VueQr = t() : n.VueQr = t()
}(this, function () {
    return function (n) {
        function t(r) {
            if (i[r]) return i[r].exports;
            var u = i[r] = {
                exports: {},
                id: r,
                loaded: !1
            };
            return n[r].call(u.exports, u, u.exports, t), u.loaded = !0, u.exports
        }
        var i = {};
        return t.m = n, t.c = i, t.p = "", t(0)
    }([function (n, t, i) {
        "use strict";

        function f(n) {
            return n && n.__esModule ? n : {
                "default": n
            }
        }
        var r = i(1),
            u = f(r);
        n.exports = u.default
    }, function (n, t, i) {
        var u, r;
        u = i(2);
        r = i(13);
        n.exports = u || {};
        n.exports.__esModule && (n.exports = n.exports.default);
        r && ((typeof n.exports == "function" ? n.exports.options : n.exports).template = r);
        !1 && function () {
            var t, i;
            (n.hot.accept(), t = require("vue-hot-reload-api"), t.install(require("vue"), !0), t.compatible) && (i = "/home/vixi_n/Documents/Github/vue-qrcode/src/Qrcode.vue", n.hot.data ? t.update(i, n.exports, r) : t.createRecord(i, n.exports))
        }()
    }, function (n, t, i) {
        "use strict";

        function e(n) {
            return n && n.__esModule ? n : {
                "default": n
            }
        }

        function o(n) {
            return n.webkitBackingStorePixelRatio || n.mozBackingStorePixelRatio || n.msBackingStorePixelRatio || n.oBackingStorePixelRatio || n.backingStorePixelRatio || 1
        }
        var u, f, r;
        Object.defineProperty(t, "__esModule", {
            value: !0
        });
        u = i(3);
        f = e(u);
        r = function () {
            this.update()
        };
        t.default = {
            props: {
                val: {
                    type: String,
                    required: !0
                },
                size: {
                    type: Number,
                    "default": 100
                },
                level: String,
                bgColor: {
                    type: String,
                    "default": "#FFFFFF"
                },
                fgColor: {
                    type: String,
                    "default": "#000000"
                }
            },
            beforeUpdate: r,
            mounted: r,
            methods: {
                update: function () {
                    var t = this.size,
                        h = this.bgColor,
                        c = this.fgColor,
                        i = this.$refs.qr,
                        l = f.default(this.val),
                        n = i.getContext("2d"),
                        r = l.modules,
                        u = t / r.length,
                        e = t / r.length,
                        s = (window.devicePixelRatio || 1) / o(n);
                    i.height = i.width = t * s;
                    n.scale(s, s);
                    r.forEach(function (t, i) {
                        t.forEach(function (t, r) {
                            n.fillStyle = t ? c : h;
                            var f = Math.ceil((r + 1) * u) - Math.floor(r * u),
                                o = Math.ceil((i + 1) * e) - Math.floor(i * e);
                            n.fillRect(Math.round(r * u), Math.round(i * e), f, o)
                        })
                    })
                }
            }
        }
    }, function (n, t, i) {
        var f = i(4),
            r = i(8),
            u = function (n, t) {
                t = t || {};
                var i = new f(t.typeNumber || -1, t.errorCorrectLevel || r.H);
                return i.addData(n), i.make(), i
            };
        u.ErrorCorrectLevel = r;
        n.exports = u
    }, function (n, t, i) {
        function u(n, t) {
            this.typeNumber = n;
            this.errorCorrectLevel = t;
            this.modules = null;
            this.moduleCount = 0;
            this.dataCache = null;
            this.dataList = []
        }
        var s = i(5),
            e = i(7),
            o = i(9),
            f = i(10),
            h = i(11),
            r = u.prototype;
        r.addData = function (n) {
            var t = new s(n);
            this.dataList.push(t);
            this.dataCache = null
        };
        r.isDark = function (n, t) {
            if (n < 0 || this.moduleCount <= n || t < 0 || this.moduleCount <= t) throw new Error(n + "," + t);
            return this.modules[n][t]
        };
        r.getModuleCount = function () {
            return this.moduleCount
        };
        r.make = function () {
            var t, n, i;
            if (this.typeNumber < 1) {
                for (t = 1, t = 1; t < 40; t++) {
                    var u = e.getRSBlocks(t, this.errorCorrectLevel),
                        r = new o,
                        s = 0;
                    for (n = 0; n < u.length; n++) s += u[n].dataCount;
                    for (n = 0; n < this.dataList.length; n++) i = this.dataList[n], r.put(i.mode, 4), r.put(i.getLength(), f.getLengthInBits(i.mode, t)), i.write(r);
                    if (r.getLengthInBits() <= s * 8) break
                }
                this.typeNumber = t
            }
            this.makeImpl(!1, this.getBestMaskPattern())
        };
        r.makeImpl = function (n, t) {
            var i, r;
            for (this.moduleCount = this.typeNumber * 4 + 17, this.modules = new Array(this.moduleCount), i = 0; i < this.moduleCount; i++)
                for (this.modules[i] = new Array(this.moduleCount), r = 0; r < this.moduleCount; r++) this.modules[i][r] = null;
            this.setupPositionProbePattern(0, 0);
            this.setupPositionProbePattern(this.moduleCount - 7, 0);
            this.setupPositionProbePattern(0, this.moduleCount - 7);
            this.setupPositionAdjustPattern();
            this.setupTimingPattern();
            this.setupTypeInfo(n, t);
            this.typeNumber >= 7 && this.setupTypeNumber(n);
            this.dataCache == null && (this.dataCache = u.createData(this.typeNumber, this.errorCorrectLevel, this.dataList));
            this.mapData(this.dataCache, t)
        };
        r.setupPositionProbePattern = function (n, t) {
            for (var r, i = -1; i <= 7; i++)
                if (!(n + i <= -1) && !(this.moduleCount <= n + i))
                    for (r = -1; r <= 7; r++) t + r <= -1 || this.moduleCount <= t + r || (this.modules[n + i][t + r] = 0 <= i && i <= 6 && (r == 0 || r == 6) || 0 <= r && r <= 6 && (i == 0 || i == 6) || 2 <= i && i <= 4 && 2 <= r && r <= 4 ? !0 : !1)
        };
        r.getBestMaskPattern = function () {
            for (var t, i = 0, r = 0, n = 0; n < 8; n++) this.makeImpl(!0, n), t = f.getLostPoint(this), (n == 0 || i > t) && (i = t, r = n);
            return r
        };
        r.createMovieClip = function (n, t, i) {
            var r = n.createEmptyMovieClip(t, i),
                u = 1,
                f, e, o, s, h;
            for (this.make(), f = 0; f < this.modules.length; f++)
                for (e = f * u, o = 0; o < this.modules[f].length; o++) s = o * u, h = this.modules[f][o], h && (r.beginFill(0, 100), r.moveTo(s, e), r.lineTo(s + u, e), r.lineTo(s + u, e + u), r.lineTo(s, e + u), r.endFill());
            return r
        };
        r.setupTimingPattern = function () {
            for (var t, n = 8; n < this.moduleCount - 8; n++) this.modules[n][6] == null && (this.modules[n][6] = n % 2 == 0);
            for (t = 8; t < this.moduleCount - 8; t++) this.modules[6][t] == null && (this.modules[6][t] = t % 2 == 0)
        };
        r.setupPositionAdjustPattern = function () {
            for (var r, e, o, n, t, i = f.getPatternPosition(this.typeNumber), u = 0; u < i.length; u++)
                for (r = 0; r < i.length; r++)
                    if (e = i[u], o = i[r], this.modules[e][o] == null)
                        for (n = -2; n <= 2; n++)
                            for (t = -2; t <= 2; t++) this.modules[e + n][o + t] = n == -2 || n == 2 || t == -2 || t == 2 || n == 0 && t == 0 ? !0 : !1
        };
        r.setupTypeNumber = function (n) {
            for (var i, r = f.getBCHTypeNumber(this.typeNumber), t = 0; t < 18; t++) i = !n && (r >> t & 1) == 1, this.modules[Math.floor(t / 3)][t % 3 + this.moduleCount - 11] = i;
            for (t = 0; t < 18; t++) i = !n && (r >> t & 1) == 1, this.modules[t % 3 + this.moduleCount - 11][Math.floor(t / 3)] = i
        };
        r.setupTypeInfo = function (n, t) {
            for (var r, e = this.errorCorrectLevel << 3 | t, u = f.getBCHTypeInfo(e), i = 0; i < 15; i++) r = !n && (u >> i & 1) == 1, i < 6 ? this.modules[i][8] = r : i < 8 ? this.modules[i + 1][8] = r : this.modules[this.moduleCount - 15 + i][8] = r;
            for (i = 0; i < 15; i++) r = !n && (u >> i & 1) == 1, i < 8 ? this.modules[8][this.moduleCount - i - 1] = r : i < 9 ? this.modules[8][15 - i] = r : this.modules[8][14 - i] = r;
            this.modules[this.moduleCount - 8][8] = !n
        };
        r.mapData = function (n, t) {
            for (var u, e, c, o = -1, i = this.moduleCount - 1, s = 7, h = 0, r = this.moduleCount - 1; r > 0; r -= 2)
                for (r == 6 && r--;;) {
                    for (u = 0; u < 2; u++) this.modules[i][r - u] == null && (e = !1, h < n.length && (e = (n[h] >>> s & 1) == 1), c = f.getMask(t, i, r - u), c && (e = !e), this.modules[i][r - u] = e, s--, s == -1 && (h++, s = 7));
                    if (i += o, i < 0 || this.moduleCount <= i) {
                        i -= o;
                        o = -o;
                        break
                    }
                }
        };
        u.PAD0 = 236;
        u.PAD1 = 17;
        u.createData = function (n, t, i) {
            for (var c, h, l = e.getRSBlocks(n, t), r = new o, s = 0; s < i.length; s++) c = i[s], r.put(c.mode, 4), r.put(c.getLength(), f.getLengthInBits(c.mode, n)), c.write(r);
            for (h = 0, s = 0; s < l.length; s++) h += l[s].dataCount;
            if (r.getLengthInBits() > h * 8) throw new Error("code length overflow. (" + r.getLengthInBits() + ">" + h * 8 + ")");
            for (r.getLengthInBits() + 4 <= h * 8 && r.put(0, 4); r.getLengthInBits() % 8 != 0;) r.putBit(!1);
            for (;;) {
                if (r.getLengthInBits() >= h * 8) break;
                if (r.put(u.PAD0, 8), r.getLengthInBits() >= h * 8) break;
                r.put(u.PAD1, 8)
            }
            return u.createBytes(r, l)
        };
        u.createBytes = function (n, t) {
            for (var o, a, y, p, s, w, i, b = 0, c = 0, l = 0, u = new Array(t.length), e = new Array(t.length), r = 0; r < t.length; r++) {
                for (o = t[r].dataCount, a = t[r].totalCount - o, c = Math.max(c, o), l = Math.max(l, a), u[r] = new Array(o), i = 0; i < u[r].length; i++) u[r][i] = 255 & n.buffer[i + b];
                b += o;
                var v = f.getErrorCorrectPolynomial(a),
                    d = new h(u[r], v.getLength() - 1),
                    k = d.mod(v);
                for (e[r] = new Array(v.getLength() - 1), i = 0; i < e[r].length; i++) y = i + k.getLength() - e[r].length, e[r][i] = y >= 0 ? k.get(y) : 0
            }
            for (p = 0, i = 0; i < t.length; i++) p += t[i].totalCount;
            for (s = new Array(p), w = 0, i = 0; i < c; i++)
                for (r = 0; r < t.length; r++) i < u[r].length && (s[w++] = u[r][i]);
            for (i = 0; i < l; i++)
                for (r = 0; r < t.length; r++) i < e[r].length && (s[w++] = e[r][i]);
            return s
        };
        n.exports = u
    }, function (n, t, i) {
        function r(n) {
            this.mode = u.MODE_8BIT_BYTE;
            this.data = n
        }
        var u = i(6);
        r.prototype = {
            getLength: function () {
                return this.data.length
            },
            write: function (n) {
                for (var t = 0; t < this.data.length; t++) n.put(this.data.charCodeAt(t), 8)
            }
        };
        n.exports = r
    }, function (n) {
        n.exports = {
            MODE_NUMBER: 1,
            MODE_ALPHA_NUM: 2,
            MODE_8BIT_BYTE: 4,
            MODE_KANJI: 8
        }
    }, function (n, t, i) {
        function r(n, t) {
            this.totalCount = n;
            this.dataCount = t
        }
        var u = i(8);
        r.RS_BLOCK_TABLE = [
            [1, 26, 19],
            [1, 26, 16],
            [1, 26, 13],
            [1, 26, 9],
            [1, 44, 34],
            [1, 44, 28],
            [1, 44, 22],
            [1, 44, 16],
            [1, 70, 55],
            [1, 70, 44],
            [2, 35, 17],
            [2, 35, 13],
            [1, 100, 80],
            [2, 50, 32],
            [2, 50, 24],
            [4, 25, 9],
            [1, 134, 108],
            [2, 67, 43],
            [2, 33, 15, 2, 34, 16],
            [2, 33, 11, 2, 34, 12],
            [2, 86, 68],
            [4, 43, 27],
            [4, 43, 19],
            [4, 43, 15],
            [2, 98, 78],
            [4, 49, 31],
            [2, 32, 14, 4, 33, 15],
            [4, 39, 13, 1, 40, 14],
            [2, 121, 97],
            [2, 60, 38, 2, 61, 39],
            [4, 40, 18, 2, 41, 19],
            [4, 40, 14, 2, 41, 15],
            [2, 146, 116],
            [3, 58, 36, 2, 59, 37],
            [4, 36, 16, 4, 37, 17],
            [4, 36, 12, 4, 37, 13],
            [2, 86, 68, 2, 87, 69],
            [4, 69, 43, 1, 70, 44],
            [6, 43, 19, 2, 44, 20],
            [6, 43, 15, 2, 44, 16],
            [4, 101, 81],
            [1, 80, 50, 4, 81, 51],
            [4, 50, 22, 4, 51, 23],
            [3, 36, 12, 8, 37, 13],
            [2, 116, 92, 2, 117, 93],
            [6, 58, 36, 2, 59, 37],
            [4, 46, 20, 6, 47, 21],
            [7, 42, 14, 4, 43, 15],
            [4, 133, 107],
            [8, 59, 37, 1, 60, 38],
            [8, 44, 20, 4, 45, 21],
            [12, 33, 11, 4, 34, 12],
            [3, 145, 115, 1, 146, 116],
            [4, 64, 40, 5, 65, 41],
            [11, 36, 16, 5, 37, 17],
            [11, 36, 12, 5, 37, 13],
            [5, 109, 87, 1, 110, 88],
            [5, 65, 41, 5, 66, 42],
            [5, 54, 24, 7, 55, 25],
            [11, 36, 12],
            [5, 122, 98, 1, 123, 99],
            [7, 73, 45, 3, 74, 46],
            [15, 43, 19, 2, 44, 20],
            [3, 45, 15, 13, 46, 16],
            [1, 135, 107, 5, 136, 108],
            [10, 74, 46, 1, 75, 47],
            [1, 50, 22, 15, 51, 23],
            [2, 42, 14, 17, 43, 15],
            [5, 150, 120, 1, 151, 121],
            [9, 69, 43, 4, 70, 44],
            [17, 50, 22, 1, 51, 23],
            [2, 42, 14, 19, 43, 15],
            [3, 141, 113, 4, 142, 114],
            [3, 70, 44, 11, 71, 45],
            [17, 47, 21, 4, 48, 22],
            [9, 39, 13, 16, 40, 14],
            [3, 135, 107, 5, 136, 108],
            [3, 67, 41, 13, 68, 42],
            [15, 54, 24, 5, 55, 25],
            [15, 43, 15, 10, 44, 16],
            [4, 144, 116, 4, 145, 117],
            [17, 68, 42],
            [17, 50, 22, 6, 51, 23],
            [19, 46, 16, 6, 47, 17],
            [2, 139, 111, 7, 140, 112],
            [17, 74, 46],
            [7, 54, 24, 16, 55, 25],
            [34, 37, 13],
            [4, 151, 121, 5, 152, 122],
            [4, 75, 47, 14, 76, 48],
            [11, 54, 24, 14, 55, 25],
            [16, 45, 15, 14, 46, 16],
            [6, 147, 117, 4, 148, 118],
            [6, 73, 45, 14, 74, 46],
            [11, 54, 24, 16, 55, 25],
            [30, 46, 16, 2, 47, 17],
            [8, 132, 106, 4, 133, 107],
            [8, 75, 47, 13, 76, 48],
            [7, 54, 24, 22, 55, 25],
            [22, 45, 15, 13, 46, 16],
            [10, 142, 114, 2, 143, 115],
            [19, 74, 46, 4, 75, 47],
            [28, 50, 22, 6, 51, 23],
            [33, 46, 16, 4, 47, 17],
            [8, 152, 122, 4, 153, 123],
            [22, 73, 45, 3, 74, 46],
            [8, 53, 23, 26, 54, 24],
            [12, 45, 15, 28, 46, 16],
            [3, 147, 117, 10, 148, 118],
            [3, 73, 45, 23, 74, 46],
            [4, 54, 24, 31, 55, 25],
            [11, 45, 15, 31, 46, 16],
            [7, 146, 116, 7, 147, 117],
            [21, 73, 45, 7, 74, 46],
            [1, 53, 23, 37, 54, 24],
            [19, 45, 15, 26, 46, 16],
            [5, 145, 115, 10, 146, 116],
            [19, 75, 47, 10, 76, 48],
            [15, 54, 24, 25, 55, 25],
            [23, 45, 15, 25, 46, 16],
            [13, 145, 115, 3, 146, 116],
            [2, 74, 46, 29, 75, 47],
            [42, 54, 24, 1, 55, 25],
            [23, 45, 15, 28, 46, 16],
            [17, 145, 115],
            [10, 74, 46, 23, 75, 47],
            [10, 54, 24, 35, 55, 25],
            [19, 45, 15, 35, 46, 16],
            [17, 145, 115, 1, 146, 116],
            [14, 74, 46, 21, 75, 47],
            [29, 54, 24, 19, 55, 25],
            [11, 45, 15, 46, 46, 16],
            [13, 145, 115, 6, 146, 116],
            [14, 74, 46, 23, 75, 47],
            [44, 54, 24, 7, 55, 25],
            [59, 46, 16, 1, 47, 17],
            [12, 151, 121, 7, 152, 122],
            [12, 75, 47, 26, 76, 48],
            [39, 54, 24, 14, 55, 25],
            [22, 45, 15, 41, 46, 16],
            [6, 151, 121, 14, 152, 122],
            [6, 75, 47, 34, 76, 48],
            [46, 54, 24, 10, 55, 25],
            [2, 45, 15, 64, 46, 16],
            [17, 152, 122, 4, 153, 123],
            [29, 74, 46, 14, 75, 47],
            [49, 54, 24, 10, 55, 25],
            [24, 45, 15, 46, 46, 16],
            [4, 152, 122, 18, 153, 123],
            [13, 74, 46, 32, 75, 47],
            [48, 54, 24, 14, 55, 25],
            [42, 45, 15, 32, 46, 16],
            [20, 147, 117, 4, 148, 118],
            [40, 75, 47, 7, 76, 48],
            [43, 54, 24, 22, 55, 25],
            [10, 45, 15, 67, 46, 16],
            [19, 148, 118, 6, 149, 119],
            [18, 75, 47, 31, 76, 48],
            [34, 54, 24, 34, 55, 25],
            [20, 45, 15, 61, 46, 16]
        ];
        r.getRSBlocks = function (n, t) {
            var u = r.getRsBlockTable(n, t),
                o, f, i, e;
            if (u == undefined) throw new Error("bad rs block @ typeNumber:" + n + "/errorCorrectLevel:" + t);
            for (o = u.length / 3, f = [], i = 0; i < o; i++) {
                var s = u[i * 3 + 0],
                    h = u[i * 3 + 1],
                    c = u[i * 3 + 2];
                for (e = 0; e < s; e++) f.push(new r(h, c))
            }
            return f
        };
        r.getRsBlockTable = function (n, t) {
            switch (t) {
                case u.L:
                    return r.RS_BLOCK_TABLE[(n - 1) * 4 + 0];
                case u.M:
                    return r.RS_BLOCK_TABLE[(n - 1) * 4 + 1];
                case u.Q:
                    return r.RS_BLOCK_TABLE[(n - 1) * 4 + 2];
                case u.H:
                    return r.RS_BLOCK_TABLE[(n - 1) * 4 + 3];
                default:
                    return undefined
            }
        };
        n.exports = r
    }, function (n) {
        n.exports = {
            L: 1,
            M: 0,
            Q: 3,
            H: 2
        }
    }, function (n) {
        function t() {
            this.buffer = [];
            this.length = 0
        }
        t.prototype = {
            get: function (n) {
                var t = Math.floor(n / 8);
                return (this.buffer[t] >>> 7 - n % 8 & 1) == 1
            },
            put: function (n, t) {
                for (var i = 0; i < t; i++) this.putBit((n >>> t - i - 1 & 1) == 1)
            },
            getLengthInBits: function () {
                return this.length
            },
            putBit: function (n) {
                var t = Math.floor(this.length / 8);
                this.buffer.length <= t && this.buffer.push(0);
                n && (this.buffer[t] |= 128 >>> this.length % 8);
                this.length++
            }
        };
        n.exports = t
    }, function (n, t, i) {
        var u = i(6),
            e = i(11),
            o = i(12),
            f = {
                PATTERN000: 0,
                PATTERN001: 1,
                PATTERN010: 2,
                PATTERN011: 3,
                PATTERN100: 4,
                PATTERN101: 5,
                PATTERN110: 6,
                PATTERN111: 7
            },
            r = {
                PATTERN_POSITION_TABLE: [
                    [],
                    [6, 18],
                    [6, 22],
                    [6, 26],
                    [6, 30],
                    [6, 34],
                    [6, 22, 38],
                    [6, 24, 42],
                    [6, 26, 46],
                    [6, 28, 50],
                    [6, 30, 54],
                    [6, 32, 58],
                    [6, 34, 62],
                    [6, 26, 46, 66],
                    [6, 26, 48, 70],
                    [6, 26, 50, 74],
                    [6, 30, 54, 78],
                    [6, 30, 56, 82],
                    [6, 30, 58, 86],
                    [6, 34, 62, 90],
                    [6, 28, 50, 72, 94],
                    [6, 26, 50, 74, 98],
                    [6, 30, 54, 78, 102],
                    [6, 28, 54, 80, 106],
                    [6, 32, 58, 84, 110],
                    [6, 30, 58, 86, 114],
                    [6, 34, 62, 90, 118],
                    [6, 26, 50, 74, 98, 122],
                    [6, 30, 54, 78, 102, 126],
                    [6, 26, 52, 78, 104, 130],
                    [6, 30, 56, 82, 108, 134],
                    [6, 34, 60, 86, 112, 138],
                    [6, 30, 58, 86, 114, 142],
                    [6, 34, 62, 90, 118, 146],
                    [6, 30, 54, 78, 102, 126, 150],
                    [6, 24, 50, 76, 102, 128, 154],
                    [6, 28, 54, 80, 106, 132, 158],
                    [6, 32, 58, 84, 110, 136, 162],
                    [6, 26, 54, 82, 110, 138, 166],
                    [6, 30, 58, 86, 114, 142, 170]
                ],
                G15: 1335,
                G18: 7973,
                G15_MASK: 21522,
                getBCHTypeInfo: function (n) {
                    for (var t = n << 10; r.getBCHDigit(t) - r.getBCHDigit(r.G15) >= 0;) t ^= r.G15 << r.getBCHDigit(t) - r.getBCHDigit(r.G15);
                    return (n << 10 | t) ^ r.G15_MASK
                },
                getBCHTypeNumber: function (n) {
                    for (var t = n << 12; r.getBCHDigit(t) - r.getBCHDigit(r.G18) >= 0;) t ^= r.G18 << r.getBCHDigit(t) - r.getBCHDigit(r.G18);
                    return n << 12 | t
                },
                getBCHDigit: function (n) {
                    for (var t = 0; n != 0;) t++, n >>>= 1;
                    return t
                },
                getPatternPosition: function (n) {
                    return r.PATTERN_POSITION_TABLE[n - 1]
                },
                getMask: function (n, t, i) {
                    switch (n) {
                        case f.PATTERN000:
                            return (t + i) % 2 == 0;
                        case f.PATTERN001:
                            return t % 2 == 0;
                        case f.PATTERN010:
                            return i % 3 == 0;
                        case f.PATTERN011:
                            return (t + i) % 3 == 0;
                        case f.PATTERN100:
                            return (Math.floor(t / 2) + Math.floor(i / 3)) % 2 == 0;
                        case f.PATTERN101:
                            return t * i % 2 + t * i % 3 == 0;
                        case f.PATTERN110:
                            return (t * i % 2 + t * i % 3) % 2 == 0;
                        case f.PATTERN111:
                            return (t * i % 3 + (t + i) % 2) % 2 == 0;
                        default:
                            throw new Error("bad maskPattern:" + n);
                    }
                },
                getErrorCorrectPolynomial: function (n) {
                    for (var t = new e([1], 0), i = 0; i < n; i++) t = t.multiply(new e([1, o.gexp(i)], 0));
                    return t
                },
                getLengthInBits: function (n, t) {
                    if (1 <= t && t < 10) switch (n) {
                        case u.MODE_NUMBER:
                            return 10;
                        case u.MODE_ALPHA_NUM:
                            return 9;
                        case u.MODE_8BIT_BYTE:
                            return 8;
                        case u.MODE_KANJI:
                            return 8;
                        default:
                            throw new Error("mode:" + n);
                    } else if (t < 27) switch (n) {
                        case u.MODE_NUMBER:
                            return 12;
                        case u.MODE_ALPHA_NUM:
                            return 11;
                        case u.MODE_8BIT_BYTE:
                            return 16;
                        case u.MODE_KANJI:
                            return 10;
                        default:
                            throw new Error("mode:" + n);
                    } else if (t < 41) switch (n) {
                        case u.MODE_NUMBER:
                            return 14;
                        case u.MODE_ALPHA_NUM:
                            return 13;
                        case u.MODE_8BIT_BYTE:
                            return 16;
                        case u.MODE_KANJI:
                            return 12;
                        default:
                            throw new Error("mode:" + n);
                    } else throw new Error("type:" + t);
                },
                getLostPoint: function (n) {
                    for (var s, c, u, f, e, h, t, l, r = n.getModuleCount(), o = 0, i = 0; i < r; i++)
                        for (t = 0; t < r; t++) {
                            for (s = 0, c = n.isDark(i, t), u = -1; u <= 1; u++)
                                if (!(i + u < 0) && !(r <= i + u))
                                    for (f = -1; f <= 1; f++) t + f < 0 || r <= t + f || (u != 0 || f != 0) && c == n.isDark(i + u, t + f) && s++;
                            s > 5 && (o += 3 + s - 5)
                        }
                    for (i = 0; i < r - 1; i++)
                        for (t = 0; t < r - 1; t++) e = 0, n.isDark(i, t) && e++, n.isDark(i + 1, t) && e++, n.isDark(i, t + 1) && e++, n.isDark(i + 1, t + 1) && e++, (e == 0 || e == 4) && (o += 3);
                    for (i = 0; i < r; i++)
                        for (t = 0; t < r - 6; t++) n.isDark(i, t) && !n.isDark(i, t + 1) && n.isDark(i, t + 2) && n.isDark(i, t + 3) && n.isDark(i, t + 4) && !n.isDark(i, t + 5) && n.isDark(i, t + 6) && (o += 40);
                    for (t = 0; t < r; t++)
                        for (i = 0; i < r - 6; i++) n.isDark(i, t) && !n.isDark(i + 1, t) && n.isDark(i + 2, t) && n.isDark(i + 3, t) && n.isDark(i + 4, t) && !n.isDark(i + 5, t) && n.isDark(i + 6, t) && (o += 40);
                    for (h = 0, t = 0; t < r; t++)
                        for (i = 0; i < r; i++) n.isDark(i, t) && h++;
                    return l = Math.abs(100 * h / r / r - 50) / 5, o + l * 10
                }
            };
        n.exports = r
    }, function (n, t, i) {
        function u(n, t) {
            var i, r;
            if (n.length == undefined) throw new Error(n.length + "/" + t);
            for (i = 0; i < n.length && n[i] == 0;) i++;
            for (this.num = new Array(n.length - i + t), r = 0; r < n.length - i; r++) this.num[r] = n[r + i]
        }
        var r = i(12);
        u.prototype = {
            get: function (n) {
                return this.num[n]
            },
            getLength: function () {
                return this.num.length
            },
            multiply: function (n) {
                for (var t, f = new Array(this.getLength() + n.getLength() - 1), i = 0; i < this.getLength(); i++)
                    for (t = 0; t < n.getLength(); t++) f[i + t] ^= r.gexp(r.glog(this.get(i)) + r.glog(n.get(t)));
                return new u(f, 0)
            },
            mod: function (n) {
                var f, i, t;
                if (this.getLength() - n.getLength() < 0) return this;
                for (f = r.glog(this.get(0)) - r.glog(n.get(0)), i = new Array(this.getLength()), t = 0; t < this.getLength(); t++) i[t] = this.get(t);
                for (t = 0; t < n.getLength(); t++) i[t] ^= r.gexp(r.glog(n.get(t)) + f);
                return new u(i, 0).mod(n)
            }
        };
        n.exports = u
    }, function (n) {
        for (var i = {
                glog: function (n) {
                    if (n < 1) throw new Error("glog(" + n + ")");
                    return i.LOG_TABLE[n]
                },
                gexp: function (n) {
                    while (n < 0) n += 255;
                    while (n >= 256) n -= 255;
                    return i.EXP_TABLE[n]
                },
                EXP_TABLE: new Array(256),
                LOG_TABLE: new Array(256)
            }, t = 0; t < 8; t++) i.EXP_TABLE[t] = 1 << t;
        for (t = 8; t < 256; t++) i.EXP_TABLE[t] = i.EXP_TABLE[t - 4] ^ i.EXP_TABLE[t - 5] ^ i.EXP_TABLE[t - 6] ^ i.EXP_TABLE[t - 8];
        for (t = 0; t < 255; t++) i.LOG_TABLE[i.EXP_TABLE[t]] = t;
        n.exports = i
    }, function (n) {
        n.exports = '\n  <div>\n    <!-- todo: \':val\' is set as workaround for update not being fired on props change.. -->\n    <canvas\n      :style="{height: size + \'px\', width: size + \'px\'}"\n      :height="size"\n      :width="size"\n      ref="qr"\n      :val="val"\n    ><\/canvas>\n  <\/div>\n'
    }])
}),
function (n, t) {
    typeof exports == "object" && typeof module != "undefined" ? module.exports = t() : typeof define == "function" && define.amd ? define(t) : n.i18next = t()
}(this, function () {
    "use strict";

    function p(n) {
        return n == null ? "" : "" + n
    }

    function rt(n, t, i) {
        n.forEach(function (n) {
            t[n] && (i[n] = t[n])
        })
    }

    function c(n, t, i) {
        function f(n) {
            return n && n.indexOf("###") > -1 ? n.replace(/###/g, ".") : n
        }

        function e() {
            return !n || typeof n == "string"
        }
        for (var u = typeof t != "string" ? [].concat(t) : t.split("."), r; u.length > 1;) {
            if (e()) return {};
            r = f(u.shift());
            !n[r] && i && (n[r] = new i);
            n = n[r]
        }
        return e() ? {} : {
            obj: n,
            k: f(u.shift())
        }
    }

    function w(n, t, i) {
        var r = c(n, t, Object),
            u = r.obj,
            f = r.k;
        u[f] = i
    }

    function ut(n, t, i, r) {
        var e = c(n, t, Object),
            u = e.obj,
            f = e.k;
        u[f] = u[f] || [];
        r && (u[f] = u[f].concat(i));
        r || u[f].push(i)
    }

    function u(n, t) {
        var i = c(n, t),
            r = i.obj,
            u = i.k;
        return r ? r[u] : undefined
    }

    function b(n, t, i) {
        for (var r in t) r in n ? typeof n[r] == "string" || n[r] instanceof String || typeof t[r] == "string" || t[r] instanceof String ? i && (n[r] = t[r]) : b(n[r], t[r], i) : n[r] = t[r];
        return n
    }

    function f(n) {
        return n.replace(/[\-\[\]\/\{\}\(\)\*\+\?\.\\\^\$\|]/g, "\\$&")
    }

    function et(n) {
        return typeof n == "string" ? n.replace(/[&<>"'\/]/g, function (n) {
            return ft[n]
        }) : n
    }

    function l(n) {
        return n.interpolation = {
            unescapeSuffix: "HTML"
        }, n.interpolation.prefix = n.interpolationPrefix || "__", n.interpolation.suffix = n.interpolationSuffix || "__", n.interpolation.escapeValue = n.escapeInterpolation || !1, n.interpolation.nestingPrefix = n.reusePrefix || "$t(", n.interpolation.nestingSuffix = n.reuseSuffix || ")", n
    }

    function st(n) {
        return n.resStore && (n.resources = n.resStore), n.ns && n.ns.defaultNs ? (n.defaultNS = n.ns.defaultNs, n.ns = n.ns.namespaces) : n.defaultNS = n.ns || "translation", n.fallbackToDefaultNS && n.defaultNS && (n.fallbackNS = n.defaultNS), n.saveMissing = n.sendMissing, n.saveMissingTo = n.sendMissingTo || "current", n.returnNull = n.fallbackOnNull ? !1 : !0, n.returnEmptyString = n.fallbackOnEmpty ? !1 : !0, n.returnObjects = n.returnObjectTrees, n.joinArrays = "\n", n.returnedObjectHandler = n.objectTreeKeyHandler, n.parseMissingKeyHandler = n.parseMissingKey, n.appendNamespaceToMissingKey = !0, n.nsSeparator = n.nsseparator || ":", n.keySeparator = n.keyseparator || ".", n.shortcutFunction === "sprintf" && (n.overloadTranslationOptionHandler = function (n) {
            for (var i = [], t = 1; t < n.length; t++) i.push(n[t]);
            return {
                postProcess: "sprintf",
                sprintf: i
            }
        }), n.whitelist = n.lngWhitelist, n.preload = n.preload, n.load === "current" && (n.load = "currentOnly"), n.load === "unspecific" && (n.load = "languageOnly"), n.backend = n.backend || {}, n.backend.loadPath = n.resGetPath || "locales/__lng__/__ns__.json", n.backend.addPath = n.resPostPath || "locales/add/__lng__/__ns__", n.backend.allowMultiLoading = n.dynamicLoad, n.cache = n.cache || {}, n.cache.prefix = "res_", n.cache.expirationTime = 6048e5, n.cache.enabled = n.useLocalStorage ? !0 : !1, n = l(n), n.defaultVariables && (n.interpolation.defaultVariables = n.defaultVariables), n
    }

    function ht(n) {
        return n = l(n), n.joinArrays = "\n", n
    }

    function d(n) {
        return (n.interpolationPrefix || n.interpolationSuffix || n.escapeInterpolation) && (n = l(n)), n.nsSeparator = n.nsseparator, n.keySeparator = n.keyseparator, n.returnObjects = n.returnObjectTrees, n
    }

    function ct(n) {
        n.lng = function () {
            return t.deprecate("i18next.lng() can be replaced by i18next.language for detected language or i18next.languages for languages ordered by translation lookup."), n.services.languageUtils.toResolveHierarchy(n.language)[0]
        };
        n.preload = function (i, r) {
            t.deprecate("i18next.preload() can be replaced with i18next.loadLanguages()");
            n.loadLanguages(i, r)
        };
        n.setLng = function (i, r, u) {
            if (t.deprecate("i18next.setLng() can be replaced with i18next.changeLanguage() or i18next.getFixedT() to get a translation function with fixed language or namespace."), typeof r == "function" && (u = r, r = {}), r || (r = {}), r.fixLng === !0 && u) return u(null, n.getFixedT(i));
            n.changeLanguage(i, u)
        };
        n.addPostProcessor = function (i, r) {
            t.deprecate("i18next.addPostProcessor() can be replaced by i18next.use({ type: 'postProcessor', name: 'name', process: fc })");
            n.use({
                type: "postProcessor",
                name: i,
                process: r
            })
        }
    }

    function a(n) {
        return n.charAt(0).toUpperCase() + n.slice(1)
    }

    function yt() {
        var n = {};
        return at.forEach(function (t) {
            t.lngs.forEach(function (i) {
                return n[i] = {
                    numbers: t.nr,
                    plurals: vt[t.fc]
                }
            })
        }), n
    }

    function bt(n, t) {
        for (var i = n.indexOf(t); i !== -1;) n.splice(i, 1), i = n.indexOf(t)
    }

    function v() {
        return {
            debug: !1,
            initImmediate: !0,
            ns: ["translation"],
            defaultNS: ["translation"],
            fallbackLng: ["dev"],
            fallbackNS: !1,
            whitelist: !1,
            nonExplicitWhitelist: !1,
            load: "all",
            preload: !1,
            simplifyPluralSuffix: !0,
            keySeparator: ".",
            nsSeparator: ":",
            pluralSeparator: "_",
            contextSeparator: "_",
            saveMissing: !1,
            saveMissingTo: "fallback",
            missingKeyHandler: !1,
            postProcess: !1,
            returnNull: !0,
            returnEmptyString: !0,
            returnObjects: !1,
            joinArrays: !1,
            returnedObjectHandler: function () {},
            parseMissingKeyHandler: !1,
            appendNamespaceToMissingKey: !1,
            appendNamespaceToCIMode: !1,
            overloadTranslationOptionHandler: function (n) {
                return {
                    defaultValue: n[1]
                }
            },
            interpolation: {
                escapeValue: !0,
                format: function (n) {
                    return n
                },
                prefix: "{{",
                suffix: "}}",
                formatSeparator: ",",
                unescapePrefix: "-",
                nestingPrefix: "$t(",
                nestingSuffix: ")",
                defaultVariables: undefined
            }
        }
    }

    function h(n) {
        return typeof n.ns == "string" && (n.ns = [n.ns]), typeof n.fallbackLng == "string" && (n.fallbackLng = [n.fallbackLng]), typeof n.fallbackNS == "string" && (n.fallbackNS = [n.fallbackNS]), n.whitelist && n.whitelist.indexOf("cimode") < 0 && n.whitelist.push("cimode"), n
    }

    function y() {}
    var nt = typeof Symbol == "function" && typeof Symbol.iterator == "symbol" ? function (n) {
            return typeof n
        } : function (n) {
            return n && typeof Symbol == "function" && n.constructor === Symbol && n !== Symbol.prototype ? "symbol" : typeof n
        },
        i = function (n, t) {
            if (!(n instanceof t)) throw new TypeError("Cannot call a class as a function");
        },
        n = Object.assign || function (n) {
            for (var i, r, t = 1; t < arguments.length; t++) {
                i = arguments[t];
                for (r in i) Object.prototype.hasOwnProperty.call(i, r) && (n[r] = i[r])
            }
            return n
        },
        e = function (n, t) {
            if (typeof t != "function" && t !== null) throw new TypeError("Super expression must either be null or a function, not " + typeof t);
            n.prototype = Object.create(t && t.prototype, {
                constructor: {
                    value: n,
                    enumerable: !1,
                    writable: !0,
                    configurable: !0
                }
            });
            t && (Object.setPrototypeOf ? Object.setPrototypeOf(n, t) : n.__proto__ = t)
        },
        r = function (n, t) {
            if (!n) throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
            return t && (typeof t == "object" || typeof t == "function") ? t : n
        },
        s = function () {
            function n(n, t) {
                var r = [],
                    u = !0,
                    f = !1,
                    e = undefined,
                    i, o;
                try {
                    for (i = n[Symbol.iterator](); !(u = (o = i.next()).done); u = !0)
                        if (r.push(o.value), t && r.length === t) break
                } catch (s) {
                    f = !0;
                    e = s
                } finally {
                    try {
                        !u && i["return"] && i["return"]()
                    } finally {
                        if (f) throw e;
                    }
                }
                return r
            }
            return function (t, i) {
                if (Array.isArray(t)) return t;
                if (Symbol.iterator in Object(t)) return n(t, i);
                throw new TypeError("Invalid attempt to destructure non-iterable instance");
            }
        }(),
        tt = {
            type: "logger",
            log: function (n) {
                this._output("log", n)
            },
            warn: function (n) {
                this._output("warn", n)
            },
            error: function (n) {
                this._output("error", n)
            },
            _output: function (n, t) {
                console && console[n] && console[n].apply(console, Array.prototype.slice.call(t))
            }
        },
        it = function () {
            function t(n) {
                var r = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
                i(this, t);
                this.init(n, r)
            }
            return t.prototype.init = function (n) {
                var t = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
                this.prefix = t.prefix || "i18next:";
                this.logger = n || tt;
                this.options = t;
                this.debug = t.debug === !1 ? !1 : !0
            }, t.prototype.setDebug = function (n) {
                this.debug = n
            }, t.prototype.log = function () {
                this.forward(arguments, "log", "", !0)
            }, t.prototype.warn = function () {
                this.forward(arguments, "warn", "", !0)
            }, t.prototype.error = function () {
                this.forward(arguments, "error", "")
            }, t.prototype.deprecate = function () {
                this.forward(arguments, "warn", "WARNING DEPRECATED: ", !0)
            }, t.prototype.forward = function (n, t, i, r) {
                (!r || this.debug) && (typeof n[0] == "string" && (n[0] = i + this.prefix + " " + n[0]), this.logger[t](n))
            }, t.prototype.create = function (i) {
                return new t(this.logger, n({
                    prefix: this.prefix + ":" + i + ":"
                }, this.options))
            }, t
        }(),
        t = new it,
        o = function () {
            function n() {
                i(this, n);
                this.observers = {}
            }
            return n.prototype.on = function (n, t) {
                var i = this;
                n.split(" ").forEach(function (n) {
                    i.observers[n] = i.observers[n] || [];
                    i.observers[n].push(t)
                })
            }, n.prototype.off = function (n, t) {
                var i = this;
                this.observers[n] && this.observers[n].forEach(function () {
                    if (t) {
                        var r = i.observers[n].indexOf(t);
                        r > -1 && i.observers[n].splice(r, 1)
                    } else delete i.observers[n]
                })
            }, n.prototype.emit = function (n) {
                for (var u, f, i = arguments.length, r = Array(i > 1 ? i - 1 : 0), t = 1; t < i; t++) r[t - 1] = arguments[t];
                this.observers[n] && (u = [].concat(this.observers[n]), u.forEach(function (n) {
                    n.apply(undefined, r)
                }));
                this.observers["*"] && (f = [].concat(this.observers["*"]), f.forEach(function (t) {
                    var i;
                    t.apply(t, (i = [n]).concat.apply(i, r))
                }))
            }, n
        }(),
        ft = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
            "/": "&#x2F;"
        },
        ot = function (t) {
            function f() {
                var u = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {},
                    e = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {
                        ns: ["translation"],
                        defaultNS: "translation"
                    },
                    n;
                return i(this, f), n = r(this, t.call(this)), n.data = u, n.options = e, n
            }
            return e(f, t), f.prototype.addNamespaces = function (n) {
                this.options.ns.indexOf(n) < 0 && this.options.ns.push(n)
            }, f.prototype.removeNamespaces = function (n) {
                var t = this.options.ns.indexOf(n);
                t > -1 && this.options.ns.splice(t, 1)
            }, f.prototype.getResource = function (n, t, i) {
                var e = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {},
                    f = e.keySeparator || this.options.keySeparator,
                    r;
                return f === undefined && (f = "."), r = [n, t], i && typeof i != "string" && (r = r.concat(i)), i && typeof i == "string" && (r = r.concat(f ? i.split(f) : i)), n.indexOf(".") > -1 && (r = n.split(".")), u(this.data, r)
            }, f.prototype.addResource = function (n, t, i, r) {
                var e = arguments.length > 4 && arguments[4] !== undefined ? arguments[4] : {
                        silent: !1
                    },
                    f = this.options.keySeparator,
                    u;
                f === undefined && (f = ".");
                u = [n, t];
                i && (u = u.concat(f ? i.split(f) : i));
                n.indexOf(".") > -1 && (u = n.split("."), r = t, t = u[1]);
                this.addNamespaces(t);
                w(this.data, u, r);
                e.silent || this.emit("added", n, t, i, r)
            }, f.prototype.addResources = function (n, t, i) {
                for (var r in i) typeof i[r] == "string" && this.addResource(n, t, r, i[r], {
                    silent: !0
                });
                this.emit("added", n, t, i)
            }, f.prototype.addResourceBundle = function (t, i, r, f, e) {
                var s = [t, i],
                    o;
                t.indexOf(".") > -1 && (s = t.split("."), f = r, r = i, i = s[1]);
                this.addNamespaces(i);
                o = u(this.data, s) || {};
                f ? b(o, r, e) : o = n({}, o, r);
                w(this.data, s, o);
                this.emit("added", t, i, r)
            }, f.prototype.removeResourceBundle = function (n, t) {
                this.hasResourceBundle(n, t) && delete this.data[n][t];
                this.removeNamespaces(t);
                this.emit("removed", n, t)
            }, f.prototype.hasResourceBundle = function (n, t) {
                return this.getResource(n, t) !== undefined
            }, f.prototype.getResourceBundle = function (t, i) {
                return (i || (i = this.options.defaultNS), this.options.compatibilityAPI === "v1") ? n({}, this.getResource(t, i)) : this.getResource(t, i)
            }, f.prototype.toJSON = function () {
                return this.data
            }, f
        }(o),
        k = {
            processors: {},
            addPostProcessor: function (n) {
                this.processors[n.name] = n
            },
            handle: function (n, t, i, r, u) {
                var f = this;
                return n.forEach(function (n) {
                    f.processors[n] && (t = f.processors[n].process(t, i, r, u))
                }), t
            }
        },
        g = function (u) {
            function f(n) {
                var o = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {},
                    e;
                return i(this, f), e = r(this, u.call(this)), rt(["resourceStore", "languageUtils", "pluralResolver", "interpolator", "backendConnector"], n, e), e.options = o, e.logger = t.create("translator"), e
            }
            return e(f, u), f.prototype.changeLanguage = function (n) {
                n && (this.language = n)
            }, f.prototype.exists = function (n) {
                var t = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {
                    interpolation: {}
                };
                return this.options.compatibilityAPI === "v1" && (t = d(t)), this.resolve(n, t) !== undefined
            }, f.prototype.extractFromKey = function (n, t) {
                var i = t.nsSeparator || this.options.nsSeparator,
                    u, r, f;
                return i === undefined && (i = ":"), u = t.keySeparator || this.options.keySeparator || ".", r = t.ns || this.options.defaultNS, i && n.indexOf(i) > -1 && (f = n.split(i), (i !== u || i === u && this.options.ns.indexOf(f[0]) > -1) && (r = f.shift()), n = f.join(u)), typeof r == "string" && (r = [r]), {
                    key: n,
                    namespaces: r
                }
            }, f.prototype.translate = function (t) {
                var r = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {},
                    k, p, c, w, o, f, s, l;
                if ((typeof r == "undefined" ? "undefined" : nt(r)) !== "object" ? r = this.options.overloadTranslationOptionHandler(arguments) : this.options.compatibilityAPI === "v1" && (r = d(r)), t === undefined || t === null || t === "") return "";
                typeof t == "number" && (t = String(t));
                typeof t == "string" && (t = [t]);
                var g = r.keySeparator || this.options.keySeparator || ".",
                    b = this.extractFromKey(t[t.length - 1], r),
                    u = b.key,
                    a = b.namespaces,
                    e = a[a.length - 1],
                    v = r.lng || this.language,
                    tt = r.appendNamespaceToCIMode || this.options.appendNamespaceToCIMode;
                if (v && v.toLowerCase() === "cimode") return tt ? (k = r.nsSeparator || this.options.nsSeparator, e + k + u) : u;
                var i = this.resolve(t, r),
                    h = Object.prototype.toString.apply(i),
                    y = r.joinArrays !== undefined ? r.joinArrays : this.options.joinArrays;
                if (i && typeof i != "string" && ["[object Number]", "[object Function]", "[object RegExp]"].indexOf(h) < 0 && !(y && h === "[object Array]")) {
                    if (!r.returnObjects && !this.options.returnObjects) return this.logger.warn("accessing an object - but returnObjects options is not enabled!"), this.options.returnedObjectHandler ? this.options.returnedObjectHandler(u, i, r) : "key '" + u + " (" + this.language + ")' returned an object instead of string.";
                    if (r.keySeparator || this.options.keySeparator) {
                        p = h === "[object Array]" ? [] : {};
                        for (c in i) i.hasOwnProperty(c) && (p[c] = this.translate("" + u + g + c, n({}, r, {
                            joinArrays: !1,
                            ns: a
                        })));
                        i = p
                    }
                } else if (y && h === "[object Array]") i = i.join(y), i && (i = this.extendTranslation(i, u, r));
                else {
                    if (w = !1, o = !1, this.isValidLookup(i) || r.defaultValue === undefined || (w = !0, i = r.defaultValue), this.isValidLookup(i) || (o = !0, i = u), o || w) {
                        if (this.logger.log("missingKey", v, e, u, i), f = [], s = this.languageUtils.getFallbackCodes(this.options.fallbackLng, r.lng || this.language), this.options.saveMissingTo === "fallback" && s && s[0])
                            for (l = 0; l < s.length; l++) f.push(s[l]);
                        else this.options.saveMissingTo === "all" ? f = this.languageUtils.toResolveHierarchy(r.lng || this.language) : f.push(r.lng || this.language);
                        this.options.saveMissing && (this.options.missingKeyHandler ? this.options.missingKeyHandler(f, e, u, i) : this.backendConnector && this.backendConnector.saveMissing && this.backendConnector.saveMissing(f, e, u, i));
                        this.emit("missingKey", f, e, u, i)
                    }
                    i = this.extendTranslation(i, u, r);
                    o && i === u && this.options.appendNamespaceToMissingKey && (i = e + ":" + u);
                    o && this.options.parseMissingKeyHandler && (i = this.options.parseMissingKeyHandler(i))
                }
                return i
            }, f.prototype.extendTranslation = function (t, i, r) {
                var o = this,
                    u, f, e;
                return r.interpolation && this.interpolator.init(n({}, r, {
                    interpolation: n({}, this.options.interpolation, r.interpolation)
                })), u = r.replace && typeof r.replace != "string" ? r.replace : r, this.options.interpolation.defaultVariables && (u = n({}, this.options.interpolation.defaultVariables, u)), t = this.interpolator.interpolate(t, u, this.language), t = this.interpolator.nest(t, function () {
                    for (var t = arguments.length, i = Array(t), n = 0; n < t; n++) i[n] = arguments[n];
                    return o.translate.apply(o, i)
                }, r), r.interpolation && this.interpolator.reset(), f = r.postProcess || this.options.postProcess, e = typeof f == "string" ? [f] : f, t !== undefined && e && e.length && r.applyPostProcessor !== !1 && (t = k.handle(e, t, i, r, this)), t
            }, f.prototype.resolve = function (n) {
                var t = this,
                    i = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {},
                    r = void 0;
                return typeof n == "string" && (n = [n]), n.forEach(function (n) {
                    if (!t.isValidLookup(r)) {
                        var e = t.extractFromKey(n, i),
                            s = e.key,
                            u = e.namespaces;
                        t.options.fallbackNS && (u = u.concat(t.options.fallbackNS));
                        var f = i.count !== undefined && typeof i.count != "string",
                            o = i.context !== undefined && typeof i.context == "string" && i.context !== "",
                            h = i.lngs ? i.lngs : t.languageUtils.toResolveHierarchy(i.lng || t.language);
                        u.forEach(function (n) {
                            t.isValidLookup(r) || h.forEach(function (u) {
                                var l;
                                if (!t.isValidLookup(r)) {
                                    var e = s,
                                        h = [e],
                                        c = void 0;
                                    for (f && (c = t.pluralResolver.getSuffix(u, i.count)), f && o && h.push(e + c), o && h.push(e += "" + t.options.contextSeparator + i.context), f && h.push(e += c), l = void 0; l = h.pop();) t.isValidLookup(r) || (r = t.getResource(u, n, l, i))
                                }
                            })
                        })
                    }
                }), r
            }, f.prototype.isValidLookup = function (n) {
                return n !== undefined && !(!this.options.returnNull && n === null) && !(!this.options.returnEmptyString && n === "")
            }, f.prototype.getResource = function (n, t, i) {
                var r = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {};
                return this.resourceStore.getResource(n, t, i, r)
            }, f
        }(o),
        lt = function () {
            function n(r) {
                i(this, n);
                this.options = r;
                this.whitelist = this.options.whitelist || !1;
                this.logger = t.create("languageUtils")
            }
            return n.prototype.getScriptPartFromCode = function (n) {
                if (!n || n.indexOf("-") < 0) return null;
                var t = n.split("-");
                return t.length === 2 ? null : (t.pop(), this.formatLanguageCode(t.join("-")))
            }, n.prototype.getLanguagePartFromCode = function (n) {
                if (!n || n.indexOf("-") < 0) return n;
                var t = n.split("-");
                return this.formatLanguageCode(t[0])
            }, n.prototype.formatLanguageCode = function (n) {
                if (typeof n == "string" && n.indexOf("-") > -1) {
                    var i = ["hans", "hant", "latn", "cyrl", "cans", "mong", "arab"],
                        t = n.split("-");
                    return this.options.lowerCaseLng ? t = t.map(function (n) {
                        return n.toLowerCase()
                    }) : t.length === 2 ? (t[0] = t[0].toLowerCase(), t[1] = t[1].toUpperCase(), i.indexOf(t[1].toLowerCase()) > -1 && (t[1] = a(t[1].toLowerCase()))) : t.length === 3 && (t[0] = t[0].toLowerCase(), t[1].length === 2 && (t[1] = t[1].toUpperCase()), t[0] !== "sgn" && t[2].length === 2 && (t[2] = t[2].toUpperCase()), i.indexOf(t[1].toLowerCase()) > -1 && (t[1] = a(t[1].toLowerCase())), i.indexOf(t[2].toLowerCase()) > -1 && (t[2] = a(t[2].toLowerCase()))), t.join("-")
                }
                return this.options.cleanCode || this.options.lowerCaseLng ? n.toLowerCase() : n
            }, n.prototype.isWhitelisted = function (n) {
                return (this.options.load === "languageOnly" || this.options.nonExplicitWhitelist) && (n = this.getLanguagePartFromCode(n)), !this.whitelist || !this.whitelist.length || this.whitelist.indexOf(n) > -1
            }, n.prototype.getFallbackCodes = function (n, t) {
                if (!n) return [];
                if (typeof n == "string" && (n = [n]), Object.prototype.toString.apply(n) === "[object Array]") return n;
                if (!t) return n.default || [];
                var i = n[t];
                return i || (i = n[this.getScriptPartFromCode(t)]), i || (i = n[this.formatLanguageCode(t)]), i || (i = n.default), i || []
            }, n.prototype.toResolveHierarchy = function (n, t) {
                var r = this,
                    f = this.getFallbackCodes(t || this.options.fallbackLng || [], n),
                    u = [],
                    i = function (n) {
                        n && (r.isWhitelisted(n) ? u.push(n) : r.logger.warn("rejecting non-whitelisted language code: " + n))
                    };
                return typeof n == "string" && n.indexOf("-") > -1 ? (this.options.load !== "languageOnly" && i(this.formatLanguageCode(n)), this.options.load !== "languageOnly" && this.options.load !== "currentOnly" && i(this.getScriptPartFromCode(n)), this.options.load !== "currentOnly" && i(this.getLanguagePartFromCode(n))) : typeof n == "string" && i(this.formatLanguageCode(n)), f.forEach(function (n) {
                    u.indexOf(n) < 0 && i(r.formatLanguageCode(n))
                }), u
            }, n
        }(),
        at = [{
            lngs: ["ach", "ak", "am", "arn", "br", "fil", "gun", "ln", "mfe", "mg", "mi", "oc", "tg", "ti", "tr", "uz", "wa"],
            nr: [1, 2],
            fc: 1
        }, {
            lngs: ["af", "an", "ast", "az", "bg", "bn", "ca", "da", "de", "dev", "el", "en", "eo", "es", "es_ar", "et", "eu", "fi", "fo", "fur", "fy", "gl", "gu", "ha", "he", "hi", "hu", "hy", "ia", "it", "kn", "ku", "lb", "mai", "ml", "mn", "mr", "nah", "nap", "nb", "ne", "nl", "nn", "no", "nso", "pa", "pap", "pms", "ps", "pt", "pt_br", "rm", "sco", "se", "si", "so", "son", "sq", "sv", "sw", "ta", "te", "tk", "ur", "yo"],
            nr: [1, 2],
            fc: 2
        }, {
            lngs: ["ay", "bo", "cgg", "fa", "id", "ja", "jbo", "ka", "kk", "km", "ko", "ky", "lo", "ms", "sah", "su", "th", "tt", "ug", "vi", "wo", "zh"],
            nr: [1],
            fc: 3
        }, {
            lngs: ["be", "bs", "dz", "hr", "ru", "sr", "uk"],
            nr: [1, 2, 5],
            fc: 4
        }, {
            lngs: ["ar"],
            nr: [0, 1, 2, 3, 11, 100],
            fc: 5
        }, {
            lngs: ["cs", "sk"],
            nr: [1, 2, 5],
            fc: 6
        }, {
            lngs: ["csb", "pl"],
            nr: [1, 2, 5],
            fc: 7
        }, {
            lngs: ["cy"],
            nr: [1, 2, 3, 8],
            fc: 8
        }, {
            lngs: ["fr"],
            nr: [1, 2],
            fc: 9
        }, {
            lngs: ["ga"],
            nr: [1, 2, 3, 7, 11],
            fc: 10
        }, {
            lngs: ["gd"],
            nr: [1, 2, 3, 20],
            fc: 11
        }, {
            lngs: ["is"],
            nr: [1, 2],
            fc: 12
        }, {
            lngs: ["jv"],
            nr: [0, 1],
            fc: 13
        }, {
            lngs: ["kw"],
            nr: [1, 2, 3, 4],
            fc: 14
        }, {
            lngs: ["lt"],
            nr: [1, 2, 10],
            fc: 15
        }, {
            lngs: ["lv"],
            nr: [1, 2, 0],
            fc: 16
        }, {
            lngs: ["mk"],
            nr: [1, 2],
            fc: 17
        }, {
            lngs: ["mnk"],
            nr: [0, 1, 2],
            fc: 18
        }, {
            lngs: ["mt"],
            nr: [1, 2, 11, 20],
            fc: 19
        }, {
            lngs: ["or"],
            nr: [2, 1],
            fc: 2
        }, {
            lngs: ["ro"],
            nr: [1, 2, 20],
            fc: 20
        }, {
            lngs: ["sl"],
            nr: [5, 1, 2, 3],
            fc: 21
        }],
        vt = {
            1: function (n) {
                return Number(n > 1)
            },
            2: function (n) {
                return Number(n != 1)
            },
            3: function () {
                return 0
            },
            4: function (n) {
                return Number(n % 10 == 1 && n % 100 != 11 ? 0 : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 1 : 2)
            },
            5: function (n) {
                return Number(n === 0 ? 0 : n == 1 ? 1 : n == 2 ? 2 : n % 100 >= 3 && n % 100 <= 10 ? 3 : n % 100 >= 11 ? 4 : 5)
            },
            6: function (n) {
                return Number(n == 1 ? 0 : n >= 2 && n <= 4 ? 1 : 2)
            },
            7: function (n) {
                return Number(n == 1 ? 0 : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 1 : 2)
            },
            8: function (n) {
                return Number(n == 1 ? 0 : n == 2 ? 1 : n != 8 && n != 11 ? 2 : 3)
            },
            9: function (n) {
                return Number(n >= 2)
            },
            10: function (n) {
                return Number(n == 1 ? 0 : n == 2 ? 1 : n < 7 ? 2 : n < 11 ? 3 : 4)
            },
            11: function (n) {
                return Number(n == 1 || n == 11 ? 0 : n == 2 || n == 12 ? 1 : n > 2 && n < 20 ? 2 : 3)
            },
            12: function (n) {
                return Number(n % 10 != 1 || n % 100 == 11)
            },
            13: function (n) {
                return Number(n !== 0)
            },
            14: function (n) {
                return Number(n == 1 ? 0 : n == 2 ? 1 : n == 3 ? 2 : 3)
            },
            15: function (n) {
                return Number(n % 10 == 1 && n % 100 != 11 ? 0 : n % 10 >= 2 && (n % 100 < 10 || n % 100 >= 20) ? 1 : 2)
            },
            16: function (n) {
                return Number(n % 10 == 1 && n % 100 != 11 ? 0 : n !== 0 ? 1 : 2)
            },
            17: function (n) {
                return Number(n == 1 || n % 10 == 1 ? 0 : 1)
            },
            18: function (n) {
                return Number(n == 0 ? 0 : n == 1 ? 1 : 2)
            },
            19: function (n) {
                return Number(n == 1 ? 0 : n === 0 || n % 100 > 1 && n % 100 < 11 ? 1 : n % 100 > 10 && n % 100 < 20 ? 2 : 3)
            },
            20: function (n) {
                return Number(n == 1 ? 0 : n === 0 || n % 100 > 0 && n % 100 < 20 ? 1 : 2)
            },
            21: function (n) {
                return Number(n % 100 == 1 ? 1 : n % 100 == 2 ? 2 : n % 100 == 3 || n % 100 == 4 ? 3 : 0)
            }
        },
        pt = function () {
            function n(r) {
                var u = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
                i(this, n);
                this.languageUtils = r;
                this.options = u;
                this.logger = t.create("pluralResolver");
                this.rules = yt()
            }
            return n.prototype.addRule = function (n, t) {
                this.rules[n] = t
            }, n.prototype.getRule = function (n) {
                return this.rules[this.languageUtils.getLanguagePartFromCode(n)]
            }, n.prototype.needsPlural = function (n) {
                var t = this.getRule(n);
                return t && t.numbers.length <= 1 ? !1 : !0
            }, n.prototype.getSuffix = function (n, t) {
                var e = this,
                    i = this.getRule(n),
                    u, r, f;
                return i ? i.numbers.length === 1 ? "" : (u = i.noAbs ? i.plurals(t) : i.plurals(Math.abs(t)), r = i.numbers[u], this.options.simplifyPluralSuffix && i.numbers.length === 2 && i.numbers[0] === 1 && (r === 2 ? r = "plural" : r === 1 && (r = "")), f = function () {
                    return e.options.prepend && r.toString() ? e.options.prepend + r.toString() : r.toString()
                }, this.options.compatibilityJSON === "v1") ? r === 1 ? "" : typeof r == "number" ? "_plural_" + r.toString() : f() : this.options.compatibilityJSON === "v2" || i.numbers.length === 2 && i.numbers[0] === 1 || i.numbers.length === 2 && i.numbers[0] === 1 ? f() : this.options.prepend && u.toString() ? this.options.prepend + u.toString() : u.toString() : (this.logger.warn("no plural rule found for: " + n), "")
            }, n
        }(),
        wt = function () {
            function r() {
                var n = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {};
                i(this, r);
                this.logger = t.create("interpolator");
                this.init(n, !0)
            }
            return r.prototype.init = function () {
                var t = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {},
                    i = arguments[1],
                    n;
                i && (this.options = t, this.format = t.interpolation && t.interpolation.format || function (n) {
                    return n
                }, this.escape = t.interpolation && t.interpolation.escape || et);
                t.interpolation || (t.interpolation = {
                    escapeValue: !0
                });
                n = t.interpolation;
                this.escapeValue = n.escapeValue !== undefined ? n.escapeValue : !0;
                this.prefix = n.prefix ? f(n.prefix) : n.prefixEscaped || "{{";
                this.suffix = n.suffix ? f(n.suffix) : n.suffixEscaped || "}}";
                this.formatSeparator = n.formatSeparator ? n.formatSeparator : n.formatSeparator || ",";
                this.unescapePrefix = n.unescapeSuffix ? "" : n.unescapePrefix || "-";
                this.unescapeSuffix = this.unescapePrefix ? "" : n.unescapeSuffix || "";
                this.nestingPrefix = n.nestingPrefix ? f(n.nestingPrefix) : n.nestingPrefixEscaped || f("$t(");
                this.nestingSuffix = n.nestingSuffix ? f(n.nestingSuffix) : n.nestingSuffixEscaped || f(")");
                this.resetRegExp()
            }, r.prototype.reset = function () {
                this.options && this.init(this.options)
            }, r.prototype.resetRegExp = function () {
                var i = this.prefix + "(.+?)" + this.suffix,
                    n, t;
                this.regexp = new RegExp(i, "g");
                n = this.prefix + this.unescapePrefix + "(.+?)" + this.unescapeSuffix + this.suffix;
                this.regexpUnescape = new RegExp(n, "g");
                t = this.nestingPrefix + "(.+?)" + this.nestingSuffix;
                this.nestingRegexp = new RegExp(t, "g")
            }, r.prototype.interpolate = function (n, t, i) {
                function o(n) {
                    return n.replace(/\$/g, "$$$$")
                }
                var e = this,
                    f = void 0,
                    r = void 0,
                    s = function (n) {
                        if (n.indexOf(e.formatSeparator) < 0) return u(t, n);
                        var r = n.split(e.formatSeparator),
                            f = r.shift().trim(),
                            o = r.join(e.formatSeparator).trim();
                        return e.format(u(t, f), o, i)
                    },
                    h;
                for (this.resetRegExp(); f = this.regexpUnescape.exec(n);) h = s(f[1].trim()), n = n.replace(f[0], h), this.regexpUnescape.lastIndex = 0;
                while (f = this.regexp.exec(n)) r = s(f[1].trim()), typeof r != "string" && (r = p(r)), r || (this.logger.warn("missed to pass in variable " + f[1] + " for interpolating " + n), r = ""), r = this.escapeValue ? o(this.escape(r)) : o(r), n = n.replace(f[0], r), this.regexp.lastIndex = 0;
                return n
            }, r.prototype.nest = function (t, i) {
                function o(n) {
                    var i, t;
                    if (n.indexOf(",") < 0) return n;
                    i = n.split(",");
                    n = i.shift();
                    t = i.join(",");
                    t = this.interpolate(t, f);
                    t = t.replace(/'/g, '"');
                    try {
                        f = JSON.parse(t)
                    } catch (r) {
                        this.logger.error("failed parsing options string in nesting for key " + n, r)
                    }
                    return n
                }
                var e = arguments.length > 2 && arguments[2] !== undefined ? arguments[2] : {},
                    u = void 0,
                    r = void 0,
                    f = n({}, e);
                for (f.applyPostProcessor = !1; u = this.nestingRegexp.exec(t);) r = i(o.call(this, u[1].trim()), f), typeof r != "string" && (r = p(r)), r || (this.logger.warn("missed to pass in variable " + u[1] + " for interpolating " + t), r = ""), t = t.replace(u[0], r), this.regexp.lastIndex = 0;
                return t
            }, r
        }(),
        kt = function (f) {
            function o(n, u, e) {
                var h = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {},
                    s;
                return i(this, o), s = r(this, f.call(this)), s.backend = n, s.store = u, s.services = e, s.options = h, s.logger = t.create("backendConnector"), s.state = {}, s.queue = [], s.backend && s.backend.init && s.backend.init(e, h.backend, h), s
            }
            return e(o, f), o.prototype.queueLoad = function (n, t, i) {
                var u = this,
                    f = [],
                    r = [],
                    o = [],
                    e = [];
                return n.forEach(function (n) {
                    var i = !0;
                    t.forEach(function (t) {
                        var o = n + "|" + t;
                        u.store.hasResourceBundle(n, t) ? u.state[o] = 2 : u.state[o] < 0 || (u.state[o] === 1 ? r.indexOf(o) < 0 && r.push(o) : (u.state[o] = 1, i = !1, r.indexOf(o) < 0 && r.push(o), f.indexOf(o) < 0 && f.push(o), e.indexOf(t) < 0 && e.push(t)))
                    });
                    i || o.push(n)
                }), (f.length || r.length) && this.queue.push({
                    pending: r,
                    loaded: {},
                    errors: [],
                    callback: i
                }), {
                    toLoad: f,
                    pending: r,
                    toLoadLanguages: o,
                    toLoadNamespaces: e
                }
            }, o.prototype.loaded = function (n, t, i) {
                var e = this,
                    o = n.split("|"),
                    f = s(o, 2),
                    r = f[0],
                    u = f[1];
                t && this.emit("failedLoading", r, u, t);
                i && this.store.addResourceBundle(r, u, i);
                this.state[n] = t ? -1 : 2;
                this.queue.forEach(function (i) {
                    ut(i.loaded, [r], u);
                    bt(i.pending, n);
                    t && i.errors.push(t);
                    i.pending.length !== 0 || i.done || (e.emit("loaded", i.loaded), i.errors.length ? i.callback(i.errors) : i.callback(), i.done = !0)
                });
                this.queue = this.queue.filter(function (n) {
                    return !n.done
                })
            }, o.prototype.read = function (n, t, i, r, u, f) {
                var e = this;
                if (r || (r = 0), u || (u = 250), !n.length) return f(null, {});
                this.backend[i](n, t, function (o, s) {
                    if (o && s && r < 5) {
                        setTimeout(function () {
                            e.read.call(e, n, t, i, ++r, u * 2, f)
                        }, u);
                        return
                    }
                    f(o, s)
                })
            }, o.prototype.load = function (t, i, r) {
                var e = this,
                    o, f, h;
                if (!this.backend) return this.logger.warn("No backend was added via i18next.use. Will not load resources."), r && r();
                if (o = n({}, this.backend.options, this.options.backend), typeof t == "string" && (t = this.services.languageUtils.toResolveHierarchy(t)), typeof i == "string" && (i = [i]), f = this.queueLoad(t, i, r), !f.toLoad.length) {
                    f.pending.length || r();
                    return
                }
                o.allowMultiLoading && this.backend.readMulti ? this.read(f.toLoadLanguages, f.toLoadNamespaces, "readMulti", null, null, function (n, t) {
                    n && e.logger.warn("loading namespaces " + f.toLoadNamespaces.join(", ") + " for languages " + f.toLoadLanguages.join(", ") + " via multiloading failed", n);
                    !n && t && e.logger.log("loaded namespaces " + f.toLoadNamespaces.join(", ") + " for languages " + f.toLoadLanguages.join(", ") + " via multiloading", t);
                    f.toLoad.forEach(function (i) {
                        var l = i.split("|"),
                            f = s(l, 2),
                            o = f[0],
                            h = f[1],
                            c = u(t, [o, h]),
                            r;
                        c ? e.loaded(i, n, c) : (r = "loading namespace " + h + " for language " + o + " via multiloading failed", e.loaded(i, r), e.logger.error(r))
                    })
                }) : (h = function (n) {
                    var t = this,
                        f = n.split("|"),
                        u = s(f, 2),
                        i = u[0],
                        r = u[1];
                    this.read(i, r, "read", null, null, function (u, f) {
                        u && t.logger.warn("loading namespace " + r + " for language " + i + " failed", u);
                        !u && f && t.logger.log("loaded namespace " + r + " for language " + i, f);
                        t.loaded(n, u, f)
                    })
                }, f.toLoad.forEach(function (n) {
                    h.call(e, n)
                }))
            }, o.prototype.reload = function (t, i) {
                var r = this,
                    f, e;
                this.backend || this.logger.warn("No backend was added via i18next.use. Will not load resources.");
                f = n({}, this.backend.options, this.options.backend);
                typeof t == "string" && (t = this.services.languageUtils.toResolveHierarchy(t));
                typeof i == "string" && (i = [i]);
                f.allowMultiLoading && this.backend.readMulti ? this.read(t, i, "readMulti", null, null, function (n, f) {
                    n && r.logger.warn("reloading namespaces " + i.join(", ") + " for languages " + t.join(", ") + " via multiloading failed", n);
                    !n && f && r.logger.log("reloaded namespaces " + i.join(", ") + " for languages " + t.join(", ") + " via multiloading", f);
                    t.forEach(function (t) {
                        i.forEach(function (i) {
                            var o = u(f, [t, i]),
                                e;
                            o ? r.loaded(t + "|" + i, n, o) : (e = "reloading namespace " + i + " for language " + t + " via multiloading failed", r.loaded(t + "|" + i, e), r.logger.error(e))
                        })
                    })
                }) : (e = function (n) {
                    var t = this,
                        f = n.split("|"),
                        u = s(f, 2),
                        i = u[0],
                        r = u[1];
                    this.read(i, r, "read", null, null, function (u, f) {
                        u && t.logger.warn("reloading namespace " + r + " for language " + i + " failed", u);
                        !u && f && t.logger.log("reloaded namespace " + r + " for language " + i, f);
                        t.loaded(n, u, f)
                    })
                }, t.forEach(function (n) {
                    i.forEach(function (t) {
                        e.call(r, n + "|" + t)
                    })
                }))
            }, o.prototype.saveMissing = function (n, t, i, r) {
                (this.backend && this.backend.create && this.backend.create(n, t, i, r), n && n[0]) && this.store.addResource(n[0], t, i, r)
            }, o
        }(o),
        dt = function (u) {
            function f(n, e, o) {
                var h = arguments.length > 3 && arguments[3] !== undefined ? arguments[3] : {},
                    s;
                return i(this, f), s = r(this, u.call(this)), s.cache = n, s.store = e, s.services = o, s.options = h, s.logger = t.create("cacheConnector"), s.cache && s.cache.init && s.cache.init(o, h.cache, h), s
            }
            return e(f, u), f.prototype.load = function (t, i, r) {
                var u = this,
                    f;
                if (!this.cache) return r && r();
                f = n({}, this.cache.options, this.options.cache);
                typeof t == "string" && (t = this.services.languageUtils.toResolveHierarchy(t));
                typeof i == "string" && (i = [i]);
                f.enabled ? this.cache.load(t, function (n, i) {
                    var f, e, o;
                    if (n && u.logger.error("loading languages " + t.join(", ") + " from cache failed", n), i)
                        for (f in i)
                            for (e in i[f]) e !== "i18nStamp" && (o = i[f][e], o && u.store.addResourceBundle(f, e, o));
                    r && r()
                }) : r && r()
            }, f.prototype.save = function () {
                this.cache && this.options.cache && this.options.cache.enabled && this.cache.save(this.store.data)
            }, f
        }(o),
        gt = function (u) {
            function f() {
                var e = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {},
                    o = arguments[1],
                    n, s;
                if (i(this, f), n = r(this, u.call(this)), n.options = h(e), n.services = {}, n.logger = t, n.modules = {
                        external: []
                    }, o && !n.isInitialized && !e.isClone) {
                    if (!n.options.initImmediate) return s = n.init(e, o), r(n, s);
                    setTimeout(function () {
                        n.init(e, o)
                    }, 0)
                }
                return n
            }
            return e(f, u), f.prototype.init = function (i, r) {
                function e(n) {
                    if (n) return typeof n == "function" ? new n : n
                }
                var f = this,
                    o, u, c, s;
                if (typeof i == "function" && (r = i, i = {}), i || (i = {}), this.options = i.compatibilityAPI === "v1" ? n({}, v(), h(st(i)), {}) : i.compatibilityJSON === "v1" ? n({}, v(), h(ht(i)), {}) : n({}, v(), this.options, h(i)), r || (r = y), !this.options.isClone) {
                    this.modules.logger ? t.init(e(this.modules.logger), this.options) : t.init(null, this.options);
                    o = new lt(this.options);
                    this.store = new ot(this.options.resources, this.options);
                    u = this.services;
                    u.logger = t;
                    u.resourceStore = this.store;
                    u.resourceStore.on("added removed", function () {
                        u.cacheConnector.save()
                    });
                    u.languageUtils = o;
                    u.pluralResolver = new pt(o, {
                        prepend: this.options.pluralSeparator,
                        compatibilityJSON: this.options.compatibilityJSON,
                        simplifyPluralSuffix: this.options.simplifyPluralSuffix
                    });
                    u.interpolator = new wt(this.options);
                    u.backendConnector = new kt(e(this.modules.backend), u.resourceStore, u, this.options);
                    u.backendConnector.on("*", function (n) {
                        for (var i = arguments.length, r = Array(i > 1 ? i - 1 : 0), t = 1; t < i; t++) r[t - 1] = arguments[t];
                        f.emit.apply(f, [n].concat(r))
                    });
                    u.backendConnector.on("loaded", function () {
                        u.cacheConnector.save()
                    });
                    u.cacheConnector = new dt(e(this.modules.cache), u.resourceStore, u, this.options);
                    u.cacheConnector.on("*", function (n) {
                        for (var i = arguments.length, r = Array(i > 1 ? i - 1 : 0), t = 1; t < i; t++) r[t - 1] = arguments[t];
                        f.emit.apply(f, [n].concat(r))
                    });
                    this.modules.languageDetector && (u.languageDetector = e(this.modules.languageDetector), u.languageDetector.init(u, this.options.detection, this.options));
                    this.translator = new g(this.services, this.options);
                    this.translator.on("*", function (n) {
                        for (var i = arguments.length, r = Array(i > 1 ? i - 1 : 0), t = 1; t < i; t++) r[t - 1] = arguments[t];
                        f.emit.apply(f, [n].concat(r))
                    });
                    this.modules.external.forEach(function (n) {
                        n.init && n.init(f)
                    })
                }
                return c = ["getResource", "addResource", "addResources", "addResourceBundle", "removeResourceBundle", "hasResourceBundle", "getResourceBundle"], c.forEach(function (n) {
                    f[n] = function () {
                        return this.store[n].apply(this.store, arguments)
                    }
                }), this.options.compatibilityAPI === "v1" && ct(this), s = function () {
                    f.changeLanguage(f.options.lng, function (n, t) {
                        f.isInitialized = !0;
                        f.logger.log("initialized", f.options);
                        f.emit("initialized", f.options);
                        r(n, t)
                    })
                }, this.options.resources || !this.options.initImmediate ? s() : setTimeout(s, 0), this
            }, f.prototype.loadResources = function () {
                var i = this,
                    r = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : y,
                    n, t, u;
                if (this.options.resources) r(null);
                else {
                    if (this.language && this.language.toLowerCase() === "cimode") return r();
                    n = [];
                    t = function (t) {
                        if (t) {
                            var r = i.services.languageUtils.toResolveHierarchy(t);
                            r.forEach(function (t) {
                                n.indexOf(t) < 0 && n.push(t)
                            })
                        }
                    };
                    this.language ? t(this.language) : (u = this.services.languageUtils.getFallbackCodes(this.options.fallbackLng), u.forEach(function (n) {
                        return t(n)
                    }));
                    this.options.preload && this.options.preload.forEach(function (n) {
                        return t(n)
                    });
                    this.services.cacheConnector.load(n, this.options.ns, function () {
                        i.services.backendConnector.load(n, i.options.ns, r)
                    })
                }
            }, f.prototype.reloadResources = function (n, t) {
                n || (n = this.languages);
                t || (t = this.options.ns);
                this.services.backendConnector.reload(n, t)
            }, f.prototype.use = function (n) {
                return n.type === "backend" && (this.modules.backend = n), n.type === "cache" && (this.modules.cache = n), (n.type === "logger" || n.log && n.warn && n.error) && (this.modules.logger = n), n.type === "languageDetector" && (this.modules.languageDetector = n), n.type === "postProcessor" && k.addPostProcessor(n), n.type === "3rdParty" && this.modules.external.push(n), this
            }, f.prototype.changeLanguage = function (n, t) {
                var i = this,
                    r = function (r) {
                        n && (i.emit("languageChanged", n), i.logger.log("languageChanged", n));
                        t && t(r, function () {
                            for (var t = arguments.length, r = Array(t), n = 0; n < t; n++) r[n] = arguments[n];
                            return i.t.apply(i, r)
                        })
                    };
                !n && this.services.languageDetector && (n = this.services.languageDetector.detect());
                n && (this.language = n, this.languages = this.services.languageUtils.toResolveHierarchy(n), this.translator.changeLanguage(n), this.services.languageDetector && this.services.languageDetector.cacheUserLanguage(n));
                this.loadResources(function (n) {
                    r(n)
                })
            }, f.prototype.getFixedT = function (t, i) {
                var u = this,
                    r = function r(t) {
                        var f = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {},
                            i = n({}, f);
                        return i.lng = i.lng || r.lng, i.ns = i.ns || r.ns, u.t(t, i)
                    };
                return r.lng = t, r.ns = i, r
            }, f.prototype.t = function () {
                return this.translator && this.translator.translate.apply(this.translator, arguments)
            }, f.prototype.exists = function () {
                return this.translator && this.translator.exists.apply(this.translator, arguments)
            }, f.prototype.setDefaultNamespace = function (n) {
                this.options.defaultNS = n
            }, f.prototype.loadNamespaces = function (n, t) {
                var i = this;
                if (!this.options.ns) return t && t();
                typeof n == "string" && (n = [n]);
                n.forEach(function (n) {
                    i.options.ns.indexOf(n) < 0 && i.options.ns.push(n)
                });
                this.loadResources(t)
            }, f.prototype.loadLanguages = function (n, t) {
                typeof n == "string" && (n = [n]);
                var i = this.options.preload || [],
                    r = n.filter(function (n) {
                        return i.indexOf(n) < 0
                    });
                if (!r.length) return t();
                this.options.preload = i.concat(r);
                this.loadResources(t)
            }, f.prototype.dir = function (n) {
                if (n || (n = this.language), !n) return "rtl";
                return ["ar", "shu", "sqr", "ssh", "xaa", "yhd", "yud", "aao", "abh", "abv", "acm", "acq", "acw", "acx", "acy", "adf", "ads", "aeb", "aec", "afb", "ajp", "apc", "apd", "arb", "arq", "ars", "ary", "arz", "auz", "avl", "ayh", "ayl", "ayn", "ayp", "bbz", "pga", "he", "iw", "ps", "pbt", "pbu", "pst", "prp", "prd", "ur", "ydd", "yds", "yih", "ji", "yi", "hbo", "men", "xmn", "fa", "jpr", "peo", "pes", "prs", "dv", "sam"].indexOf(this.services.languageUtils.getLanguagePartFromCode(n)) >= 0 ? "rtl" : "ltr"
            }, f.prototype.createInstance = function () {
                var n = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {},
                    t = arguments[1];
                return new f(n, t)
            }, f.prototype.cloneInstance = function () {
                var u = this,
                    e = arguments.length > 0 && arguments[0] !== undefined ? arguments[0] : {},
                    i = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : y,
                    r = n({}, e, this.options, {
                        isClone: !0
                    }),
                    t = new f(r, i);
                ["store", "services", "language"].forEach(function (n) {
                    t[n] = u[n]
                });
                t.translator = new g(t.services, t.options);
                t.translator.on("*", function (n) {
                    for (var r = arguments.length, u = Array(r > 1 ? r - 1 : 0), i = 1; i < r; i++) u[i - 1] = arguments[i];
                    t.emit.apply(t, [n].concat(u))
                });
                return t.init(r, i), t
            }, f
        }(o);
    return new gt
}),
function (n, t) {
    typeof exports == "object" && typeof module != "undefined" ? module.exports = t() : typeof define == "function" && define.amd ? define(t) : n.i18nextXHRBackend = t()
}(this, function () {
    "use strict";

    function e(n) {
        return u.call(f.call(arguments, 1), function (t) {
            if (t)
                for (var i in t) n[i] === undefined && (n[i] = t[i])
        }), n
    }

    function i(n, i) {
        var r, u, f;
        if (i && (typeof i == "undefined" ? "undefined" : t(i)) === "object") {
            r = "";
            u = encodeURIComponent;
            for (f in i) r += "&" + u(f) + "=" + u(i[f]);
            if (!r) return n;
            n = n + (n.indexOf("?") !== -1 ? "&" : "?") + r.slice(1)
        }
        return n
    }

    function o(n, r, u, f, e) {
        var o, s, h;
        f && (typeof f == "undefined" ? "undefined" : t(f)) === "object" && (e || (f._t = new Date), f = i("", f).slice(1));
        r.queryStringParams && (n = i(n, r.queryStringParams));
        try {
            if (o = XMLHttpRequest ? new XMLHttpRequest : new ActiveXObject("MSXML2.XMLHTTP.3.0"), o.open(f ? "POST" : "GET", n, 1), r.crossDomain || o.setRequestHeader("X-Requested-With", "XMLHttpRequest"), o.withCredentials = !!r.withCredentials, f && o.setRequestHeader("Content-type", "application/x-www-form-urlencoded"), o.overrideMimeType && o.overrideMimeType("application/json"), s = r.customHeaders, s)
                for (h in s) o.setRequestHeader(h, s[h]);
            o.onreadystatechange = function () {
                o.readyState > 3 && u && u(o.responseText, o)
            };
            o.send(f)
        } catch (c) {
            console && console.log(c)
        }
    }

    function h(n, t) {
        if (!(n instanceof t)) throw new TypeError("Cannot call a class as a function");
    }

    function c() {
        return {
            loadPath: "/locales/{{lng}}/{{ns}}.json",
            addPath: "/locales/add/{{lng}}/{{ns}}",
            allowMultiLoading: !1,
            parse: JSON.parse,
            crossDomain: !1,
            ajax: o
        }
    }
    var n = [],
        u = n.forEach,
        f = n.slice,
        t = typeof Symbol == "function" && typeof Symbol.iterator == "symbol" ? function (n) {
            return typeof n
        } : function (n) {
            return n && typeof Symbol == "function" && n.constructor === Symbol && n !== Symbol.prototype ? "symbol" : typeof n
        },
        s = function () {
            function n(n, t) {
                for (var i, r = 0; r < t.length; r++) i = t[r], i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(n, i.key, i)
            }
            return function (t, i, r) {
                return i && n(t.prototype, i), r && n(t, r), t
            }
        }(),
        r = function () {
            function n(t) {
                var i = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
                h(this, n);
                this.init(t, i);
                this.type = "backend"
            }
            return s(n, [{
                key: "init",
                value: function (n) {
                    var t = arguments.length > 1 && arguments[1] !== undefined ? arguments[1] : {};
                    this.services = n;
                    this.options = e(t, this.options || {}, c())
                }
            }, {
                key: "readMulti",
                value: function (n, t, i) {
                    var r = this.options.loadPath,
                        u;
                    typeof this.options.loadPath == "function" && (r = this.options.loadPath(n, t));
                    u = this.services.interpolator.interpolate(r, {
                        lng: n.join("+"),
                        ns: t.join("+")
                    });
                    this.loadUrl(u, i)
                }
            }, {
                key: "read",
                value: function (n, t, i) {
                    var r = this.options.loadPath,
                        u;
                    typeof this.options.loadPath == "function" && (r = this.options.loadPath([n], [t]));
                    u = this.services.interpolator.interpolate(r, {
                        lng: n,
                        ns: t
                    });
                    this.loadUrl(u, i)
                }
            }, {
                key: "loadUrl",
                value: function (n, t) {
                    var i = this;
                    this.options.ajax(n, this.options, function (r, u) {
                        if (u.status >= 500 && u.status < 600) return t("failed loading " + n, !0);
                        if (u.status >= 400 && u.status < 500) return t("failed loading " + n, !1);
                        var e = void 0,
                            f = void 0;
                        try {
                            e = i.options.parse(r, n)
                        } catch (o) {
                            f = "failed parsing " + n + " to json"
                        }
                        if (f) return t(f, !1);
                        t(null, e)
                    })
                }
            }, {
                key: "create",
                value: function (n, t, i, r) {
                    var u = this,
                        f;
                    typeof n == "string" && (n = [n]);
                    f = {};
                    f[i] = r || "";
                    n.forEach(function (n) {
                        var i = u.services.interpolator.interpolate(u.options.addPath, {
                            lng: n,
                            ns: t
                        });
                        u.options.ajax(i, u.options, function () {}, f)
                    })
                }
            }]), n
        }();
    return r.type = "backend", r
});
! function (n, t) {
    "object" == typeof exports && "object" == typeof module ? module.exports = t() : "function" == typeof define && define.amd ? define("VueI18next", [], t) : "object" == typeof exports ? exports.VueI18next = t() : n.VueI18next = t()
}(this, function () {
    return function (n) {
        function t(r) {
            if (i[r]) return i[r].exports;
            var u = i[r] = {
                i: r,
                l: !1,
                exports: {}
            };
            return n[r].call(u.exports, u, u.exports, t), u.l = !0, u.exports
        }
        var i = {};
        return t.m = n, t.c = i, t.i = function (n) {
            return n
        }, t.d = function (n, i, r) {
            t.o(n, i) || Object.defineProperty(n, i, {
                configurable: !1,
                enumerable: !0,
                get: r
            })
        }, t.n = function (n) {
            var i = n && n.__esModule ? function () {
                return n.default
            } : function () {
                return n
            };
            return t.d(i, "a", i), i
        }, t.o = function (n, t) {
            return Object.prototype.hasOwnProperty.call(n, t)
        }, t.p = "/dist/", t(t.s = 2)
    }([function (n, t, i) {
        "use strict";

        function r(n) {
            r.installed || (r.installed = !0, t.Vue = u = n, u.mixin({
                computed: {
                    $t: function () {
                        var n = this;
                        return function (t, i) {
                            return n.$i18n.t(t, i, n.$i18n.i18nLoadedAt)
                        }
                    }
                },
                beforeCreate: function () {
                    var n = this.$options;
                    n.i18n ? this.$i18n = n.i18n : n.parent && n.parent.$i18n && (this.$i18n = n.parent.$i18n)
                }
            }), u.component(f.default.name, f.default))
        }
        Object.defineProperty(t, "__esModule", {
            value: !0
        });
        t.Vue = void 0;
        t.install = r;
        var e = i(1),
            f = function (n) {
                return n && n.__esModule ? n : {
                    "default": n
                }
            }(e),
            u = t.Vue = void 0
    }, function (n, t) {
        "use strict";
        Object.defineProperty(t, "__esModule", {
            value: !0
        });
        t.default = {
            name: "i18next",
            functional: !0,
            props: {
                tag: {
                    type: String,
                    "default": "span"
                },
                path: {
                    type: String,
                    required: !0
                }
            },
            render: function (n, t) {
                var u = t.props,
                    e = t.data,
                    i = t.children,
                    o = t.parent,
                    r = o.$i18n;
                if (!r) return i;
                var s = u.path,
                    h = r.i18next.services.interpolator.regexp,
                    c = r.t(s, {
                        interpolation: {
                            prefix: "#$?",
                            suffix: "?$#"
                        }
                    }),
                    f = [],
                    l = {};
                return i.forEach(function (n) {
                    n.data && n.data.attrs && n.data.attrs.tkey && (l[n.data.attrs.tkey] = n)
                }), c.split(h).reduce(function (n, t, r) {
                    var u = void 0;
                    if (r % 2 == 0) {
                        if (0 === t.length) return n;
                        u = t
                    } else u = i[parseInt(t, 10)];
                    return n.push(u), n
                }, f), n(u.tag, e, f)
            }
        };
        n.exports = t.default
    }, function (n, t, i) {
        "use strict";

        function f(n, t) {
            if (!(n instanceof t)) throw new TypeError("Cannot call a class as a function");
        }
        Object.defineProperty(t, "__esModule", {
            value: !0
        });
        var e = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (n) {
                return typeof n
            } : function (n) {
                return n && "function" == typeof Symbol && n.constructor === Symbol && n !== Symbol.prototype ? "symbol" : typeof n
            },
            o = function () {
                function n(n, t) {
                    for (var i, r = 0; r < t.length; r++) i = t[r], i.enumerable = i.enumerable || !1, i.configurable = !0, "value" in i && (i.writable = !0), Object.defineProperty(n, i.key, i)
                }
                return function (t, i, r) {
                    return i && n(t.prototype, i), r && n(t, r), t
                }
            }(),
            r = i(0),
            u = function () {
                function n(t) {
                    var i = arguments.length > 1 && void 0 !== arguments[1] ? arguments[1] : {};
                    f(this, n);
                    var r = i.bindI18n,
                        u = void 0 === r ? "languageChanged loaded" : r,
                        e = i.bindStore,
                        o = void 0 === e ? "added removed" : e;
                    this._vm = null;
                    this.i18next = t;
                    this.onI18nChanged = this.onI18nChanged.bind(this);
                    u && this.i18next.on(u, this.onI18nChanged);
                    o && this.i18next.store && this.i18next.store.on(o, this.onI18nChanged);
                    this.resetVM({
                        i18nLoadedAt: new Date
                    })
                }
                return o(n, [{
                    key: "resetVM",
                    value: function (n) {
                        var t = this._vm,
                            i = r.Vue.config.silent;
                        r.Vue.config.silent = !0;
                        this._vm = new r.Vue({
                            data: n
                        });
                        r.Vue.config.silent = i;
                        t && r.Vue.nextTick(function () {
                            return t.$destroy()
                        })
                    }
                }, {
                    key: "t",
                    value: function (n, t) {
                        return this.i18next.t(n, t)
                    }
                }, {
                    key: "onI18nChanged",
                    value: function () {
                        this.i18nLoadedAt = new Date
                    }
                }, {
                    key: "i18nLoadedAt",
                    get: function () {
                        return this._vm.$data.i18nLoadedAt
                    },
                    set: function (n) {
                        this._vm.$set(this._vm, "i18nLoadedAt", n)
                    }
                }]), n
            }();
        t.default = u;
        u.install = r.install;
        u.version = "0.4.0";
        ("undefined" == typeof window ? "undefined" : e(window)) && window.Vue && window.Vue.use(u);
        n.exports = t.default
    }])
});
/*!
 * jQuery Pretty Dropdowns Plugin v4.11.0 by T. H. Doan (http://thdoan.github.io/pretty-dropdowns/)
 *
 * jQuery Pretty Dropdowns by T. H. Doan is licensed under the MIT License.
 * Read a copy of the license in the LICENSE file or at
 * http://choosealicense.com/licenses/mit
 */
(function (n) {
    n.fn.prettyDropdown = function (t) {
        t = n.extend({
            classic: !1,
            customClass: "arrow",
            height: 50,
            hoverIntent: 200,
            multiDelimiter: "; ",
            multiVerbosity: 99,
            selectedMarker: "&#10003;",
            reverse: !1,
            afterLoad: function () {}
        }, t);
        t.selectedMarker = '<span aria-hidden="true" class="checked"> ' + t.selectedMarker + "<\/span>";
        (isNaN(t.height) || t.height < 8) && (t.height = 8);
        (isNaN(t.hoverIntent) || t.hoverIntent < 0) && (t.hoverIntent = 200);
        isNaN(t.multiVerbosity) && (t.multiVerbosity = 99);
        var p = "None selected",
            w = "Selected: ",
            b = " selected",
            r, k = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", , , , , , , , "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"],
            c, u, f, s, h, a = function (i) {
                var u = n(i),
                    k = i.size,
                    nt = i.name || i.id || "",
                    a, p, r, g, it, b;
                if (!u.data("loaded")) {
                    u.data("size", k).removeAttr("size");
                    u.css("visibility", "hidden").outerHeight(t.height);
                    h = +new Date;
                    i.id && (p = n("label[for=" + i.id + "]"), p.length && (p.attr("id") && !/^menu\d{13,}$/.test(p.attr("id")) ? a = p.attr("id") : p.attr("id", a = "menu" + h)));
                    c = 0;
                    var s = n("optgroup, option", u),
                        tt = s.filter(":selected"),
                        w = i.multiple,
                        f = "<ul" + (i.disabled ? "" : ' tabindex="0"') + ' role="listbox"' + (i.title ? ' title="' + i.title + '" aria-label="' + i.title + '"' : "") + (a ? ' aria-labelledby="' + a + '"' : "") + ' aria-activedescendant="item' + h + '-1" aria-expanded="false" style="max-height:' + (t.height - 2) + "px;margin:" + u.css("margin-top") + " " + u.css("margin-right") + " " + u.css("margin-bottom") + " " + u.css("margin-left") + ';">';
                    w ? (f += e(null, "selected"), s.each(function () {
                        f += this.selected ? e(this, "", !0) : e(this)
                    })) : t.classic ? s.each(function () {
                        f += e(this)
                    }) : (f += e(tt[0], "selected"), s.filter(":not(:selected)").each(function () {
                        f += e(this)
                    }));
                    f += "<\/ul>";
                    u.wrap("<div " + (nt ? 'id="prettydropdown-' + nt + '" ' : "") + 'class="prettydropdown ' + (t.classic ? "classic " : "") + (i.disabled ? "disabled " : "") + (w ? "multiple " : "") + t.customClass + ' loading"' + (w || k > 1 ? ' style="height:' + t.height + 'px;"' : "") + "><\/div>").before(f).data("loaded", !0);
                    r = u.parent().children("ul");
                    g = r.outerWidth(!0);
                    s = r.children();
                    w ? y(r) : t.classic && n('[data-value="' + tt.val() + '"]', r).addClass("selected").append(t.selectedMarker);
                    r.width() <= 0 && (b = r.parent().clone().css({
                        position: "absolute",
                        top: "-100%"
                    }), n("body").append(b), g = b.children("ul").outerWidth(!0), n("li", b).width(g), it = b.children("ul").outerWidth(!0), b.remove());
                    s.width(g).css("width", s.css("width")).click(function () {
                        var i = n(this),
                            f = r.children(".selected"),
                            a;
                        if (!r.parent().hasClass("disabled"))
                            if (!r.hasClass("active") || i.hasClass("disabled") || i.hasClass("label") || i.data("value") === f.data("value") || (w ? (i.children("span.checked").length ? i.children("span.checked").remove() : i.append(t.selectedMarker), r.children(":not(.selected)").each(function (t) {
                                    n("optgroup, option", u).eq(t).prop("selected", n(this).children("span.checked").length > 0)
                                }), y(r)) : (f.removeClass("selected").children("span.checked").remove(), i.addClass("selected").append(t.selectedMarker), t.classic || r.prepend(i), r.removeClass("reverse").attr("aria-activedescendant", i.attr("id")), f.data("group") && !t.classic && r.children(".label").filter(function () {
                                    return n(this).text() === f.data("group")
                                }).after(f), n("optgroup, option", u).filter(function () {
                                    return this.value == i.data("value") || this.text === i.contents().filter(function () {
                                        return this.nodeType === 3
                                    }).text()
                                }).prop("selected", !0)), u.trigger("change")), (i.hasClass("selected") || !w) && (r.toggleClass("active"), r.attr("aria-expanded", r.hasClass("active"))), r.hasClass("active")) {
                                n(".prettydropdown > ul.active").length > 1 && o(n(".prettydropdown > ul.active").not(r)[0]);
                                var l = window.innerHeight,
                                    e, s = r.offset().top,
                                    h = document.body.scrollTop,
                                    c = r.outerHeight();
                                k && (e = k * (t.height - 2), e < c - 2 && (c = e + 2));
                                a = s - h + c;
                                (a > l || t.reverse) && (s - h > l - (s - h + t.height) || t.reverse ? (r.addClass("reverse"), t.classic || r.append(f), s - h + t.height < c && (r.outerHeight(s - h + t.height), r.scrollTop(c))) : r.height(r.height() - (a - l)));
                                e && e < r.height() && r.css("height", e + "px");
                                t.classic && r.scrollTop(f.index() * (t.height - 2))
                            } else r.data("clicked", !0), o(r[0])
                    });
                    r.on({
                        focusin: function () {
                            n(window).off("keydown", l).on("keydown", l)
                        },
                        focusout: function () {
                            n(window).off("keydown", l)
                        },
                        mouseenter: function () {
                            r.data("hover", !0)
                        },
                        mouseleave: o,
                        mousemove: d
                    });
                    a && n("#" + a).off("click", v).click(v);
                    r.parent().width(it || r.outerWidth(!0)).removeClass("loading");
                    t.afterLoad()
                }
            },
            v = function (t) {
                n("ul[aria-labelledby=" + t.target.id + "]").focus()
            },
            l = function (e) {
                var c = n(".prettydropdown > ul.active, .prettydropdown > ul:focus"),
                    a, b, v;
                if (c.length) {
                    if (e.which === 9) {
                        o(c[0]);
                        return
                    }
                    e.preventDefault();
                    e.stopPropagation();
                    var h = c.children(),
                        l = c.hasClass("active"),
                        p = c.height() / (t.height - 2),
                        w = p % 1 < .5 ? Math.floor(p) : Math.ceil(p),
                        y;
                    u = Math.max(0, c.children(".hover").index());
                    f = h.length - 1;
                    r = h.eq(u);
                    c.data("lastKeypress", +new Date);
                    switch (e.which) {
                        case 13:
                            l || (r = h.filter(".selected"), i(r, 1));
                            r.click();
                            break;
                        case 27:
                            l && o(c[0]);
                            break;
                        case 32:
                            l ? y = " " : (r = h.filter(".selected"), i(r, 1), r.click());
                            break;
                        case 33:
                            l && (i(r, 0), i(h.eq(Math.max(u - w - 1, 0)), 1));
                            break;
                        case 34:
                            l && (i(r, 0), i(h.eq(Math.min(u + w - 1, f)), 1));
                            break;
                        case 35:
                            l && (i(r, 0), i(h.eq(f), 1));
                            break;
                        case 36:
                            l && (i(r, 0), i(h.eq(0), 1));
                            break;
                        case 38:
                            l && (i(r, 0), i(u ? h.eq(u - 1) : h.eq(f), 1));
                            break;
                        case 40:
                            l && (i(r, 0), i(u === f ? h.eq(0) : h.eq(u + 1), 1));
                            break;
                        default:
                            l && (y = k[e.which - 48])
                    }
                    if (y && (clearTimeout(s), c.data("keysPressed", c.data("keysPressed") === undefined ? y : c.data("keysPressed") + y), s = setTimeout(function () {
                            c.removeData("keysPressed")
                        }, 300), a = [], b = r.index(), h.each(function (t) {
                            n(this).text().toLowerCase().indexOf(c.data("keysPressed")) === 0 && a.push(t)
                        }), a.length))
                        for (v = 0; v < a.length; ++v) {
                            if (a[v] > b) {
                                i(h, 0);
                                i(h.eq(a[v]), 1);
                                break
                            }
                            v === a.length - 1 && (i(h, 0), i(h.eq(a[0]), 1))
                        }
                }
            },
            d = function (t) {
                var r = n(t.currentTarget);
                t.target.nodeName !== "LI" || !r.hasClass("active") || new Date - r.data("lastKeypress") < 200 || (i(r.children(), 0, 1), i(n(t.target), 1, 1))
            },
            e = function (i, r, u) {
                var e = "",
                    o = "",
                    f;
                if (r = r || "", i) {
                    switch (i.nodeName) {
                        case "OPTION":
                            i.parentNode.nodeName === "OPTGROUP" && (e = i.parentNode.getAttribute("label"));
                            o = (i.getAttribute("data-prefix") || "") + i.text + (i.getAttribute("data-suffix") || "");
                            break;
                        case "OPTGROUP":
                            r += " label";
                            o = i.getAttribute("label")
                    }(i.disabled || e && i.parentNode.disabled) && (r += " disabled");
                    f = i.title;
                    e && !f && (f = i.parentNode.title)
                }
                return ++c, '<li id="item' + h + "-" + c + '"' + (e ? ' data-group="' + e + '"' : "") + (i && i.value ? ' data-value="' + i.value + '"' : "") + (i && i.nodeName === "OPTION" ? ' role="option"' : "") + (f ? ' title="' + f + '" aria-label="' + f + '"' : "") + (r ? ' class="' + n.trim(r) + '"' : "") + (t.height !== 50 ? ' style="height:' + (t.height - 2) + "px;line-height:" + (t.height - 4) + 'px;"' : "") + ">" + o + (u || r === "selected" ? t.selectedMarker : "") + "<\/li>"
            },
            o = function (i) {
                var r = n(i.currentTarget || i);
                i.type !== "mouseleave" || r.hasClass("active") || r.data("clicked") || (r = n(".prettydropdown > ul.active"));
                r.data("hover", !1);
                clearTimeout(s);
                s = setTimeout(function () {
                    r.data("hover") || (r.hasClass("reverse") && !t.classic && r.prepend(r.children(":last-child")), r.removeClass("active reverse").removeData("clicked").attr("aria-expanded", "false").css("height", ""), r.children().removeClass("hover nohover"))
                }, i.type === "mouseleave" && !r.data("clicked") ? t.hoverIntent : 0)
            },
            i = function (n, i, u) {
                if (i) {
                    if (n.removeClass("nohover").addClass("hover"), n.length === 1 && r && !u) {
                        var e = n.parent(),
                            s = e.outerHeight(),
                            o = n.offset().top - e.offset().top - 1;
                        n.index() === 0 ? e.scrollTop(0) : n.index() === f ? e.scrollTop(e.children().length * t.height) : o + t.height > s ? e.scrollTop(e.scrollTop() + t.height + o - s) : o < 0 && e.scrollTop(e.scrollTop() + o)
                    }
                } else n.removeClass("hover").addClass("nohover")
            },
            y = function (i) {
                var r = i.parent().children("select"),
                    u = n("option", r).map(function () {
                        if (this.selected) return this.text
                    }).get(),
                    f, e;
                f = t.multiVerbosity >= u.length ? u.join(t.multiDelimiter) || p : u.length + "/" + n("option", r).length + b;
                f ? (e = (r.attr("title") ? r.attr("title") : "") + (u.length ? "\n" + w + u.join(t.multiDelimiter) : ""), i.children(".selected").text(f), i.attr({
                    title: e,
                    "aria-label": e
                })) : (i.children(".selected").empty(), i.attr({
                    title: r.attr("title"),
                    "aria-label": r.attr("title")
                }))
            };
        return this.refresh = function () {
            return this.each(function () {
                var t = n(this);
                t.prevAll("ul").remove();
                t.unwrap().data("loaded", !1);
                this.size = t.data("size");
                a(this)
            })
        }, this.each(function () {
            a(this)
        })
    }
})(jQuery);
/*! vex.combined.js: vex 4.0.1, vex-dialog 1.0.7 */
! function (n) {
    if ("object" == typeof exports && "undefined" != typeof module) module.exports = n();
    else if ("function" == typeof define && define.amd) define([], n);
    else {
        var t;
        t = "undefined" != typeof window ? window : "undefined" != typeof global ? global : "undefined" != typeof self ? self : this;
        t.vex = n()
    }
}(function () {
    var n;
    return function t(n, i, r) {
        function u(f, o) {
            var h, c, s;
            if (!i[f]) {
                if (!n[f]) {
                    if (h = "function" == typeof require && require, !o && h) return h(f, !0);
                    if (e) return e(f, !0);
                    c = new Error("Cannot find module '" + f + "'");
                    throw c.code = "MODULE_NOT_FOUND", c;
                }
                s = i[f] = {
                    exports: {}
                };
                n[f][0].call(s.exports, function (t) {
                    var i = n[f][1][t];
                    return u(i ? i : t)
                }, s, s.exports, t, n, i, r)
            }
            return i[f].exports
        }
        for (var e = "function" == typeof require && require, f = 0; f < r.length; f++) u(r[f]);
        return u
    }({
        1: [function () {
            "document" in window.self && ("classList" in document.createElement("_") && (!document.createElementNS || "classList" in document.createElementNS("http://www.w3.org/2000/svg", "g")) ? ! function () {
                "use strict";
                var n = document.createElement("_"),
                    t, i;
                (n.classList.add("c1", "c2"), n.classList.contains("c2")) || (t = function (n) {
                    var t = DOMTokenList.prototype[n];
                    DOMTokenList.prototype[n] = function (n) {
                        for (var r = arguments.length, i = 0; i < r; i++) n = arguments[i], t.call(this, n)
                    }
                }, t("add"), t("remove"));
                (n.classList.toggle("c3", !1), n.classList.contains("c3")) && (i = DOMTokenList.prototype.toggle, DOMTokenList.prototype.toggle = function (n, t) {
                    return 1 in arguments && !this.contains(n) == !t ? t : i.call(this, n)
                });
                n = null
            }() : ! function (n) {
                "use strict";
                var f;
                if ("Element" in n) {
                    var e = "classList",
                        t = "prototype",
                        o = n.Element[t],
                        r = Object,
                        l = String[t].trim || function () {
                            return this.replace(/^\s+|\s+$/g, "")
                        },
                        a = Array[t].indexOf || function (n) {
                            for (var t = 0, i = this.length; t < i; t++)
                                if (t in this && this[t] === n) return t;
                            return -1
                        },
                        s = function (n, t) {
                            this.name = n;
                            this.code = DOMException[n];
                            this.message = t
                        },
                        u = function (n, t) {
                            if ("" === t) throw new s("SYNTAX_ERR", "An invalid or illegal string was specified");
                            if (/\s/.test(t)) throw new s("INVALID_CHARACTER_ERR", "String contains an invalid character");
                            return a.call(n, t)
                        },
                        h = function (n) {
                            for (var i = l.call(n.getAttribute("class") || ""), r = i ? i.split(/\s+/) : [], t = 0, u = r.length; t < u; t++) this.push(r[t]);
                            this._updateClassName = function () {
                                n.setAttribute("class", this.toString())
                            }
                        },
                        i = h[t] = [],
                        c = function () {
                            return new h(this)
                        };
                    if (s[t] = Error[t], i.item = function (n) {
                            return this[n] || null
                        }, i.contains = function (n) {
                            return n += "", u(this, n) !== -1
                        }, i.add = function () {
                            var n, t = arguments,
                                i = 0,
                                f = t.length,
                                r = !1;
                            do n = t[i] + "", u(this, n) === -1 && (this.push(n), r = !0); while (++i < f);
                            r && this._updateClassName()
                        }, i.remove = function () {
                            var t, n, i = arguments,
                                r = 0,
                                e = i.length,
                                f = !1;
                            do
                                for (t = i[r] + "", n = u(this, t); n !== -1;) this.splice(n, 1), f = !0, n = u(this, t); while (++r < e);
                            f && this._updateClassName()
                        }, i.toggle = function (n, t) {
                            n += "";
                            var i = this.contains(n),
                                r = i ? t !== !0 && "remove" : t !== !1 && "add";
                            return r && this[r](n), t === !0 || t === !1 ? t : !i
                        }, i.toString = function () {
                            return this.join(" ")
                        }, r.defineProperty) {
                        f = {
                            get: c,
                            enumerable: !0,
                            configurable: !0
                        };
                        try {
                            r.defineProperty(o, e, f)
                        } catch (v) {
                            v.number === -2146823252 && (f.enumerable = !1, r.defineProperty(o, e, f))
                        }
                    } else r[t].__defineGetter__ && o.__defineGetter__(e, c)
                }
            }(window.self))
        }, {}],
        2: [function (n, t) {
            function f(n, t) {
                var u, f, r, o;
                if ("string" != typeof n) throw new TypeError("String expected");
                if (t || (t = document), u = /<([\w:]+)/.exec(n), !u) return t.createTextNode(n);
                if (n = n.replace(/^\s+|\s+$/g, ""), f = u[1], "body" == f) return r = t.createElement("html"), r.innerHTML = n, r.removeChild(r.lastChild);
                var e = i[f] || i._default,
                    s = e[0],
                    h = e[1],
                    c = e[2],
                    r = t.createElement("div");
                for (r.innerHTML = h + n + c; s--;) r = r.lastChild;
                if (r.firstChild == r.lastChild) return r.removeChild(r.firstChild);
                for (o = t.createDocumentFragment(); r.firstChild;) o.appendChild(r.removeChild(r.firstChild));
                return o
            }
            var r, u, i;
            t.exports = f;
            u = !1;
            "undefined" != typeof document && (r = document.createElement("div"), r.innerHTML = '  <link/><table><\/table><a href="/a">a<\/a><input type="checkbox"/>', u = !r.getElementsByTagName("link").length, r = void 0);
            i = {
                legend: [1, "<fieldset>", "<\/fieldset>"],
                tr: [2, "<table><tbody>", "<\/tbody><\/table>"],
                col: [2, "<table><tbody><\/tbody><colgroup>", "<\/colgroup><\/table>"],
                _default: u ? [1, "X<div>", "<\/div>"] : [0, "", ""]
            };
            i.td = i.th = [3, "<table><tbody><tr>", "<\/tr><\/tbody><\/table>"];
            i.option = i.optgroup = [1, '<select multiple="multiple">', "<\/select>"];
            i.thead = i.tbody = i.colgroup = i.caption = i.tfoot = [1, "<table>", "<\/table>"];
            i.polyline = i.ellipse = i.polygon = i.circle = i.text = i.line = i.path = i.rect = i.g = [1, '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">', "<\/svg>"]
        }, {}],
        3: [function (n, t) {
            "use strict";

            function i(n) {
                var u, i, t, r, e;
                if (void 0 === n || null === n) throw new TypeError("Cannot convert first argument to object");
                for (u = Object(n), i = 1; i < arguments.length; i++)
                    if (t = arguments[i], void 0 !== t && null !== t)
                        for (var o = Object.keys(Object(t)), f = 0, s = o.length; f < s; f++) r = o[f], e = Object.getOwnPropertyDescriptor(t, r), void 0 !== e && e.enumerable && (u[r] = t[r]);
                return u
            }

            function r() {
                Object.assign || Object.defineProperty(Object, "assign", {
                    enumerable: !1,
                    configurable: !0,
                    writable: !0,
                    value: i
                })
            }
            t.exports = {
                assign: i,
                polyfill: r
            }
        }, {}],
        4: [function (n, t) {
            function u(n, t) {
                var i, f, u;
                "object" != typeof t ? t = {
                    hash: !!t
                } : void 0 === t.hash && (t.hash = !0);
                for (var r = t.hash ? {} : "", c = t.serializer || (t.hash ? e : o), p = n && n.elements ? n.elements : [], l = Object.create(null), v = 0; v < p.length; ++v)
                    if (i = p[v], (t.disabled || !i.disabled) && i.name && h.test(i.nodeName) && !s.test(i.type)) {
                        if (u = i.name, f = i.value, "checkbox" !== i.type && "radio" !== i.type || i.checked || (f = void 0), t.empty) {
                            if ("checkbox" !== i.type || i.checked || (f = ""), "radio" === i.type && (l[i.name] || i.checked ? i.checked && (l[i.name] = !0) : l[i.name] = !1), !f && "radio" == i.type) continue
                        } else if (!f) continue;
                        if ("select-multiple" !== i.type) r = c(r, u, f);
                        else {
                            f = [];
                            for (var w = i.options, b = !1, y = 0; y < w.length; ++y) {
                                var a = w[y],
                                    k = t.empty && !a.value,
                                    d = a.value || k;
                                a.selected && d && (b = !0, r = t.hash && "[]" !== u.slice(u.length - 2) ? c(r, u + "[]", a.value) : c(r, u, a.value))
                            }!b && t.empty && (r = c(r, u, ""))
                        }
                    } if (t.empty)
                    for (u in l) l[u] || (r = c(r, u, ""));
                return r
            }

            function f(n) {
                var i = [],
                    u = new RegExp(r),
                    t = /^([^\[\]]*)/.exec(n);
                for (t[1] && i.push(t[1]); null !== (t = u.exec(n));) i.push(t[1]);
                return i
            }

            function i(n, t, r) {
                var u, o, f, e;
                return 0 === t.length ? r : (u = t.shift(), o = u.match(/^\[(.+?)\]$/), "[]" === u) ? (n = n || [], Array.isArray(n) ? n.push(i(null, t, r)) : (n._values = n._values || [], n._values.push(i(null, t, r))), n) : (o ? (f = o[1], e = +f, isNaN(e) ? (n = n || {}, n[f] = i(n[f], t, r)) : (n = n || [], n[e] = i(n[e], t, r))) : n[u] = i(n[u], t, r), n)
            }

            function e(n, t, u) {
                var s = t.match(r),
                    o, e;
                return s ? (o = f(t), i(n, o, u)) : (e = n[t], e ? (Array.isArray(e) || (n[t] = [e]), n[t].push(u)) : n[t] = u), n
            }

            function o(n, t, i) {
                return i = i.replace(/(\r)?\n/g, "\r\n"), i = encodeURIComponent(i), i = i.replace(/%20/g, "+"), n + (n ? "&" : "") + encodeURIComponent(t) + "=" + i
            }
            var s = /^(?:submit|button|image|reset|file)$/i,
                h = /^(?:input|select|textarea|keygen)/i,
                r = /(\[[^\[\]]*\])/g;
            t.exports = u
        }, {}],
        5: [function (t, i, r) {
            (function (u) {
                ! function (t) {
                    if ("object" == typeof r && "undefined" != typeof i) i.exports = t();
                    else if ("function" == typeof n && n.amd) n([], t);
                    else {
                        var f;
                        f = "undefined" != typeof window ? window : "undefined" != typeof u ? u : "undefined" != typeof self ? self : this;
                        f.vexDialog = t()
                    }
                }(function () {
                    return function n(i, r, u) {
                        function f(e, s) {
                            var c, l, h;
                            if (!r[e]) {
                                if (!i[e]) {
                                    if (c = "function" == typeof t && t, !s && c) return c(e, !0);
                                    if (o) return o(e, !0);
                                    l = new Error("Cannot find module '" + e + "'");
                                    throw l.code = "MODULE_NOT_FOUND", l;
                                }
                                h = r[e] = {
                                    exports: {}
                                };
                                i[e][0].call(h.exports, function (n) {
                                    var t = i[e][1][n];
                                    return f(t ? t : n)
                                }, h, h.exports, n, i, r, u)
                            }
                            return r[e].exports
                        }
                        for (var o = "function" == typeof t && t, e = 0; e < u.length; e++) f(u[e]);
                        return f
                    }({
                        1: [function (n, t) {
                            function f(n, t) {
                                var u, f, r, o;
                                if ("string" != typeof n) throw new TypeError("String expected");
                                if (t || (t = document), u = /<([\w:]+)/.exec(n), !u) return t.createTextNode(n);
                                if (n = n.replace(/^\s+|\s+$/g, ""), f = u[1], "body" == f) return r = t.createElement("html"), r.innerHTML = n, r.removeChild(r.lastChild);
                                var e = i[f] || i._default,
                                    s = e[0],
                                    h = e[1],
                                    c = e[2],
                                    r = t.createElement("div");
                                for (r.innerHTML = h + n + c; s--;) r = r.lastChild;
                                if (r.firstChild == r.lastChild) return r.removeChild(r.firstChild);
                                for (o = t.createDocumentFragment(); r.firstChild;) o.appendChild(r.removeChild(r.firstChild));
                                return o
                            }
                            var r, u, i;
                            t.exports = f;
                            u = !1;
                            "undefined" != typeof document && (r = document.createElement("div"), r.innerHTML = '  <link/><table><\/table><a href="/a">a<\/a><input type="checkbox"/>', u = !r.getElementsByTagName("link").length, r = void 0);
                            i = {
                                legend: [1, "<fieldset>", "<\/fieldset>"],
                                tr: [2, "<table><tbody>", "<\/tbody><\/table>"],
                                col: [2, "<table><tbody><\/tbody><colgroup>", "<\/colgroup><\/table>"],
                                _default: u ? [1, "X<div>", "<\/div>"] : [0, "", ""]
                            };
                            i.td = i.th = [3, "<table><tbody><tr>", "<\/tr><\/tbody><\/table>"];
                            i.option = i.optgroup = [1, '<select multiple="multiple">', "<\/select>"];
                            i.thead = i.tbody = i.colgroup = i.caption = i.tfoot = [1, "<table>", "<\/table>"];
                            i.polyline = i.ellipse = i.polygon = i.circle = i.text = i.line = i.path = i.rect = i.g = [1, '<svg xmlns="http://www.w3.org/2000/svg" version="1.1">', "<\/svg>"]
                        }, {}],
                        2: [function (n, t) {
                            function u(n, t) {
                                var i, f, u;
                                "object" != typeof t ? t = {
                                    hash: !!t
                                } : void 0 === t.hash && (t.hash = !0);
                                for (var r = t.hash ? {} : "", c = t.serializer || (t.hash ? e : o), p = n && n.elements ? n.elements : [], l = Object.create(null), v = 0; v < p.length; ++v)
                                    if (i = p[v], (t.disabled || !i.disabled) && i.name && h.test(i.nodeName) && !s.test(i.type)) {
                                        if (u = i.name, f = i.value, "checkbox" !== i.type && "radio" !== i.type || i.checked || (f = void 0), t.empty) {
                                            if ("checkbox" !== i.type || i.checked || (f = ""), "radio" === i.type && (l[i.name] || i.checked ? i.checked && (l[i.name] = !0) : l[i.name] = !1), !f && "radio" == i.type) continue
                                        } else if (!f) continue;
                                        if ("select-multiple" !== i.type) r = c(r, u, f);
                                        else {
                                            f = [];
                                            for (var w = i.options, b = !1, y = 0; y < w.length; ++y) {
                                                var a = w[y],
                                                    k = t.empty && !a.value,
                                                    d = a.value || k;
                                                a.selected && d && (b = !0, r = t.hash && "[]" !== u.slice(u.length - 2) ? c(r, u + "[]", a.value) : c(r, u, a.value))
                                            }!b && t.empty && (r = c(r, u, ""))
                                        }
                                    } if (t.empty)
                                    for (u in l) l[u] || (r = c(r, u, ""));
                                return r
                            }

                            function f(n) {
                                var i = [],
                                    u = new RegExp(r),
                                    t = /^([^\[\]]*)/.exec(n);
                                for (t[1] && i.push(t[1]); null !== (t = u.exec(n));) i.push(t[1]);
                                return i
                            }

                            function i(n, t, r) {
                                var u, o, f, e;
                                return 0 === t.length ? r : (u = t.shift(), o = u.match(/^\[(.+?)\]$/), "[]" === u) ? (n = n || [], Array.isArray(n) ? n.push(i(null, t, r)) : (n._values = n._values || [], n._values.push(i(null, t, r))), n) : (o ? (f = o[1], e = +f, isNaN(e) ? (n = n || {}, n[f] = i(n[f], t, r)) : (n = n || [], n[e] = i(n[e], t, r))) : n[u] = i(n[u], t, r), n)
                            }

                            function e(n, t, u) {
                                var s = t.match(r),
                                    o, e;
                                return s ? (o = f(t), i(n, o, u)) : (e = n[t], e ? (Array.isArray(e) || (n[t] = [e]), n[t].push(u)) : n[t] = u), n
                            }

                            function o(n, t, i) {
                                return i = i.replace(/(\r)?\n/g, "\r\n"), i = encodeURIComponent(i), i = i.replace(/%20/g, "+"), n + (n ? "&" : "") + encodeURIComponent(t) + "=" + i
                            }
                            var s = /^(?:submit|button|image|reset|file)$/i,
                                h = /^(?:input|select|textarea|keygen)/i,
                                r = /(\[[^\[\]]*\])/g;
                            t.exports = u
                        }, {}],
                        3: [function (n, t) {
                            var i = n("domify"),
                                r = n("form-serialize"),
                                u = function (n) {
                                    var t = document.createElement("form"),
                                        r, u;
                                    return t.classList.add("vex-dialog-form"), r = document.createElement("div"), r.classList.add("vex-dialog-message"), r.appendChild(n.message instanceof window.Node ? n.message : i(n.message)), u = document.createElement("div"), u.classList.add("vex-dialog-input"), u.appendChild(n.input instanceof window.Node ? n.input : i(n.input)), t.appendChild(r), t.appendChild(u), t
                                },
                                f = function (n) {
                                    var u = document.createElement("div"),
                                        i, r, t;
                                    for (u.classList.add("vex-dialog-buttons"), i = 0; i < n.length; i++) r = n[i], t = document.createElement("button"), t.type = r.type, t.textContent = r.text, t.className = r.className, t.classList.add("vex-dialog-button"), 0 === i ? t.classList.add("vex-first") : i === n.length - 1 && t.classList.add("vex-last"),
                                        function (n) {
                                            t.addEventListener("click", function (t) {
                                                n.click && n.click.call(this, t)
                                            }.bind(this))
                                        }.bind(this)(r), u.appendChild(t);
                                    return u
                                },
                                e = function (n) {
                                    var t = {
                                        name: "dialog",
                                        open: function (t) {
                                            var i = Object.assign({}, this.defaultOptions, t),
                                                o;
                                            i.unsafeMessage && !i.message ? i.message = i.unsafeMessage : i.message && (i.message = n._escapeHtml(i.message));
                                            var e = i.unsafeContent = u(i),
                                                r = n.open(i),
                                                s = i.beforeClose && i.beforeClose.bind(r);
                                            return (r.options.beforeClose = function () {
                                                var n = !s || s();
                                                return n && i.callback(this.value || !1), n
                                            }.bind(r), e.appendChild(f.call(r, i.buttons)), r.form = e, e.addEventListener("submit", i.onSubmit.bind(r)), i.focusFirstInput) && (o = r.contentEl.querySelector("button, input, select, textarea"), o && o.focus()), r
                                        },
                                        alert: function (n) {
                                            return "string" == typeof n && (n = {
                                                message: n
                                            }), n = Object.assign({}, this.defaultOptions, this.defaultAlertOptions, n), this.open(n)
                                        },
                                        confirm: function (n) {
                                            if ("object" != typeof n || "function" != typeof n.callback) throw new Error("dialog.confirm(options) requires options.callback.");
                                            return n = Object.assign({}, this.defaultOptions, this.defaultConfirmOptions, n), this.open(n)
                                        },
                                        prompt: function (t) {
                                            var i, r, u;
                                            if ("object" != typeof t || "function" != typeof t.callback) throw new Error("dialog.prompt(options) requires options.callback.");
                                            return i = Object.assign({}, this.defaultOptions, this.defaultPromptOptions), r = {
                                                unsafeMessage: '<label for="vex">' + n._escapeHtml(t.label || i.label) + "<\/label>",
                                                input: '<input name="vex" type="text" class="vex-dialog-prompt-input" placeholder="' + n._escapeHtml(t.placeholder || i.placeholder) + '" value="' + n._escapeHtml(t.value || i.value) + '" />'
                                            }, t = Object.assign(i, r, t), u = t.callback, t.callback = function (n) {
                                                if ("object" == typeof n) {
                                                    var t = Object.keys(n);
                                                    n = t.length ? n[t[0]] : ""
                                                }
                                                u(n)
                                            }, this.open(t)
                                        }
                                    };
                                    return t.buttons = {
                                        YES: {
                                            text: "OK",
                                            type: "submit",
                                            className: "vex-dialog-button-primary",
                                            click: function () {
                                                this.value = !0
                                            }
                                        },
                                        NO: {
                                            text: "Cancel",
                                            type: "button",
                                            className: "vex-dialog-button-secondary",
                                            click: function () {
                                                this.value = !1;
                                                this.close()
                                            }
                                        }
                                    }, t.defaultOptions = {
                                        callback: function () {},
                                        afterOpen: function () {},
                                        message: "",
                                        input: "",
                                        buttons: [t.buttons.YES, t.buttons.NO],
                                        showCloseButton: !1,
                                        onSubmit: function (n) {
                                            return n.preventDefault(), this.options.input && (this.value = r(this.form, {
                                                hash: !0
                                            })), this.close()
                                        },
                                        focusFirstInput: !0
                                    }, t.defaultAlertOptions = {
                                        buttons: [t.buttons.YES]
                                    }, t.defaultPromptOptions = {
                                        label: "Prompt:",
                                        placeholder: "",
                                        value: ""
                                    }, t.defaultConfirmOptions = {}, t
                                };
                            t.exports = e
                        }, {
                            domify: 1,
                            "form-serialize": 2
                        }]
                    }, {}, [3])(3)
                })
            }).call(this, "undefined" != typeof global ? global : "undefined" != typeof self ? self : "undefined" != typeof window ? window : {})
        }, {
            domify: 2,
            "form-serialize": 4
        }],
        6: [function (n, t) {
            var i = n("./vex");
            i.registerPlugin(n("vex-dialog"));
            t.exports = i
        }, {
            "./vex": 7,
            "vex-dialog": 5
        }],
        7: [function (n, t) {
            n("classlist-polyfill");
            n("es6-object-assign").polyfill();
            var h = n("domify"),
                s = function (n) {
                    if ("undefined" != typeof n) {
                        var t = document.createElement("div");
                        return t.appendChild(document.createTextNode(n)), t.innerHTML
                    }
                    return ""
                },
                e = function (n, t) {
                    var r, i, u;
                    if ("string" == typeof t && 0 !== t.length)
                        for (r = t.split(" "), i = 0; i < r.length; i++) u = r[i], u.length && n.classList.add(u)
                },
                f = function () {
                    var i = document.createElement("div"),
                        n = {
                            WebkitAnimation: "webkitAnimationEnd",
                            MozAnimation: "animationend",
                            OAnimation: "oanimationend",
                            msAnimation: "MSAnimationEnd",
                            animation: "animationend"
                        };
                    for (var t in n)
                        if (void 0 !== i.style[t]) return n[t];
                    return !1
                }(),
                u = {
                    vex: "vex",
                    content: "vex-content",
                    overlay: "vex-overlay",
                    close: "vex-close",
                    closing: "vex-closing",
                    open: "vex-open"
                },
                r = {},
                c = 1,
                o = !1,
                i = {
                    open: function (n) {
                        var p = function (n) {
                                console.warn('The "' + n + '" property is deprecated in vex 3. Use CSS classes and the appropriate "ClassName" options, instead.');
                                console.warn("See http://github.hubspot.com/vex/api/advanced/#options")
                            },
                            t, w, v, y;
                        n.css && p("css");
                        n.overlayCSS && p("overlayCSS");
                        n.contentCSS && p("contentCSS");
                        n.closeCSS && p("closeCSS");
                        t = {};
                        t.id = c++;
                        r[t.id] = t;
                        t.isOpen = !0;
                        t.close = function () {
                            function t(n) {
                                return "none" !== s.getPropertyValue(n + "animation-name") && "0s" !== s.getPropertyValue(n + "animation-duration")
                            }
                            var n, e;
                            if (!this.isOpen) return !0;
                            if ((n = this.options, o && !n.escapeButtonCloses) || (e = function () {
                                    return !n.beforeClose || n.beforeClose.call(this)
                                }.bind(this)(), e === !1)) return !1;
                            this.isOpen = !1;
                            var s = window.getComputedStyle(this.contentEl),
                                c = t("") || t("-webkit-") || t("-moz-") || t("-o-"),
                                i = function h() {
                                    this.rootEl.parentNode && (this.rootEl.removeEventListener(f, h), this.overlayEl.removeEventListener(f, h), delete r[this.id], this.rootEl.parentNode.removeChild(this.rootEl), this.bodyEl.removeChild(this.overlayEl), n.afterClose && n.afterClose.call(this), 0 === Object.keys(r).length && document.body.classList.remove(u.open))
                                }.bind(this);
                            return f && c ? (this.rootEl.addEventListener(f, i), this.overlayEl.addEventListener(f, i), this.rootEl.classList.add(u.closing), this.overlayEl.classList.add(u.closing)) : i(), !0
                        };
                        "string" == typeof n && (n = {
                            content: n
                        });
                        n.unsafeContent && !n.content ? n.content = n.unsafeContent : n.content && (n.content = s(n.content));
                        var l = t.options = Object.assign({}, i.defaultOptions, n),
                            b = t.bodyEl = document.getElementsByTagName("body")[0],
                            a = t.rootEl = document.createElement("div");
                        return a.classList.add(u.vex), e(a, l.className), w = t.overlayEl = document.createElement("div"), w.classList.add(u.overlay), e(w, l.overlayClassName), l.overlayClosesOnClick && a.addEventListener("click", function (n) {
                            n.target === a && t.close()
                        }), b.appendChild(w), v = t.contentEl = document.createElement("div"), (v.classList.add(u.content), e(v, l.contentClassName), v.appendChild(l.content instanceof window.Node ? l.content : h(l.content)), a.appendChild(v), l.showCloseButton) && (y = t.closeEl = document.createElement("div"), y.classList.add(u.close), e(y, l.closeClassName), y.addEventListener("click", t.close.bind(t)), v.appendChild(y)), document.querySelector(l.appendLocation).appendChild(a), l.afterOpen && l.afterOpen.call(t), document.body.classList.add(u.open), t
                    },
                    close: function (n) {
                        var t;
                        if (n.id) t = n.id;
                        else {
                            if ("string" != typeof n) throw new TypeError("close requires a vex object or id string");
                            t = n
                        }
                        return !!r[t] && r[t].close()
                    },
                    closeTop: function () {
                        var n = Object.keys(r);
                        return !!n.length && r[n[n.length - 1]].close()
                    },
                    closeAll: function () {
                        for (var n in r) this.close(n);
                        return !0
                    },
                    getAll: function () {
                        return r
                    },
                    getById: function (n) {
                        return r[n]
                    }
                };
            window.addEventListener("keyup", function (n) {
                27 === n.keyCode && (o = !0, i.closeTop(), o = !1)
            });
            window.addEventListener("popstate", function () {
                i.defaultOptions.closeAllOnPopState && i.closeAll()
            });
            i.defaultOptions = {
                content: "",
                showCloseButton: !0,
                escapeButtonCloses: !0,
                overlayClosesOnClick: !0,
                appendLocation: "body",
                className: "",
                overlayClassName: "",
                contentClassName: "",
                closeClassName: "",
                closeAllOnPopState: !0
            };
            Object.defineProperty(i, "_escapeHtml", {
                configurable: !1,
                enumerable: !1,
                writable: !1,
                value: s
            });
            i.registerPlugin = function (n, t) {
                var r = n(i),
                    u = t || r.name;
                if (i[u]) throw new Error("Plugin " + t + " is already registered.");
                i[u] = r
            };
            t.exports = i
        }, {
            "classlist-polyfill": 1,
            domify: 2,
            "es6-object-assign": 3
        }]
    }, {}, [6])(6)
});
(window.onpopstate = function () {
    var n, i = /\+/g,
        r = /([^&=]+)=?([^&]*)/g,
        t = function (n) {
            return decodeURIComponent(n.replace(i, " "))
        },
        u = window.location.search.substring(1);
    for (urlParams = {}; n = r.exec(u);) urlParams[t(n[1])] = t(n[2])
})();
ChangellyComponent = {
    props: ["storeId", "toCurrency", "toCurrencyDue", "toCurrencyAddress", "merchantId"],
    data: function () {
        return {
            currencies: [],
            isLoading: !0,
            calculatedAmount: 0,
            selectedFromCurrency: "",
            prettyDropdownInstance: null,
            calculateError: !1,
            currenciesError: !1
        }
    },
    computed: {
        url: function () {
            return this.calculatedAmount && this.selectedFromCurrency && !this.isLoading ? "https://changelly.com/widget/v1?auth=email&from=" + this.selectedFromCurrency + "&to=" + this.toCurrency + "&address=" + this.toCurrencyAddress + "&amount=" + this.calculatedAmount + (this.merchantId ? "&merchant_id=" + this.merchantId + "&ref_id=" + this.merchantId : "") : null
        }
    },
    watch: {
        selectedFromCurrency: function (n) {
            n ? this.calculateAmount() : this.calculateAmount = 0
        }
    },
    mounted: function () {
        this.prettyDropdownInstance = initDropdown(this.$refs.changellyCurrenciesDropdown);
        this.loadCurrencies()
    },
    methods: {
        getUrl: function () {
            return window.location.origin + "/changelly/" + this.storeId
        },
        loadCurrencies: function () {
            this.isLoading = !0;
            this.currenciesError = !1;
            $.ajax({
                context: this,
                url: this.getUrl() + "/currencies",
                dataType: "json",
                success: function (n) {
                    for (i = 0; i < n.length; i++) n[i].enabled && n[i].name.toLowerCase() !== this.toCurrency.toLowerCase() && this.currencies.push(n[i]);
                    var t = this;
                    Vue.nextTick(function () {
                        t.prettyDropdownInstance.refresh().on("change", function () {
                            t.onCurrencyChange(t.$refs.changellyCurrenciesDropdown.value)
                        })
                    })
                },
                error: function () {
                    this.currenciesError = !0
                },
                complete: function () {
                    this.isLoading = !1
                }
            })
        },
        calculateAmount: function () {
            this.isLoading = !0;
            this.calculateError = !1;
            $.ajax({
                url: this.getUrl() + "/calculate",
                dataType: "json",
                data: {
                    fromCurrency: this.selectedFromCurrency,
                    toCurrency: this.toCurrency,
                    toCurrencyAmount: this.toCurrencyDue
                },
                context: this,
                success: function (n) {
                    this.calculatedAmount = n
                },
                error: function () {
                    this.calculateError = !0
                },
                complete: function () {
                    this.isLoading = !1
                }
            })
        },
        retry: function (n) {
            n == "loadCurrencies" ? this.loadCurrencies() : n == "calculateAmount" && this.calculateAmount()
        },
        onCurrencyChange: function (n) {
            this.selectedFromCurrency = n;
            this.calculatedAmount = 0
        },
        openDialog: function (n) {
            n && n.preventDefault && n.preventDefault();
            var t = window.open(this.url, "Changelly", "width=600,height=470,toolbar=0,menubar=0,location=0,status=1,scrollbars=1,resizable=0,left=0,top=0");
            t.focus()
        }
    }
};
CoinSwitchComponent = {
    props: ["toCurrency", "toCurrencyDue", "toCurrencyAddress", "merchantId", "autoload", "mode"],
    data: function () {
        return {
            opened: !1
        }
    },
    computed: {
        showInlineIFrame: function () {
            return this.url && this.opened
        },
        url: function () {
            return window.location.origin + "/checkout/coinswitch.html?&toCurrency=" + this.toCurrency + "&toCurrencyAddress=" + this.toCurrencyAddress + "&toCurrencyDue=" + this.toCurrencyDue + "&mode=" + this.mode + (this.merchantId ? "&merchant_id=" + this.merchantId : "")
        }
    },
    methods: {
        openDialog: function (n) {
            if (n && n.preventDefault && n.preventDefault(), this.mode === "inline") this.opened = !0;
            else if (this.mode === "popup") {
                var t = window.open(this.url, "CoinSwitch", "width=360,height=650,toolbar=0,menubar=0,location=0,status=1,scrollbars=1,resizable=0,left=0,top=0");
                t.opener = null;
                t.focus()
            }
        },
        closeDialog: function () {
            this.mode === "inline" && (this.opened = !1)
        },
        onLoadIframe: function (n) {
            $("#prettydropdown-DefaultLang").hide();
            var t = this.closeDialog.bind(this);
            n.currentTarget.contentWindow.addEventListener("message", function (n) {
                n && n.data == "popup-closed" && (t(), $("#prettydropdown-DefaultLang").show())
            })
        }
    },
    mounted: function () {
        this.autoload && this.openDialog()
    }
};
$(document).ready(function () {
    function f() {
        $("#emailAddressView").removeClass("active");
        $("placeholder-refundEmail").html(srvModel.customerEmail);
        $(".modal-dialog").removeClass("enter-purchaser-email");
        $("#scan").addClass("active")
    }

    function h() {
        $(".modal-dialog").addClass("enter-purchaser-email");
        $("#emailAddressForm .action-button").click(function () {
            var n = $("#emailAddressFormInput").val();
            return e(n) ? ($("#emailAddressForm .input-wrapper bp-loading-button .action-button").addClass("loading"), srvModel.customerEmail = n, $.ajax({
                url: window.location.pathname + "/UpdateCustomer?invoiceId=" + srvModel.invoiceId,
                type: "POST",
                data: JSON.stringify({
                    Email: srvModel.customerEmail
                }),
                contentType: "application/json; charset=utf-8"
            }).done(function () {
                f()
            }).fail(function () {}).always(function () {
                $("#emailAddressForm .input-wrapper bp-loading-button .action-button").removeClass("loading")
            })) : $("#emailAddressForm").addClass("ng-touched ng-dirty ng-submitted ng-invalid"), !1
        })
    }

    function e(n) {
        return /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/.test(n)
    }

    function r(n) {
        $(n + "-tab").addClass("active");
        $(n).show();
        $(n).addClass("active")
    }

    function l(n) {
        function i() {
            var h = new Date,
                e = t.getTime() - h.getTime(),
                f = 100 - Math.round(e / n * 100),
                o = checkoutCtrl.srvModel.status,
                s;
            u(e / 1e3);
            f === 75 && (o === "paidPartial" || o === "new") && ($(".timer-row").addClass("expiring-soon"), checkoutCtrl.expiringSoon = !0, r(f));
            f <= 100 && (r(f), s = 300, setTimeout(i, s))
        }

        function r(n) {
            $(".timer-row__progress-bar").css("width", n + "%")
        }

        function u(n) {
            var r = $(".timer-row__time-left"),
                t, i;
            n >= 0 ? (t = parseInt(n / 60, 10), t = t < 10 ? "0" + t : t, i = parseInt(n % 60, 10), i = i < 10 ? "0" + i : i, r.text(t + ":" + i)) : r.text("00:00")
        }
        var t = new Date;
        t.setSeconds(t.getSeconds() + srvModel.expirationSeconds);
        n *= 1e3;
        i()
    }

    function s(n, t, i) {
        var r = $(n),
            u = r.offset();
        return u.top -= t, u.left += r.width() / 2 - i, $(".copyLabelPopup").css(u).addClass("copied"), r.removeClass("copy-cursor").addClass("clipboardCopied"), setTimeout(y, 100), setTimeout(function () {
            r.removeClass("clipboardCopied").addClass("copy-cursor");
            $(".copyLabelPopup").removeClass("copied")
        }, 1e3), n
    }

    function y() {
        window.getSelection ? window.getSelection().removeAllRanges() : document.selection && document.selection.empty()
    }

    var o, n, t, u, c, i, a, v;
    fetchStatus();
    //onDataCallback(srvModel);
    srvModel.expirationSeconds > 0 && (l(srvModel.maxTimeSeconds), srvModel.requiresRefundEmail && !e(srvModel.customerEmail) ? h() : f());
    $(".close-action").on("click", function () {
        $("invoice").fadeOut(300, function () {
            window.parent.postMessage("close", "*")
        })
    });
    c = setInterval(function () {
        fetchStatus()
    }, 2e3);
    if (window.parent.postMessage("loaded", "*"), jQuery("invoice").fadeOut(0), jQuery("invoice").fadeIn(300), $("#emailAddressFormInput").change(function () {
            $("#emailAddressForm").hasClass("ng-submitted") && $("#emailAddressForm").removeClass("ng-submitted")
        }), $("#scan-tab").click(function () {
            resetTabsSlider();
            r("#scan")
        }), $("#copy-tab").click(function () {
            resetTabsSlider();
            r("#copy");
            $("#tabsSlider").addClass("slide-copy")
        }), $("#altcoins-tab").click(function () {
            resetTabsSlider();
            r("#altcoins");
            $("#tabsSlider").addClass("slide-altcoins")
        }), o = "WebSocket" in window && window.WebSocket.CLOSING === 2, o) {
        n = window.location;
        
        //console.log(window.decodeURIComponent(n.href))
        //console.log(n.host)
        //console.log(decode(n.href));
        //console.log(decodeURI(n.href))
        t = n.protocol === "https:" ? "wss:" : "ws:";
        t += "/" + n.host;
        t += n.pathname + "status/ws/";
        t=decode(t);
        console.log(t)
        try {
            u = new WebSocket(t);
            u.onmessage = function () {
                fetchStatus()
            };
            u.onerror = function () {
                console.error("Error while connecting to websocket for invoice notifications (callback)")
            }
            clearInterval(c);
        } catch (p) {
            console.error("Error while connecting to websocket for invoice notifications")
        }
    }
    $(".menu__item").click(function () {
        $(".menu__scroll .menu__item").removeClass("selected");
        $(this).addClass("selected");
        language();
        $(".selector span").text($(".selected").text())
    });
    i = !1;
    $(".buyerTotalLine").click(function () {
        $("line-items").toggleClass("expanded");
        i ? $("line-items").slideUp() : $("line-items").slideDown();
        i = !i;
        $(".buyerTotalLine").toggleClass("expanded");
        $(".single-item-order__right__btc-price__chevron").toggleClass("expanded")
    });
    a = new Clipboard("._copySpan", {
        target: function (n) {
            return s(n, 0, 65).firstChild
        }
    });
    v = new Clipboard("._copyInput", {
        target: function (n) {
            return s(n, 4, 65).firstChild
        }
    });
    $(document).keypress(function (n) {
        n.which === "13" && n.preventDefault()
    })
});
