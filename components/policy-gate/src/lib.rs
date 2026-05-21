//! policy-gate — Regorus-backed authorization middleware (as a tool).
//!
//! Exposes a single tool, `peek_attendees`, that evaluates a Rego policy
//! against the request before doing anything. The policy denies by default,
//! so triggering the tool produces a denial — which is the audience-flash
//! beat of the talk.

mod bindings {
    wit_bindgen::generate!({
        world: "policy-gate",
        generate_all,
    });
}

use bindings::exports::wasmcp::mcp_v20251125::tools::Guest;
use bindings::wasmcp::mcp_v20251125::mcp::*;
use bindings::wasmcp::mcp_v20251125::server_handler::MessageContext;
use regorus::{Engine, Value};

const POLICY: &str = r#"
package authz

default allow := false

# Anything other than peek_attendees is allowed; peek_attendees is denied.
allow if {
    input.action != "peek_attendees"
}
"#;

struct PolicyGate;

impl Guest for PolicyGate {
    fn list_tools(
        _ctx: MessageContext,
        _request: ListToolsRequest,
    ) -> Result<ListToolsResult, ErrorCode> {
        Ok(ListToolsResult {
            tools: vec![Tool {
                name: "peek_attendees".to_string(),
                input_schema: r#"{"type":"object","properties":{}}"#.to_string(),
                options: Some(ToolOptions {
                    meta: None,
                    icons: None,
                    annotations: None,
                    description: Some(
                        "List the audience members. Requires Regorus policy approval.".to_string(),
                    ),
                    output_schema: None,
                    title: Some("Peek attendees".to_string()),
                }),
            }],
            next_cursor: None,
            meta: None,
        })
    }

    fn call_tool(
        _ctx: MessageContext,
        request: CallToolRequest,
    ) -> Result<Option<CallToolResult>, ErrorCode> {
        if request.name != "peek_attendees" {
            return Ok(None);
        }

        let allowed = match evaluate(&request.name) {
            Ok(v) => v,
            Err(msg) => return Ok(Some(deny_result(msg))),
        };

        Ok(Some(if allowed {
            success_result("attendees: [...]".to_string())
        } else {
            deny_result(
                "denied by Regorus policy: action 'peek_attendees' is never allowed".to_string(),
            )
        }))
    }
}

fn evaluate(action: &str) -> Result<bool, String> {
    let mut engine = Engine::new();
    engine
        .add_policy("authz.rego".to_string(), POLICY.to_string())
        .map_err(|e| format!("policy load failed: {e}"))?;

    let input_json = serde_json::json!({ "action": action }).to_string();
    let input_value =
        Value::from_json_str(&input_json).map_err(|e| format!("input parse failed: {e}"))?;
    engine.set_input(input_value);

    let results = engine
        .eval_query("data.authz.allow".to_string(), false)
        .map_err(|e| format!("policy eval failed: {e}"))?;

    let allowed = results
        .result
        .first()
        .and_then(|r| r.expressions.first())
        .map(|e| matches!(e.value, Value::Bool(true)))
        .unwrap_or(false);

    Ok(allowed)
}

fn success_result(msg: String) -> CallToolResult {
    CallToolResult {
        content: vec![ContentBlock::Text(TextContent {
            text: TextData::Text(msg),
            options: None,
        })],
        is_error: None,
        meta: None,
        structured_content: None,
    }
}

fn deny_result(reason: String) -> CallToolResult {
    let payload = serde_json::json!({
        "denied": true,
        "reason": reason,
    })
    .to_string();
    CallToolResult {
        content: vec![ContentBlock::Text(TextContent {
            text: TextData::Text(payload),
            options: None,
        })],
        is_error: Some(true),
        meta: None,
        structured_content: None,
    }
}

bindings::export!(PolicyGate with_types_in bindings);
