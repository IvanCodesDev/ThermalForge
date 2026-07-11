"""Agent 协议注册表与跨契约一致性校验。"""
from __future__ import annotations

from hashlib import sha256

from core.agents.contracts import AgentDefinition, PromptDefinition, SkillDefinition, ToolDefinition, ToolPolicy
from core.config import REQUIRED_LLM_MODEL, Settings


class PromptRegistry:
    def __init__(self, definitions: tuple[PromptDefinition, ...] = ()) -> None:
        self._items: dict[str, PromptDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: PromptDefinition) -> None:
        expected = sha256(definition.template.encode("utf-8")).hexdigest()
        if definition.sha256 != expected:
            raise ValueError(f"prompt {definition.id} 的 sha256 与模板不匹配")
        if definition.id in self._items:
            raise ValueError(f"prompt {definition.id} 已注册")
        self._items[definition.id] = definition

    def get(self, prompt_id: str) -> PromptDefinition:
        try:
            return self._items[prompt_id]
        except KeyError as exc:
            raise KeyError(f"prompt {prompt_id} 未注册") from exc


class SkillRegistry:
    def __init__(self, definitions: tuple[SkillDefinition, ...] = ()) -> None:
        self._items: dict[str, SkillDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: SkillDefinition) -> None:
        if definition.id in self._items:
            raise ValueError(f"skill {definition.id} 已注册")
        self._items[definition.id] = definition

    def get(self, skill_id: str) -> SkillDefinition:
        try:
            return self._items[skill_id]
        except KeyError as exc:
            raise KeyError(f"skill {skill_id} 未注册") from exc


class AgentRegistry:
    def __init__(
        self,
        settings: Settings,
        prompts: PromptRegistry,
        skills: SkillRegistry,
        tools: tuple[ToolDefinition, ...],
        definitions: tuple[AgentDefinition, ...] = (),
    ) -> None:
        self.settings = settings
        self.prompts = prompts
        self.skills = skills
        self.tools = {tool.id: tool for tool in tools}
        self._items: dict[str, AgentDefinition] = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition: AgentDefinition) -> None:
        if self.settings.openai_text_model != REQUIRED_LLM_MODEL or definition.model != REQUIRED_LLM_MODEL:
            raise ValueError(f"agent {definition.id} 只能使用 Settings.openai_text_model={REQUIRED_LLM_MODEL}")
        self.prompts.get(definition.prompt_id)
        for skill_id in definition.skills:
            self.skills.get(skill_id)
        for tool_id in definition.tools:
            tool = self.tools.get(tool_id)
            if tool is None:
                raise ValueError(f"tool {tool_id} 未注册")
            if tool.adapter_only:
                raise ValueError(f"LLM agent {definition.id} 不得绑定 adapter-only tool {tool_id}")
            if not set(tool.required_permissions).issubset(definition.permissions):
                raise ValueError(f"agent {definition.id} 缺少 tool {tool_id} 所需权限")
        if definition.id in self._items:
            raise ValueError(f"agent {definition.id} 已注册")
        self._items[definition.id] = definition

    def get(self, agent_id: str) -> AgentDefinition:
        try:
            return self._items[agent_id]
        except KeyError as exc:
            raise KeyError(f"agent {agent_id} 未注册") from exc

    def policy_for(self, agent_id: str) -> ToolPolicy:
        definition = self.get(agent_id)
        return ToolPolicy(allowed_tools=definition.tools, denied_permissions=tuple(
            permission for permission in ("network", "filesystem_write", "shell", "secrets_read")
            if permission not in definition.permissions
        ))
