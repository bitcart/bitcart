use std::collections::HashMap;

use bigdecimal::RoundingMode;
use minijinja::value::{Kwargs, Rest, Value, ValueOrKwargs};
use minijinja::{Environment, Error, ErrorKind, State};

use crate::number::Decimal;

const DEFAULT_DIVISIBILITY: u32 = 2;
const TRUNCATE_ARGUMENTS: [&str; 4] = ["length", "killwords", "end", "leeway"];

fn format_decimal(
    currencies: &HashMap<String, u32>,
    obj: Value,
    key: String,
) -> Result<Value, Error> {
    if currencies.is_empty() {
        return Err(Error::new(
            ErrorKind::InvalidOperation,
            "the request has no currency table",
        ));
    }
    let value = obj.get_attr(&key)?;
    if value.is_undefined() {
        return Ok(Value::from(""));
    }
    let currency = obj.get_attr("currency")?;
    let (Some(currency), Some(number)) = (currency.as_str(), Decimal::parse(&value.to_string()))
    else {
        return Ok(value);
    };
    let places = currencies
        .get(&currency.to_uppercase())
        .copied()
        .unwrap_or(DEFAULT_DIVISIBILITY);
    let rounded = number.round(i64::from(places), RoundingMode::HalfUp);
    Ok(rounded.map_or(value, |rounded| Value::from(rounded.to_string())))
}

fn tg_escape(text: Value) -> String {
    let mut escaped = String::new();
    for c in text.to_string().chars() {
        if matches!(c, '_' | '*' | '`' | '[') {
            escaped.push('\\');
        }
        escaped.push(c);
    }
    escaped
}

fn truncate(
    state: &mut State,
    value: &Value,
    Rest(args): Rest<ValueOrKwargs>,
) -> Result<Value, Error> {
    let mut names = TRUNCATE_ARGUMENTS.iter();
    let mut named = Vec::new();
    for arg in args {
        let arg = arg.into_value();
        if arg.is_kwargs() {
            let kwargs = Kwargs::try_from(arg)?;
            for name in kwargs.args() {
                named.push((name.to_string(), kwargs.peek::<Value>(name)?));
            }
        } else {
            let name = names
                .next()
                .ok_or_else(|| Error::from(ErrorKind::TooManyArguments))?;
            named.push((name.to_string(), arg));
        }
    }
    minijinja_contrib::filters::truncate(state, value, Kwargs::from_iter(named))
}

pub fn register(env: &mut Environment<'static>, currencies: HashMap<String, u32>) {
    env.add_filter("format_decimal", move |obj: Value, key: String| {
        format_decimal(&currencies, obj, key)
    });
    env.add_filter("tg_escape", tg_escape);
    env.add_filter("truncate", truncate);
}
