"""PLUTO Agent Orchestrator - The Brain"""
import json
from typing import Optional, Dict, Any, List, AsyncGenerator
from app.schemas.chat import AgentStateEvent, ExecutionStep, Activity, ActionPreview
from app.agent.tool_registry import tool_registry
from app.llm.gpt_oss import gpt_oss_client
from app.voice.elevenlabs import elevenlabs_client
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class AgentOrchestrator:
    """Central orchestrator for PLUTO agent"""
    
    def __init__(self):
        self.conversation_history: List[Dict[str, str]] = []
        self.system_prompt = """You are PLUTO, a futuristic AI desktop assistant for Linux.

You can control the user's computer through safe, structured tool calls. You have access to these capabilities:
- Filesystem operations (create/read/list/delete files and directories)
- Application launching (VS Code, Firefox, terminal, etc.)
- System monitoring (CPU, RAM, processes)
- Terminal command execution (with safety checks)
- URL opening in browser

When the user asks you to do something:
1. Analyze the request carefully
2. Break it into clear steps if needed
3. Use the appropriate tools
4. Provide clear feedback

IMPORTANT RULES:
- Always use tools for OS operations - never describe what you would do
- For destructive operations (delete, etc.), the system will ask for user confirmation
- Be concise but informative
- Think step-by-step for complex requests

Respond naturally and helpfully."""
    
    async def execute_command(
        self,
        command: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[AgentStateEvent, None]:
        """
        Main command execution pipeline
        
        Yields AgentStateEvent objects for real-time frontend updates
        """
        try:
            # IDLE → UNDERSTANDING
            yield AgentStateEvent(
                type="agent_state",
                state="understanding",
                task="Parsing natural language request..."
            )
            
            # Add user message to history
            self.conversation_history.append({
                "role": "user",
                "content": command
            })
            
            # UNDERSTANDING → THINKING
            yield AgentStateEvent(
                type="agent_state",
                state="thinking",
                task="Analyzing system permissions & OS capabilities..."
            )
            
            # Get tool definitions
            tools = tool_registry.get_tool_definitions()
            
            # Build messages with system prompt
            messages = [
                {"role": "system", "content": self.system_prompt},
                *self.conversation_history
            ]
            
            # Call GPT-OSS
            logger.info("llm_request", command=command)
            response = await gpt_oss_client.chat_completion(
                messages=messages,
                tools=tools,
                temperature=0.7
            )
            
            # Check if model wants to use a tool
            tool_call = await gpt_oss_client.extract_tool_call(response)
            
            if tool_call:
                # THINKING → PLANNING
                yield AgentStateEvent(
                    type="agent_state",
                    state="planning",
                    task=f"Planning to use tool: {tool_call['tool']}"
                )
                
                # Create execution steps
                steps = await self._create_execution_steps(tool_call)
                for step in steps:
                    yield AgentStateEvent(
                        type="execution_step",
                        step=step
                    )
                
                # Check permission level
                permission = tool_registry.get_permission_level(tool_call['tool'])
                
                if permission == "CONFIRM_REQUIRED":
                    # Send confirmation request to frontend
                    preview = await self._create_action_preview(tool_call)
                    yield AgentStateEvent(
                        type="action_preview",
                        preview=preview
                    )
                    # Orchestrator waits for frontend confirmation before continuing
                    # (This would be handled via separate confirm endpoint)
                    return
                
                # PLANNING → EXECUTING
                yield AgentStateEvent(
                    type="agent_state",
                    state="executing",
                    task=f"Executing {tool_call['tool']}..."
                )
                
                # Update steps to current
                for i, step in enumerate(steps):
                    step.status = "current"
                    yield AgentStateEvent(type="execution_step", step=step)
                    
                    # Execute the tool
                    if i == len(steps) - 1:  # Last step is actual execution
                        result = await tool_registry.execute_tool(
                            tool_call['tool'],
                            **tool_call['arguments']
                        )
                    
                    step.status = "completed"
                    yield AgentStateEvent(type="execution_step", step=step)
                
                # Check result
                if result.success:
                    # EXECUTING → SUCCESS
                    yield AgentStateEvent(
                        type="agent_state",
                        state="success",
                        task=result.message or "Task completed successfully"
                    )
                    
                    # Add to activity log
                    activity = await self._create_activity(tool_call, result)
                    yield AgentStateEvent(
                        type="activity",
                        activity=activity
                    )
                    
                    # Get final response from LLM
                    self.conversation_history.append({
                        "role": "assistant",
                        "content": f"Tool executed: {result.message}"
                    })
                else:
                    # EXECUTING → ERROR
                    yield AgentStateEvent(
                        type="agent_state",
                        state="error",
                        error=result.error.get("message") if result.error else "Execution failed"
                    )
            
            else:
                # No tool call - just text response
                text_response = await gpt_oss_client.get_text_response(response)
                self.conversation_history.append({
                    "role": "assistant",
                    "content": text_response
                })
                
                yield AgentStateEvent(
                    type="agent_state",
                    state="success",
                    task="Response ready",
                    data={"response": text_response}
                )
        
        except Exception as e:
            logger.error("orchestrator_error", error=str(e))
            yield AgentStateEvent(
                type="agent_state",
                state="error",
                error=str(e)
            )
    
    async def _create_execution_steps(self, tool_call: Dict) -> List[ExecutionStep]:
        """Create execution steps based on tool"""
        tool_name = tool_call['tool']
        
        # Default steps
        return [
            ExecutionStep(id="s1", label=f"Validate {tool_name} parameters", status="pending"),
            ExecutionStep(id="s2", label="Check permissions", status="pending"),
            ExecutionStep(id="s3", label=f"Execute {tool_name}", status="pending")
        ]
    
    async def _create_action_preview(self, tool_call: Dict) -> ActionPreview:
        """Create action preview for confirmation"""
        tool_name = tool_call['tool']
        args = tool_call['arguments']
        
        if tool_name == "delete_file":
            return ActionPreview(
                type="file_delete",
                title="Confirm File Deletion",
                content=f"PLUTO wants to delete: {args.get('path')}",
                path=args.get('path'),
                requiresConfirmation=True
            )
        
        elif tool_name == "execute_command":
            return ActionPreview(
                type="command",
                title="Confirm Terminal Command",
                content=f"Execute: {args.get('command')}",
                requiresConfirmation=True
            )
        
        return ActionPreview(
            type="automation",
            title=f"Confirm {tool_name}",
            content=json.dumps(args),
            requiresConfirmation=True
        )
    
    async def _create_activity(self, tool_call: Dict, result: Any) -> Activity:
        """Create activity log entry"""
        import time
        tool_name = tool_call['tool']
        
        category_map = {
            "open_application": "app",
            "open_url": "app",
            "create_file": "file",
            "create_directory": "file",
            "delete_file": "file",
            "execute_command": "system"
        }
        
        return Activity(
            id=f"act-{int(time.time() * 1000)}",
            title=f"Executed {tool_name}",
            description=result.message or "",
            timestamp="Just now",
            status="success" if result.success else "error",
            category=category_map.get(tool_name, "automation")
        )
    
    async def synthesize_speech(self, text: str) -> bytes:
        """Convert text response to speech"""
        return await elevenlabs_client.text_to_speech(text)
    
    def reset(self):
        """Reset conversation history"""
        self.conversation_history = []


# Singleton instance
agent_orchestrator = AgentOrchestrator()
