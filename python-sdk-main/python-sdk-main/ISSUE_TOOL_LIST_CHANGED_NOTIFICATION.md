# Tool List Changed Notification Not Sent Automatically

## Summary

When tools are dynamically added to the server at runtime (e.g., via `ToolManager.add_tool()` or `FastMCP.add_tool()`), the server does not automatically send `ToolListChangedNotification` to clients, even when the server declares support for tool list change notifications via `NotificationOptions(tools_changed=True)`.

This results in a **silent update** where:
- Tools are added to the server's internal registry
- Clients are not notified of the change
- Clients must poll `tools/list` to discover new tools

## Expected Behavior

When tools are added or removed dynamically at runtime, the server should:
1. Automatically send `ToolListChangedNotification` to all connected clients
2. Only send notifications if the server has declared support (`tools_changed=True`)
3. Behave consistently with how other notifications work (e.g., `ResourceListChangedNotification`)

## Actual Behavior

- Tools can be added via `ToolManager.add_tool()` or `FastMCP.add_tool()`
- No notification is sent automatically
- The `send_tool_list_changed()` method exists in `ServerSession` but must be called manually
- Clients are unaware of tool changes unless they explicitly poll `tools/list`

## Steps to Reproduce

1. Create an MCP server with `NotificationOptions(tools_changed=True)`
2. Connect a client and initialize the session
3. Dynamically add a tool at runtime:
   ```python
   @server.tool()
   async def new_tool():
       return "result"
   # or
   server.add_tool(some_function)
   ```
4. Observe that no `ToolListChangedNotification` is sent to the client
5. Client must manually call `tools/list` to discover the new tool

## Code Locations

**Notification method exists but not called:**
- `src/mcp/server/session.py:318-320` - `send_tool_list_changed()` method
- `src/mcp/types.py:923-930` - `ToolListChangedNotification` definition

**Tool addition methods that don't trigger notification:**
- `src/mcp/server/fastmcp/tools/tool_manager.py:45-71` - `ToolManager.add_tool()`
- `src/mcp/server/fastmcp/server.py:357-391` - `FastMCP.add_tool()`

## Proposed Solution

The `ToolManager.add_tool()` method (or `FastMCP.add_tool()`) should:

1. Check if the server supports tool list change notifications (via session capabilities)
2. If supported, automatically call `session.send_tool_list_changed()` for all active sessions when:
   - A new tool is successfully added (not a duplicate)
   - A tool is removed (if removal functionality exists)

## Comparison with Similar Features

Looking at the example in `examples/snippets/servers/notifications.py`:
- Resource notifications require **manual** calls: `await ctx.session.send_resource_list_changed()`
- However, this might be intentional for resources since they can change frequently
- Tools, on the other hand, are typically added less frequently and should benefit from automatic notifications

## Impact

- **Low**: Clients can work around this by polling `tools/list` periodically
- **Medium**: Violates the MCP protocol expectation when `tools_changed=True` is declared
- **Medium**: Inconsistent with user expectations (declared capability not fully implemented)

## Additional Context

The server correctly:
- Declares tool change notification capability via `NotificationOptions(tools_changed=True)`
- Includes `listChanged: true` in the `ToolsCapability` during initialization
- Provides the `send_tool_list_changed()` method for manual notification sending

However, the automatic notification flow is missing when tools are actually added/removed.


