use std::collections::HashMap;

use bitcart_renderer::engine::render;
use bitcart_renderer::protocol::{Request, Response};
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
fn matches_recorded_cases() {
    let data: Value = serde_json::from_str(include_str!("data/decimal_cases.json")).unwrap();
    for case in data["cases"].as_array().unwrap() {
        let template = case["template"].as_str().unwrap();
        let response = run(template, data["context"].clone());
        if case.get("error").is_some() {
            assert!(
                !response.ok,
                "{} should fail, rendered {:?}",
                case["id"], response.text
            );
        } else {
            assert!(response.ok, "{} failed", case["id"]);
            assert_eq!(
                response.text,
                case["expected"].as_str().unwrap(),
                "{}",
                case["id"]
            );
        }
    }
}

#[test]
fn compares_at_full_precision() {
    let context = json!({
        "big": {"$decimal": "123456789012345678.123456789012345678"},
        "bigger": {"$decimal": "123456789012345678.123456789012345679"},
    });
    assert_eq!(
        rendered("{{ big == bigger }}|{{ big < bigger }}", context),
        "False|True"
    );
}

#[test]
fn matches_generated_cases() {
    for line in include_str!("data/generated_decimal_cases.jsonl").lines() {
        let case: Value = serde_json::from_str(line).unwrap();
        let (op, b) = (case["op"].as_str().unwrap(), &case["b"]);
        let template = match op {
            "add" => "{{ a + b }}".to_string(),
            "sub" => "{{ a - b }}".to_string(),
            "mul" => "{{ a * b }}".to_string(),
            "div" => "{{ a / b }}".to_string(),
            "rem" => "{{ a % b }}".to_string(),
            "floordiv" => "{{ a // b }}".to_string(),
            "lt" => "{{ a < b }}".to_string(),
            "eq" => "{{ a == b }}".to_string(),
            "int" => "{{ a | int }}".to_string(),
            "pow" => format!("{{{{ a ** ({}) }}}}", b.as_str().unwrap()),
            "round_he" => format!("{{{{ a | round({}) }}}}", b.as_str().unwrap()),
            "round_ceil" => format!("{{{{ a | round({}, 'ceil') }}}}", b.as_str().unwrap()),
            "round_floor" => format!("{{{{ a | round({}, 'floor') }}}}", b.as_str().unwrap()),
            _ => panic!("unknown op {op}"),
        };
        let context = json!({"a": {"$decimal": case["a"]}, "b": {"$decimal": b}});
        assert_eq!(rendered(&template, context), case["expected"], "{line}");
    }
}

#[test]
fn rounds_long_results_to_28_digits() {
    let context = json!({"big": {"$decimal": "123456789012345678.123456789012345678"}});
    assert_eq!(
        rendered("{{ big * 2 }}", context.clone()),
        "246913578024691356.2469135780"
    );
    assert_eq!(
        rendered("{{ big + 1 }}", context.clone()),
        "123456789012345679.1234567890"
    );
    assert_eq!(
        rendered("{{ -big }}", context.clone()),
        "-123456789012345678.123456789012345678"
    );
    assert_eq!(
        rendered("{{ big | abs }}", context),
        "123456789012345678.123456789012345678"
    );
}

#[test]
fn division_rounds_up_when_digits_past_a_tie_remain() {
    let context = json!({
        "a": {"$decimal": "858279"},
        "b": {"$decimal": "63014"},
        "c": {"$decimal": "839686476"},
        "d": {"$decimal": "931349491"},
    });
    assert_eq!(
        rendered("{{ a / b }}", context.clone()),
        "13.62044942393753769003713461"
    );
    assert_eq!(
        rendered("{{ c / d }}", context),
        "0.9015804315288985324629334017"
    );
}

#[test]
fn only_reasonably_long_text_becomes_a_decimal() {
    let longest = "1".repeat(4096);
    let too_long = "1".repeat(4097);
    let context = json!({"a": {"$decimal": longest}, "b": {"$decimal": too_long}});
    assert_eq!(rendered("{{ a is number }}", context.clone()), "True");
    assert_eq!(
        rendered("{{ b is number }}|{{ b['$decimal'] | length }}", context),
        "False|4097"
    );
}

#[test]
fn keeps_decimal_places_when_a_zero_is_involved() {
    let context = json!({"zero": {"$decimal": "0.00"}, "price": {"$decimal": "10.50"}});
    for (template, expected) in [
        ("{{ zero * 2 }}", "0.00"),
        ("{{ price * 0 }}", "0.00"),
        ("{{ zero / 2 }}", "0.00"),
        ("{{ zero + 1 }}", "1.00"),
        ("{{ price % price }}", "0.00"),
        ("{{ -zero }}", "0.00"),
        ("{{ zero * -1 }}", "0.00"),
    ] {
        assert_eq!(rendered(template, context.clone()), expected, "{template}");
    }
}

