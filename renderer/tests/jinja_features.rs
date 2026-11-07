use std::collections::HashMap;

use bitcart_renderer::engine::render;
use bitcart_renderer::protocol::{RenderErrorKind, Request, Response};
use serde_json::{Value, json};

fn run(text: &str, context: Value) -> Response {
    render(Request {
        text: text.to_string(),
        context,
        currencies: HashMap::from([("BTC".to_string(), 8)]),
        ..Default::default()
    })
}

fn rendered(text: &str, context: Value) -> String {
    let response = run(text, context);
    assert!(
        response.ok,
        "{text}: {}",
        response.error.map_or(String::new(), |error| error.message)
    );
    response.text
}

#[test]
fn urlencode_escapes_strings_and_maps() {
    assert_eq!(
        rendered("{{ 'a b&c/d' | urlencode }}", json!({})),
        "a%20b%26c/d"
    );
    assert_eq!(
        rendered("{{ {'order': 'a b'} | urlencode }}", json!({})),
        "order=a%20b"
    );
}

#[test]
fn identifiers_can_be_non_ascii() {
    assert_eq!(
        rendered("{% set усяго = 5 %}{{ усяго * 2 }}", json!({})),
        "10"
    );
    assert_eq!(
        rendered("{{ тавар.назва }}", json!({"тавар": {"назва": "Кубак"}})),
        "Кубак"
    );
}

#[test]
fn sort_ignores_case_outside_ascii() {
    assert_eq!(
        rendered("{{ ['б', 'А', 'в', 'Г'] | sort | join(',') }}", json!({})),
        "А,б,в,Г"
    );
}

#[test]
fn trims_the_newline_after_a_block() {
    assert_eq!(rendered("{% if true %}\nyes{% endif %}", json!({})), "yes");
}

#[test]
fn enabled_template_features_work() {
    for (template, expected) in [
        ("{{ [1, 'a'] | tojson }}", "[1, \"a\"]"),
        (
            "{% for i in [1, 2, 3] %}{% if i == 2 %}{% break %}{% endif %}{{ i }}{% endfor %}",
            "1",
        ),
        (
            "{% for i in [1, 2] %}{{ loop.previtem | default('-') }}{% endfor %}",
            "-1",
        ),
        ("{{ 1000 | filesizeformat }}", "1.0 kB"),
    ] {
        assert_eq!(rendered(template, json!({})), expected, "{template}");
    }
}

#[test]
fn runs_out_of_fuel_on_long_loops() {
    let response = run(
        "{% for a in range(3000) %}{% for b in range(3000) %}{% endfor %}{% endfor %}",
        json!({}),
    );
    assert_eq!(
        serde_json::to_value(&response).unwrap()["error"]["kind"],
        "fuel"
    );
}

#[test]
fn limits_recursion_depth() {
    let macro_definition = "{% macro m(n) %}{% if n %}{{ m(n - 1) }}{% endif %}{% endmacro %}";
    assert_eq!(
        rendered(&format!("{macro_definition}{{{{ m(5) }}}}done"), json!({})),
        "done"
    );
    let response = run(&format!("{macro_definition}{{{{ m(50) }}}}"), json!({}));
    assert_eq!(
        response.error.map(|error| error.kind).unwrap(),
        RenderErrorKind::Runtime
    );
}

#[test]
fn truncate_takes_positional_and_keyword_arguments() {
    let context = json!({"text": "hello brave new world today"});
    for (template, expected) in [
        ("{{ text | truncate }}", "hello brave new world today"),
        ("{{ text | truncate(10) }}", "hello..."),
        ("{{ text | truncate(length=10) }}", "hello..."),
        ("{{ text | truncate(10, true) }}", "hello b..."),
        ("{{ text | truncate(10, killwords=true) }}", "hello b..."),
        ("{{ text | truncate(10, true, '!') }}", "hello bra!"),
        (
            "{{ text | truncate(10, true, '...', 20) }}",
            "hello brave new world today",
        ),
    ] {
        assert_eq!(rendered(template, context.clone()), expected, "{template}");
    }
    for template in [
        "{{ text | truncate(10, true, '...', 20, 1) }}",
        "{{ text | truncate(10, unknown=1) }}",
    ] {
        assert!(!run(template, context.clone()).ok, "{template}");
    }
}

