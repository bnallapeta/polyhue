/**
 * color-ts Tools Capability
 *
 * Returns a color band from the TypeScript palette (yellow/gold hues).
 * Part of the polyglot color-assignment demo for the MCP Dev Summit talk.
 */

import * as z from 'zod';
import type {
  ListToolsRequest,
  ListToolsResult,
  CallToolRequest,
  CallToolResult,
  Tool,
} from 'wasmcp:mcp-v20251125/mcp@0.1.1';
import type { RequestCtx } from 'wasmcp:mcp-v20251125/tools@0.1.1';

const LANGUAGE = 'typescript';
const HUE_BASE = 45;
const HUE_SPREAD = 20;

const ColorToolSchema = z.object({
  seed: z.string().optional().describe('Optional session id to make the color deterministic'),
});

type ColorToolArgs = z.infer<typeof ColorToolSchema>;

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function listTools(
  _ctx: RequestCtx,
  _request: ListToolsRequest
): ListToolsResult {
  const tools: Tool[] = [
    {
      name: 'get_color_ts',
      inputSchema: JSON.stringify(z.toJSONSchema(ColorToolSchema)),
      options: {
        title: 'TypeScript color band',
        description: 'Return a TypeScript-palette color (yellow/gold hues)',
      },
    },
  ];

  return { tools };
}

async function callTool(
  _ctx: RequestCtx,
  request: CallToolRequest
): Promise<CallToolResult | undefined> {
  if (request.name !== 'get_color_ts') {
    return undefined;
  }

  try {
    const parsed: ColorToolArgs = ColorToolSchema.parse(
      request.arguments ? JSON.parse(request.arguments) : {}
    );

    const h = hashString(parsed.seed ?? '');
    const hue = HUE_BASE + (h % HUE_SPREAD);
    const sat = 70 + ((h >>> 8) % 20);
    const light = 50 + ((h >>> 16) % 10);

    const payload = JSON.stringify({
      hsl: `hsl(${hue}, ${sat}%, ${light}%)`,
      language: LANGUAGE,
    });

    return textResult(payload);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return errorResult(`Invalid arguments: ${error.message}`);
    }
    return errorResult(
      `Error processing request: ${error instanceof Error ? error.message : String(error)}`
    );
  }
}

function textResult(text: string): CallToolResult {
  return {
    content: [{
      tag: 'text',
      val: {
        text: { tag: 'text', val: text },
      },
    }],
    isError: false,
  };
}

function errorResult(message: string): CallToolResult {
  return {
    content: [{
      tag: 'text',
      val: {
        text: { tag: 'text', val: message },
      },
    }],
    isError: true,
  };
}

export const tools = {
  listTools,
  callTool,
};
