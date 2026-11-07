use bitcart_renderer::engine::render;
use bitcart_renderer::protocol::{Request, Response};
use serde_json::{Value, json};

fn run(text: &str) -> Response {
    let context = json!({
        "store": {"_ref": "Store:1", "meta": {"keep": 1}},
        "plain": {"meta": {}},
        "price": {"$decimal": "10.50"},
    });
    render(Request {
        text: text.to_string(),
        context,
        ..Default::default()
    })
}

fn writes(response: &Response) -> Value {
    serde_json::to_value(&response.writes).unwrap()
}

#[test]
fn records_writes_without_applying_them() {
    let response = run(
        "{{ update_metadata(store, 'a', 1) and '' }}{{ delete_metadata(store, 'keep') and '' }}",
    );
    assert!(response.ok);
    assert_eq!(
        writes(&response),
        json!([
            {"ref": "Store:1", "op": "set", "key": "a", "value": 1},
            {"ref": "Store:1", "op": "delete", "key": "keep", "value": null},
        ])
    );
}

#[test]
fn reads_see_pending_writes() {
    let text = "{{ update_metadata(store, 'a', 2) and '' }}{{ get_metadata(store, 'a') }}|{{ delete_metadata(store, 'keep') and '' }}{{ get_metadata(store, 'keep', 'gone') }}";
    assert_eq!(run(text).text, "2|gone");
}

#[test]
fn reads_stored_values_and_defaults() {
    assert_eq!(
        run("{{ get_metadata(store, 'keep') }}|{{ get_metadata(store, 'x', 'd') }}").text,
        "1|d"
    );
}

#[test]
fn failed_render_returns_no_writes() {
    let response = run("{{ update_metadata(store, 'a', 1) and '' }}{{ 1 / 0 }}");
    assert!(!response.ok);
    assert_eq!(writes(&response), json!([]));
}

#[test]
fn only_objects_passed_to_the_template_can_be_written() {
    assert!(!run("{{ update_metadata(plain, 'a', 1) }}").ok);
    assert!(!run("{{ update_metadata('text', 'a', 1) }}").ok);
}

#[test]
fn writes_from_a_failed_render_do_not_reach_the_next_one() {
    assert!(!run("{{ update_metadata(store, 'a', 1) and '' }}{{ 1 / 0 }}").ok);
    let next = run("x");
    assert!(next.ok);
    assert_eq!(writes(&next), json!([]));
}

#[test]
fn decimals_are_written_as_exact_text_at_any_depth() {
    let response = run(
        "{{ update_metadata(store, 'a', price) and '' }}{{ update_metadata(store, 'b', {'x': [price, 1]}) and '' }}",
    );
    assert_eq!(
        writes(&response),
        json!([
            {"ref": "Store:1", "op": "set", "key": "a", "value": "10.50"},
            {"ref": "Store:1", "op": "set", "key": "b", "value": {"x": ["10.50", 1]}},
        ])
    );
}

#[test]
fn pending_decimals_read_back_as_exact_text() {
    let text = "{{ update_metadata(store, 'a', price) and '' }}{{ get_metadata(store, 'a') }}";
    assert_eq!(run(text).text, "10.50");
}

#[test]
fn other_values_keep_their_shape() {
    let response = run(
        "{{ update_metadata(store, 'a', 'text') and '' }}{{ update_metadata(store, 'b', range(2)) and '' }}{{ update_metadata(store, 'c', namespace(n=1)) and '' }}{{ update_metadata(store, 'd', nothing) and '' }}",
    );
    let values: Vec<Value> = response
        .writes
        .iter()
        .map(|write| write.value.clone())
        .collect();
    assert_eq!(
        values,
        vec![json!("text"), json!([0, 1]), json!({"n": 1}), json!(null)]
    );
}

#[test]
fn values_containing_themselves_are_refused() {
    let response =
        run("{% set ns = namespace() %}{% set ns.me = ns %}{{ update_metadata(store, 'a', ns) }}");
    assert!(!response.ok);
    assert_eq!(
        response.error.unwrap().message,
        "invalid operation: metadata value is nested too deeply"
    );
}
