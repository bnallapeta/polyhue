//! color-rs Tools Capability Provider
//!
//! Returns a color band from the Rust palette (red-orange hues).
//! Part of the polyglot color-assignment demo for the MCP Dev Summit talk.

mod bindings {
    wit_bindgen::generate!({
        world: "color-rs",
        generate_all,
    });
}

use bindings::exports::wasmcp::mcp_v20251125::tools::Guest;
use bindings::wasmcp::mcp_v20251125::mcp::*;
use bindings::wasmcp::mcp_v20251125::server_handler::MessageContext;
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

struct RustColorer;

const LANGUAGE: &str = "rust";
const HUE_BASE: u32 = 10;
const HUE_SPREAD: u32 = 20;

impl Guest for RustColorer {
    fn list_tools(
        _ctx: MessageContext,
        _request: ListToolsRequest,
    ) -> Result<ListToolsResult, ErrorCode> {
        Ok(ListToolsResult {
            tools: vec![Tool {
                name: "get_color_rs".to_string(),
                input_schema: r#"{
                    "type": "object",
                    "properties": {
                        "seed": {"type": "string", "description": "Optional session id to make the color deterministic"}
                    }
                }"#
                .to_string(),
                options: Some(ToolOptions {
                    meta: None,
                    icons: None,
                    annotations: None,
                    description: Some("Return a Rust-palette color (red-orange hues)".to_string()),
                    output_schema: None,
                    title: Some("Rust color band".to_string()),
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
        match request.name.as_str() {
            "get_color_rs" => Ok(Some(color_result(&request.arguments))),
            _ => Ok(None),
        }
    }
}

fn color_result(arguments: &Option<String>) -> CallToolResult {
    let seed = arguments
        .as_ref()
        .and_then(|s| serde_json::from_str::<serde_json::Value>(s).ok())
        .and_then(|v| v.get("seed").and_then(|s| s.as_str()).map(String::from))
        .unwrap_or_default();

    let mut hasher = DefaultHasher::new();
    seed.hash(&mut hasher);
    let h = hasher.finish();

    let hue = HUE_BASE + (h % HUE_SPREAD as u64) as u32;
    let sat = 70 + ((h >> 8) % 20) as u32;
    let light = 50 + ((h >> 16) % 10) as u32;

    let json = format!(
        r#"{{"hsl":"hsl({}, {}%, {}%)","language":"{}"}}"#,
        hue, sat, light, LANGUAGE
    );

    CallToolResult {
        content: vec![ContentBlock::Text(TextContent {
            text: TextData::Text(json),
            options: None,
        })],
        is_error: None,
        meta: None,
        structured_content: None,
    }
}

bindings::export!(RustColorer with_types_in bindings);