fn run_with_safe_key(text: &str, context: Value, safe_key: Option<&str>) -> String {
    let response = render(Request {
        text: text.to_string(),
        context,
        autoescape: true,
        safe_key: safe_key.map(str::to_string),
        ..Default::default()
    });
    assert!(response.ok, "{text}");
    response.text
}

#[test]
fn values_marked_with_the_request_key_are_not_escaped() {
    let context = json!({
        "parts": [{"$safe:abc": "<b>Mug &amp; cup</b>"}],
        "name": "Tom & Co",
    });
    for (template, expected) in [
        ("{{ name }}", "Tom &amp; Co"),
        (
            "{% for part in parts %}<p>{{ part }}</p>{% endfor %}",
            "<p><b>Mug &amp; cup</b></p>",
        ),
        (
            "{{ parts[0] | replace('Mug', 'Cup') }}",
            "<b>Cup &amp; cup</b>",
        ),
        ("{{ parts[0] | length }}", "20"),
        ("{{ 'Mug' in parts[0] }}", "True"),
    ] {
        assert_eq!(
            run_with_safe_key(template, context.clone(), Some("$safe:abc")),
            expected,
            "{template}"
        );
    }
}

#[test]
fn stored_values_cannot_pose_as_safe() {
    let html = "<script>";
    let escaped = "&lt;script&gt;";
    for (context, key) in [
        (json!({"a": {"$safe:other": html}}), Some("$safe:abc")),
        (json!({"a": {"$safe:abc": html}}), None),
    ] {
        let printed = run_with_safe_key(
            "{% for key, value in a | items %}{{ value }}{% endfor %}",
            context,
            key,
        );
        assert_eq!(printed, escaped);
    }
    let with_extra_key = json!({"a": {"$safe:abc": html, "other": 1}});
    assert_eq!(
        run_with_safe_key("{{ a['$safe:abc'] }}", with_extra_key, Some("$safe:abc")),
        escaped
    );
}

#[test]
fn tg_escape_escapes_markdown() {
    assert_eq!(
        rendered("{{ 'a_b*c`d[e' | tg_escape }}", json!({})),
        "a\\_b\\*c\\`d\\[e"
    );
}

#[test]
fn divisibleby_never_panics() {
    let context = json!({
        "price": {"$decimal": "10.50"},
        "whole": {"$decimal": "21.00"},
        "seven": {"$decimal": "7.00"},
    });
    for (template, expected) in [
        ("{{ 21 is divisibleby(seven) }}", "True"),
        ("{{ 20 is divisibleby(seven) }}", "False"),
        ("{{ whole is divisibleby(seven) }}", "True"),
        ("{{ 21 is divisibleby(7) }}", "True"),
        ("{{ 21 is divisibleby(4) }}", "False"),
        ("{{ 10 is divisibleby(0) }}", "False"),
        ("{{ 10.5 is divisibleby(0) }}", "False"),
        ("{{ 10.5 is divisibleby(3.5) }}", "True"),
        ("{{ price is divisibleby(0) }}", "False"),
        ("{{ whole is divisibleby(7) }}", "True"),
        (
            "{{ (-170141183460469231731687303715884105727 - 1) is divisibleby(-1) }}",
            "False",
        ),
    ] {
        assert_eq!(rendered(template, context.clone()), expected, "{template}");
    }
}