#[test]
fn never_prints_exponents() {
    let context =
        json!({"tiny": {"$decimal": "0.00000001"}, "zero": {"$decimal": "0.000000000000000000"}});
    for (template, expected) in [
        ("{{ tiny }}", "0.00000001"),
        ("{{ tiny * 2 }}", "0.00000002"),
        ("{{ zero * tiny }}", "0.00000000000000000000000000"),
        ("{{ tiny / 1000 }}", "0.00000000001"),
    ] {
        assert_eq!(rendered(template, context.clone()), expected, "{template}");
    }
}

#[test]
fn refuses_impossible_and_oversized_results() {
    let context = json!({
        "two": {"$decimal": "2"},
        "half": {"$decimal": "0.5"},
        "zero": {"$decimal": "0"},
        "huge": {"$decimal": "9".repeat(4000)},
    });
    for template in [
        "{{ huge * huge * huge }}",
        "{{ huge ** 9223372036854775807 }}",
        "{{ two / 0 }}",
        "{{ two % 0 }}",
        "{{ two // 0 }}",
        "{{ zero / 0 }}",
        "{{ zero ** 0 }}",
        "{{ zero ** -1 }}",
        "{{ two ** 100000 }}",
        "{{ half ** 100000 }}",
        "{{ two ** 9223372036854775807 }}",
        "{{ two ** half }}",
    ] {
        let response = run(template, context.clone());
        assert!(!response.ok, "{template} rendered {:?}", response.text);
    }
}

#[test]
fn sorting_decimals_with_strings_keeps_a_total_order() {
    let text = "{{ [price, 'c', price - 7, 24, 41, 35, price + 36, price + 7, 32, price + 12, price - 5, price - 53, 12, 35, 'a', price + 10, 48, -22, -37, 'a', price + 31] | sort | length }}";
    assert_eq!(
        rendered(text, json!({"price": {"$decimal": "10.50"}})),
        "21"
    );
}

#[test]
fn decimals_and_whole_floats_compare_like_integers_and_floats() {
    let text =
        "{% set i = 99999999999999995000000 %}{{ i == near }}|{{ near < 1e23 }}|{{ 1e23 < i }}";
    assert_eq!(
        rendered(
            text,
            json!({"near": {"$decimal": "99999999999999995000000"}})
        ),
        "True|False|True"
    );
}

#[test]
fn sorting_mixed_values_never_panics() {
    const LARGE: [&str; 4] = [
        "99999999999999991611392",
        "99999999999999995000000",
        "100000000000000000000000",
        "100000000000000008388608",
    ];
    let context = json!({
        "d0": {"$decimal": "10.50"},
        "d1": {"$decimal": LARGE[0]},
        "d2": {"$decimal": LARGE[1]},
        "d3": {"$decimal": LARGE[2]},
        "d4": {"$decimal": LARGE[3]},
    });
    let mut state = 21u64;
    let mut random = |limit: u64| {
        state = state.wrapping_mul(6364136223846793005).wrapping_add(1);
        (state >> 33) % limit
    };
    for _ in 0..600 {
        let size = [21, 24, 32, 48, 64][random(5) as usize];
        let items: Vec<String> = (0..size)
            .map(|_| match random(8) {
                0 => format!("{}", random(100) as i64 - 50),
                1 => ["'a'", "'c'", "''"][random(3) as usize].to_string(),
                2 => format!("d0 + {}", random(60) as i64 - 30),
                3 => format!("d{}", random(5)),
                4 => LARGE[random(4) as usize].to_string(),
                5 => ["1e23", "9.999999999999999e22", "1.0000000000000001e23"][random(3) as usize]
                    .to_string(),
                6 => ["true", "false"][random(2) as usize].to_string(),
                _ => format!("{}.5", random(100)),
            })
            .collect();
        let text = format!("{{{{ [{}] | sort | length }}}}", items.join(", "));
        assert_eq!(rendered(&text, context.clone()), size.to_string(), "{text}");
    }
}

#[test]
fn keeps_scale_differences_out_of_comparisons() {
    assert_eq!(
        rendered(
            "{{ a == 10.5 }}|{{ a == 21 / 2 }}",
            json!({"a": {"$decimal": "10.500000000000000000"}})
        ),
        "True|True"
    );
}

#[test]
fn only_exact_decimal_text_becomes_a_decimal() {
    let forged = json!({"a": {"$decimal": "1e5"}, "b": {"$decimal": "x"}});
    assert_eq!(
        rendered("{{ a['$decimal'] }}|{{ b['$decimal'] }}", forged),
        "1e5|x"
    );
}
