"""
Run the Macro Pulse MCP Server
------------------------------
Starts the MCP server over stdio transport.
Use this to connect Claude Desktop or any MCP-compatible client
to your Macro Pulse API.

Usage:
    python scripts/run_mcp.py

Claude Desktop config (add to claude_desktop_config.json):
{
  "mcpServers": {
    "macro-pulse": {
      "command": "python",
      "args": ["<absolute-path-to>/scripts/run_mcp.py"],
      "cwd": "<absolute-path-to-project-root>"
    }
  }
}
"""

import asyncio
import sys
import os

# Ensure project root is in path AND set CWD so relative DB path resolves correctly
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

from mcp.server.stdio import stdio_server
from app.mcp_server import server


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())