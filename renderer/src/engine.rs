use std::collections::HashMap;
use std::io::{self, Write};

use minijinja::syntax::SyntaxConfig;
use minijinja::{AutoEscape, Environment, Error, ErrorKind, UndefinedBehavior};

use crate::protocol::{RenderError, RenderErrorKind, Request, Response, from_json};
use crate::{filters, metadata};

const FUEL: u64 = 5_000_000;
const RECURSION_LIMIT: usize = 64;
const MAX_OUTPUT: usize = 1024 * 1024;

struct CappedWriter(Vec<u8>);

impl Write for CappedWriter {
    fn write(&mut self, data: &[u8]) -> io::Result<usize> {
        if self.0.len() + data.len() > MAX_OUTPUT {
            return Err(io::Error::other("output too large"));
        }
        self.0.extend_from_slice(data);
        Ok(data.len())
    }

    fn flush(&mut self) -> io::Result<()> {
        Ok(())
    }
}

fn environment(html: bool, currencies: HashMap<String, u32>) -> Environment<'static> {
    let mut env = Environment::new();
    env.set_syntax(
        SyntaxConfig::builder()
            .trim_blocks(true)
            .build()
            .expect("trim_blocks syntax is valid"),
    );
    env.set_fuel(Some(FUEL));
    env.set_recursion_limit(RECURSION_LIMIT);
    env.set_undefined_behavior(UndefinedBehavior::Lenient);
    env.set_auto_escape_callback(move |_| {
        if html {
            AutoEscape::Html
        } else {
            AutoEscape::None
        }
    });
    env.set_unknown_method_callback(minijinja_contrib::pycompat::unknown_method_callback);
    minijinja_contrib::add_to_environment(&mut env);
    filters::register(&mut env, currencies);
    metadata::register(&mut env);
    env
}

fn failure(error: &Error) -> Response {
    let kind = match error.kind() {
        ErrorKind::SyntaxError => RenderErrorKind::Syntax,
        ErrorKind::OutOfFuel => RenderErrorKind::Fuel,
        ErrorKind::WriteFailure => RenderErrorKind::Output,
        _ => RenderErrorKind::Runtime,
    };
    let message = match error.detail() {
        Some(detail) => format!("{}: {detail}", error.kind()),
        None => error.kind().to_string(),
    };
    Response::failed(RenderError {
        kind,
        line: error.line(),
        message,
    })
}

pub fn render(request: Request) -> Response {
    metadata::clear();
    let env = environment(request.autoescape, request.currencies);
    let template = match env.template_from_str(&request.text) {
        Ok(template) => template,
        Err(error) => return failure(&error),
    };
    if request.check {
        return Response::rendered(String::new(), Vec::new());
    }
    let mut output = CappedWriter(Vec::new());
    let context = from_json(request.context, request.safe_key.as_deref());
    match template.render_captured_to(context, &mut output) {
        Ok(_) => Response::rendered(
            String::from_utf8_lossy(&output.0).into_owned(),
            metadata::take(),
        ),
        Err(error) => failure(&error),
    }
}
