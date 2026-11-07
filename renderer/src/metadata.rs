use std::cell::RefCell;

use minijinja::value::{Value, ValueKind};
use minijinja::{Environment, Error, ErrorKind};
use serde::Serialize;

use crate::decimal::as_decimal;
use crate::protocol::from_json;

const MAX_WRITE_DEPTH: usize = 32;

#[derive(Serialize, Clone, Copy, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum WriteOp {
    Set,
    Delete,
}

#[derive(Serialize, Clone)]
pub struct MetadataWrite {
    pub r#ref: String,
    pub op: WriteOp,
    pub key: String,
    pub value: serde_json::Value,
}

thread_local! {
    static WRITES: RefCell<Vec<MetadataWrite>> = const { RefCell::new(Vec::new()) };
}

pub fn clear() {
    WRITES.with(|writes| writes.borrow_mut().clear());
}

pub fn take() -> Vec<MetadataWrite> {
    WRITES.with(|writes| writes.take())
}

fn object_ref(object: &Value) -> Result<String, Error> {
    object
        .get_attr("_ref")?
        .as_str()
        .map(str::to_string)
        .ok_or_else(|| {
            Error::new(
                ErrorKind::InvalidOperation,
                "metadata helpers need an object passed to the template",
            )
        })
}

fn record(reference: String, op: WriteOp, key: String, value: serde_json::Value) {
    WRITES.with(|writes| {
        writes.borrow_mut().push(MetadataWrite {
            r#ref: reference,
            op,
            key,
            value,
        })
    });
}

fn pending_write(reference: &str, key: &str) -> Option<MetadataWrite> {
    WRITES.with(|writes| {
        writes
            .borrow()
            .iter()
            .rev()
            .find(|write| write.r#ref == reference && write.key == key)
            .cloned()
    })
}

fn get_metadata(object: Value, key: String, default: Option<Value>) -> Result<Value, Error> {
    let fallback = default.unwrap_or(Value::from(()));
    if let Some(write) = pending_write(&object_ref(&object)?, &key) {
        return Ok(if write.op == WriteOp::Set {
            from_json(write.value, None)
        } else {
            fallback
        });
    }
    let found = object.get_attr("meta")?.get_attr(&key)?;
    Ok(if found.is_undefined() {
        fallback
    } else {
        found
    })
}

fn to_json(value: &Value, depth: usize) -> Result<serde_json::Value, Error> {
    if depth > MAX_WRITE_DEPTH {
        return Err(Error::new(
            ErrorKind::InvalidOperation,
            "metadata value is nested too deeply",
        ));
    }
    if let Some(decimal) = as_decimal(value) {
        return Ok(serde_json::Value::String(decimal.to_string()));
    }
    match value.kind() {
        ValueKind::Seq => value
            .try_iter()?
            .map(|item| to_json(&item, depth + 1))
            .collect::<Result<Vec<_>, _>>()
            .map(serde_json::Value::Array),
        ValueKind::Map => value
            .try_iter()?
            .map(|key| {
                let item = to_json(&value.get_item(&key)?, depth + 1)?;
                Ok((key.to_string(), item))
            })
            .collect::<Result<serde_json::Map<_, _>, Error>>()
            .map(serde_json::Value::Object),
        _ => Ok(serde_json::to_value(value).unwrap_or(serde_json::Value::Null)),
    }
}

fn update_metadata(object: Value, key: String, value: Value) -> Result<Value, Error> {
    record(object_ref(&object)?, WriteOp::Set, key, to_json(&value, 0)?);
    Ok(object)
}

fn delete_metadata(object: Value, key: String) -> Result<Value, Error> {
    record(
        object_ref(&object)?,
        WriteOp::Delete,
        key,
        serde_json::Value::Null,
    );
    Ok(object)
}

pub fn register(env: &mut Environment<'static>) {
    env.add_function("get_metadata", get_metadata);
    env.add_function("update_metadata", update_metadata);
    env.add_function("delete_metadata", delete_metadata);
}
