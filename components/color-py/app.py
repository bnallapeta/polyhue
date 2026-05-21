"""color-py Tools Capability Provider

Returns a color band from the Python palette (blue hues).
Part of the polyglot color-assignment demo for the MCP Dev Summit talk.
"""

import json
import hashlib
from typing import Optional
from wit_world import exports
from wit_world.imports import mcp, server_handler

LANGUAGE = "python"
HUE_BASE = 210
HUE_SPREAD = 20


class PythonColorer(exports.Tools):
    def list_tools(
        self,
        ctx: server_handler.RequestCtx,
        request: mcp.ListToolsRequest,
    ) -> mcp.ListToolsResult:
        return mcp.ListToolsResult(
            tools=[
                mcp.Tool(
                    name="get_color_py",
                    input_schema=json.dumps({
                        "type": "object",
                        "properties": {
                            "seed": {
                                "type": "string",
                                "description": "Optional session id to make the color deterministic",
                            },
                        },
                    }),
                    options=mcp.ToolOptions(
                        meta=None,
                        annotations=None,
                        description="Return a Python-palette color (blue hues)",
                        output_schema=None,
                        icons=None,
                        title="Python color band",
                    ),
                ),
            ],
            meta=None,
            next_cursor=None,
        )

    def call_tool(
        self,
        ctx: server_handler.RequestCtx,
        request: mcp.CallToolRequest,
    ) -> Optional[mcp.CallToolResult]:
        if request.name != "get_color_py":
            return None

        seed = ""
        if request.arguments:
            try:
                args = json.loads(request.arguments)
                seed = str(args.get("seed", ""))
            except json.JSONDecodeError:
                pass

        digest = hashlib.sha256(seed.encode("utf-8")).digest()
        hue = HUE_BASE + (digest[0] % HUE_SPREAD)
        sat = 70 + (digest[1] % 20)
        light = 50 + (digest[2] % 10)

        payload = json.dumps({
            "hsl": f"hsl({hue}, {sat}%, {light}%)",
            "language": LANGUAGE,
        })

        return mcp.CallToolResult(
            content=[mcp.ContentBlock_Text(mcp.TextContent(
                text=mcp.TextData_Text(payload),
                options=None,
            ))],
            is_error=None,
            meta=None,
            structured_content=None,
        )


# Export the Tools implementation
Tools = PythonColorer