#[test]
fn parity_tests_only_accept_whole_numbers() {
    let context = json!({
        "whole": {"$decimal": "21.00"},
        "negative": {"$decimal": "-21"},
        "fraction": {"$decimal": "21.50"},
        "even": {"$decimal": "22.00"},
        "even_fraction": {"$decimal": "22.50"},
        "huge": {"$decimal": "1000000000000000000000000000000000000001"},
    });
    for (template, expected) in [
        ("{{ whole is odd }}", "True"),
        ("{{ negative is odd }}", "True"),
        ("{{ fraction is odd }}", "False"),
        ("{{ even is even }}", "True"),
        ("{{ even_fraction is even }}", "False"),
        ("{{ huge is odd }}", "True"),
    ] {
        assert_eq!(rendered(template, context.clone()), expected, "{template}");
    }
}

#[test]
fn round_keeps_the_requested_places() {
    let context = json!({"price": {"$decimal": "10.50"}, "large": {"$decimal": "1000.50"}});
    assert_eq!(rendered("{{ price | round(1) }}", context.clone()), "10.5");
    assert_eq!(
        rendered("{{ price | round(3) }}", context.clone()),
        "10.500"
    );
    assert_eq!(rendered("{{ price | round(-5) }}", context.clone()), "0");
    assert_eq!(
        rendered("{{ large | round(28) }}", context.clone()),
        format!("1000.5{}", "0".repeat(27))
    );
    assert!(!run("{{ price | round(99999) }}", context).ok);
}

#[test]
fn format_decimal_rounds_values_of_any_length() {
    let context = |value: &str, currency: &str| json!({"order": {"price": {"$decimal": value}, "currency": currency}});
    for (value, currency, expected) in [
        ("10.505", "USD", "10.51"),
        ("-10.505", "USD", "-10.51"),
        ("0.123456789", "BTC", "0.12345679"),
        ("0.123456789", "btc", "0.12345679"),
        (
            "123456789012345678.123456789012345678",
            "USD",
            "123456789012345678.12",
        ),
        (
            "1234567890123456789012345.50",
            "BTC",
            "1234567890123456789012345.50000000",
        ),
    ] {
        assert_eq!(
            rendered(
                "{{ order | format_decimal('price') }}",
                context(value, currency)
            ),
            expected,
            "{value}"
        );
    }
    assert_eq!(
        rendered(
            "{{ order | format_decimal('missing') }}",
            context("1", "USD")
        ),
        ""
    );
}

#[test]
fn format_decimal_fails_without_a_currency_table() {
    let response = render(Request {
        text: "{{ order | format_decimal('price') }}".to_string(),
        context: json!({"order": {"price": {"$decimal": "1.5"}, "currency": "BTC"}}),
        ..Default::default()
    });
    assert_eq!(
        response.error.unwrap().message,
        "invalid operation: the request has no currency table"
    );
}

#[test]
fn format_handles_decimals_by_conversion() {
    let context = json!({
        "price": {"$decimal": "10.50"},
        "whole": {"$decimal": "21.00"},
        "big": {"$decimal": "123456789012345678.12"},
        "name": "mug",
    });
    for (template, expected) in [
        ("{{ '%s' | format(price) }}", "10.50"),
        ("{{ '%s' | format(big) }}", "123456789012345678.12"),
        ("{{ '%d' | format(price) }}", "10"),
        ("{{ '%d' | format(big) }}", "123456789012345678"),
        ("{{ '%.1f' | format(price) }}", "10.5"),
        ("{{ '%8.2f|' | format(price) }}", "   10.50|"),
        (
            "{{ '| %-5s| %6.2f | %3.0f |' | format(name, price, 2) }}",
            "| mug  |  10.50 |   2 |",
        ),
        ("{{ '<b>%.1f</b>' | safe | format(price) }}", "<b>10.5</b>"),
        ("{{ '<b>%s</b>' | safe | format(price) }}", "<b>10.50</b>"),
        ("{{ '{}'.format(price) }}", "10.50"),
        ("{{ '{:.2f}'.format(price) }}", "10.50"),
        ("{{ '{:d}'.format(whole) }}", "21"),
    ] {
        assert_eq!(rendered(template, context.clone()), expected, "{template}");
    }
}
