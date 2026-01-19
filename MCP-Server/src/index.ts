#!/usr/bin/env node

/**
 * Revit MCP Server
 * Bridge between AI and Revit via MCP
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from "@modelcontextprotocol/sdk/types.js";
import { RevitSocketClient } from "./socket.js";
import { registerRevitTools, executeRevitTool } from "./tools/revit-tools.js";

// MCP Server Instance
const server = new Server(
  {
    name: "revit-mcp-server",
    version: "1.0.0",
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Revit Socket Client
const revitClient = new RevitSocketClient();

/**
 * Handle List Tools Request
 */
server.setRequestHandler(ListToolsRequestSchema, async () => {
  const tools = registerRevitTools();
  console.error(`[MCP Server] Registered ${tools.length} Revit tools`);
  return { tools };
});

/**
 * Handle Call Tool Request
 */
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  console.error(`[MCP Server] Calling tool: ${request.params.name}`);
  console.error(`[MCP Server] Arguments:`, JSON.stringify(request.params.arguments, null, 2));

  try {
    // Check Revit Connection
    if (!revitClient.isConnected()) {
      console.error("[MCP Server] Revit not connected, attempting to connect...");
      await revitClient.connect();
    }

    // Execute Revit Tool
    const result = await executeRevitTool(
      request.params.name,
      request.params.arguments || {},
      revitClient
    );

    console.error(`[MCP Server] Tool executed successfully`);

    return {
      content: [
        {
          type: "text",
          text: JSON.stringify(result, null, 2),
        },
      ],
    };
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error(`[MCP Server] Tool execution failed: ${errorMessage}`);

    return {
      content: [
        {
          type: "text",
          text: `Error: ${errorMessage}`,
        },
      ],
      isError: true,
    };
  }
});

/**
 * Start Server
 */
async function main() {
  console.error("Revit MCP Server starting...");
  console.error("Waiting for Revit Plugin...");

  const transport = new StdioServerTransport();
  await server.connect(transport);

  console.error("MCP Server Started");
  console.error("Socket Server listening on 8966");
}

main().catch((error) => {
  console.error("Server startup failed", error);
  process.exit(1);
});