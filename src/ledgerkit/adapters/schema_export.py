"""Export the tool catalogue in the shape the Claude API and MCP use for tool definitions."""

from ledgerkit.tools import ToolRegistry, registry


def export_tool_schemas(reg: ToolRegistry = registry, *, include_meta: bool = False) -> list[dict]:
    """Return [{"name", "description", "input_schema"}, ...].

    The result can be passed as `tools` to the Claude Messages API as is. With
    include_meta=True each entry also says whether the tool changes data and whether
    an agent needs human approval to run it.
    """
    schemas = []
    for tool in reg.list():
        schema = tool.schema()
        if include_meta:
            schema["mutating"] = tool.mutating
            schema["requires_approval"] = tool.requires_approval
        schemas.append(schema)
    return schemas
