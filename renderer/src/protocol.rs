use std::collections::HashMap;
use std::io::{self, Read, Write};
use std::os::fd::AsRawFd;
use std::os::unix::net::UnixStream;

use minijinja::value::Value;
use serde::{Deserialize, Serialize};

use crate::engine;
use crate::metadata::MetadataWrite;
use crate::number::Decimal;

const MAX_REQUEST: usize = 1024 * 1024;
pub const DECIMAL_KEY: &str = "$decimal";

#[derive(Deserialize, Default)]
pub struct Request {
    pub text: String,
    #[serde(default)]
    pub context: serde_json::Value,
    #[serde(default)]
    pub autoescape: bool,
    #[serde(default)]
    pub check: bool,
    #[serde(default)]
    pub currencies: HashMap<String, u32>,
    #[serde(default)]
    pub safe_key: Option<String>,
}

#[derive(Serialize, Clone, Copy, Debug, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum RenderErrorKind {
    Syntax,
    Fuel,
    Output,
    Runtime,
    Request,
    Memory,
    Timeout,
}

#[derive(Serialize)]
pub struct RenderError {
    pub kind: RenderErrorKind,
    pub line: Option<usize>,
    pub message: String,
}

#[derive(Serialize)]
pub struct Response {
    pub ok: bool,
    pub text: String,
    pub writes: Vec<MetadataWrite>,
    pub error: Option<RenderError>,
}

impl Response {
    pub fn rendered(text: String, writes: Vec<MetadataWrite>) -> Self {
        Self {
            ok: true,
            text,
            writes,
            error: None,
        }
    }

    pub fn failed(error: RenderError) -> Self {
        Self {
            ok: false,
            text: String::new(),
            writes: Vec::new(),
            error: Some(error),
        }
    }

    fn bad_request(message: String) -> Self {
        Self::failed(RenderError {
            kind: RenderErrorKind::Request,
            line: None,
            message,
        })
    }
}

pub fn from_json(value: serde_json::Value, safe_key: Option<&str>) -> Value {
    match value {
        serde_json::Value::Null => Value::from(()),
        serde_json::Value::Bool(value) => Value::from(value),
        serde_json::Value::Number(number) => number
            .as_i64()
            .map(Value::from)
            .or_else(|| number.as_u64().map(Value::from))
            .unwrap_or_else(|| Value::from(number.as_f64().unwrap_or(f64::NAN))),
        serde_json::Value::String(text) => Value::from(text),
        serde_json::Value::Array(items) => Value::from(
            items
                .into_iter()
                .map(|item| from_json(item, safe_key))
                .collect::<Vec<_>>(),
        ),
        serde_json::Value::Object(map) => {
            if map.len() == 1 {
                if let Some(serde_json::Value::String(text)) = map.get(DECIMAL_KEY)
                    && let Some(decimal) = Decimal::parse(text)
                {
                    return Value::from_object(decimal);
                }
                if let Some(key) = safe_key
                    && let Some(serde_json::Value::String(text)) = map.get(key)
                {
                    return Value::from_safe_string(text.clone());
                }
            }
            Value::from_pairs(
                map.into_iter()
                    .map(|(key, item)| (key, from_json(item, safe_key))),
            )
        }
    }
}

fn respond(stream: &mut UnixStream, response: &Response) -> io::Result<()> {
    let encoded = serde_json::to_vec(response).map_err(io::Error::other)?;
    stream.write_all(&(encoded.len() as u32).to_be_bytes())?;
    stream.write_all(&encoded)
}

// A request can wait in the socket queue after its client timed out. Rendering it would only delay
// everyone behind it.
fn client_left(stream: &UnixStream) -> bool {
    let mut byte = 0u8;
    // SAFETY: byte is a valid one-byte buffer for the whole call, and stream owns the descriptor.
    unsafe {
        libc::recv(
            stream.as_raw_fd(),
            (&mut byte as *mut u8).cast(),
            1,
            libc::MSG_PEEK | libc::MSG_DONTWAIT,
        ) == 0
    }
}

pub fn serve(mut stream: UnixStream) -> io::Result<()> {
    let mut size = [0u8; 4];
    stream.read_exact(&mut size)?;
    let size = u32::from_be_bytes(size) as usize;
    if size > MAX_REQUEST {
        return respond(
            &mut stream,
            &Response::bad_request("request too large".to_string()),
        );
    }
    let mut body = vec![0u8; size];
    stream.read_exact(&mut body)?;
    if client_left(&stream) {
        return Ok(());
    }
    let response = match serde_json::from_slice::<Request>(&body) {
        Ok(request) => engine::render(request),
        Err(error) => Response::bad_request(error.to_string()),
    };
    respond(&mut stream, &response)
}
