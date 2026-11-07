use std::cmp::Ordering;
use std::fmt;
use std::sync::Arc;

use bigdecimal::RoundingMode;
use minijinja::value::{Object, ObjectRepr, Value, ValueKind};
use minijinja::{Error, ErrorKind};

use crate::number::Decimal;

impl Object for Decimal {
    fn repr(self: &Arc<Self>) -> ObjectRepr {
        ObjectRepr::Plain
    }

    fn is_true(self: &Arc<Self>) -> bool {
        !self.is_zero()
    }

    fn custom_cmp_value(self: &Arc<Self>, other: &Value) -> Option<Ordering> {
        Some(match operand(other) {
            Some(other) => self.compare(&other),
            None => Value::from(0).cmp(other),
        })
    }

    fn custom_op(
        self: &Arc<Self>,
        op: &str,
        other: &Value,
        reflected: bool,
    ) -> Option<Result<Value, Error>> {
        if let Some(rv) = builtin(self, op, other, reflected) {
            return Some(rv);
        }
        if as_decimal(other).is_none() && !other.is_integer() {
            return None;
        }
        let theirs = operand(other)?;
        let (left, right) = if reflected {
            (&theirs, self.as_ref())
        } else {
            (self.as_ref(), &theirs)
        };
        let result = match op {
            "+" => left.add(right),
            "-" => left.sub(right),
            "*" => left.mul(right),
            "/" => left.div(right),
            "%" => left.rem(right),
            "//" => left.floor_div(right),
            "**" => left.pow(right),
            _ => None,
        };
        Some(result.map(Value::from_object).ok_or_else(|| {
            Error::new(
                ErrorKind::InvalidOperation,
                format!("unable to calculate with {op}"),
            )
        }))
    }

    fn render(self: &Arc<Self>, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        fmt::Display::fmt(self.as_ref(), f)
    }
}

fn builtin(
    number: &Decimal,
    op: &str,
    other: &Value,
    reflected: bool,
) -> Option<Result<Value, Error>> {
    Some(match op {
        "number" => Ok(Value::from(true)),
        "neg" => Ok(Value::from_object(number.neg())),
        "abs" => Ok(Value::from_object(number.abs())),
        "int" => number.to_i128().map(Value::from).ok_or_else(|| {
            Error::new(
                ErrorKind::InvalidOperation,
                "number is too large to convert to an integer",
            )
        }),
        "float" => Ok(Value::from(number.to_f64())),
        "odd" => Ok(Value::from(number.is_odd())),
        "even" => Ok(Value::from(number.is_even())),
        "divisibleby" => Ok(Value::from(operand(other).is_some_and(|theirs| {
            if reflected {
                theirs.is_divisible_by(number)
            } else {
                number.is_divisible_by(&theirs)
            }
        }))),
        "round" => round(number, other),
        _ => return None,
    })
}

fn round(number: &Decimal, options: &Value) -> Result<Value, Error> {
    let places = i64::try_from(options.get_item_by_index(0)?)?;
    let method = options.get_item_by_index(1)?;
    let mode = match method.as_str() {
        Some("ceil") => RoundingMode::Ceiling,
        Some("floor") => RoundingMode::Floor,
        _ => RoundingMode::HalfEven,
    };
    number
        .round(places, mode)
        .map(Value::from_object)
        .ok_or_else(|| {
            Error::new(
                ErrorKind::InvalidOperation,
                format!("unable to round to {places} places"),
            )
        })
}

pub fn as_decimal(value: &Value) -> Option<&Decimal> {
    value.downcast_object_ref::<Decimal>()
}

fn operand(value: &Value) -> Option<Decimal> {
    if let Some(decimal) = as_decimal(value) {
        return Some(decimal.clone());
    }
    if value.kind() == ValueKind::Bool {
        return Decimal::parse(if value.is_true() { "1" } else { "0" });
    }
    if value.is_integer() {
        return Decimal::parse(&value.to_string());
    }
    if !value.is_number() {
        return None;
    }
    let float = f64::try_from(value.clone()).ok()?;
    // A whole float prints in full, matching how the engine compares it with integers.
    if float.fract() == 0.0 {
        return Decimal::parse(&format!("{float:.0}"));
    }
    Decimal::parse(&format!("{float}"))
}
