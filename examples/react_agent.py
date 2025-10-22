import inspect
import json
import os
import sys
import openai
from dotenv import load_dotenv
import asyncio
import logging
from datetime import datetime
import textwrap

# Suppress HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.server import mcp
from opentargets_mcp.tools.disease import DiseaseApi
from opentargets_mcp.tools.drug import DrugApi
from opentargets_mcp.tools.evidence import EvidenceApi
from opentargets_mcp.tools.meta import MetaApi
from opentargets_mcp.tools.search import SearchApi
from opentargets_mcp.tools.study import StudyApi
from opentargets_mcp.tools.target import TargetApi
from opentargets_mcp.tools.variant import VariantApi

_API_INSTANCES = (
    TargetApi(),
    DiseaseApi(),
    DrugApi(),
    EvidenceApi(),
    SearchApi(),
    VariantApi(),
    StudyApi(),
    MetaApi(),
)

TOOL_DISPATCH = {}
for api in _API_INSTANCES:
    for attr in dir(api):
        if attr.startswith("_"):
            continue
        method = getattr(api, attr)
        if inspect.iscoroutinefunction(method):
            TOOL_DISPATCH[attr] = method

# Terminal color codes optimized for white/light backgrounds
class Colors:
    HEADER = '\033[35m'      # Magenta
    BLUE = '\033[34m'        # Blue
    GREEN = '\033[32m'       # Dark Green
    RED = '\033[31m'         # Red
    BOLD = '\033[1m'
    DIM = '\033[2m'          # Dim text
    END = '\033[0m'
    BLACK = '\033[30m'       # Black for emphasis

def print_header(text: str):
    """Print a simple header."""
    print(f"\n{Colors.BLACK}{Colors.BOLD}{text}{Colors.END}")
    print(f"{Colors.DIM}{'─' * len(text)}{Colors.END}")

def print_thought(thought: str):
    """Extract and print the thought section."""
    if "Thought:" in thought:
        thought_text = thought.split("Thought:", 1)[1].split("Action:", 1)[0].strip()
        # Remove excessive whitespace and wrap
        thought_text = ' '.join(thought_text.split())
        wrapped_text = textwrap.fill(thought_text, width=80, initial_indent="", subsequent_indent="")
        print(f"\n{Colors.BLUE}💭 {wrapped_text}{Colors.END}")

def print_action(action: dict):
    """Print the action in a compact way."""
    tool_name = action.get('tool_name')
    if tool_name == 'finish':
        print(f"\n{Colors.GREEN}🎯 Preparing final answer...{Colors.END}")
    else:
        args = action.get('arguments', {})
        args_str = ", ".join([f"{k}={repr(v)}" for k, v in args.items() if k not in ['page_size', 'page_index']])
        if len(args_str) > 60:
            args_str = args_str[:60] + "..."
        print(f"\n{Colors.GREEN}🎯 Calling {tool_name}({args_str}){Colors.END}")

def print_observation(observation: any):
    """Print key information from observation."""
    if isinstance(observation, dict) and observation:
        # Handle search results
        if 'search' in observation and 'hits' in observation['search']:
            hits = observation['search']['hits']
            total = observation['search'].get('total', len(hits))
            print(f"{Colors.DIM}   → Found {total} results{Colors.END}")
            if hits:
                first_hit = hits[0]
                name = first_hit.get('name', 'Unknown')
                entity_type = first_hit.get('entity', 'unknown')
                obj_id = first_hit.get('id', 'N/A')
                print(f"{Colors.BLACK}   → {name} ({entity_type}: {obj_id}){Colors.END}")
        
        # Handle drug info
        elif 'drug' in observation and observation['drug']:
            drug = observation['drug']
            if 'name' in drug:
                print(f"{Colors.BLACK}   → Drug: {drug['name']}{Colors.END}")
            if 'mechanismsOfAction' in drug and drug['mechanismsOfAction'].get('rows'):
                moa = drug['mechanismsOfAction']['rows'][0]
                print(f"{Colors.BLACK}   → Mechanism: {moa.get('mechanismOfAction', 'N/A')}{Colors.END}")
                if 'targets' in moa and moa['targets']:
                    target = moa['targets'][0]
                    print(f"{Colors.BLACK}   → Target: {target.get('approvedSymbol', 'N/A')}{Colors.END}")
        
        # Handle target info
        elif 'target' in observation and observation['target']:
            target = observation['target']
            if 'approvedSymbol' in target:
                print(f"{Colors.BLACK}   → Target: {target['approvedSymbol']} ({target.get('id', 'N/A')}){Colors.END}")
            if 'associatedDiseases' in target and 'count' in target['associatedDiseases']:
                print(f"{Colors.DIM}   → Associated diseases: {target['associatedDiseases']['count']}{Colors.END}")
        
        # Handle disease info
        elif 'disease' in observation and observation['disease']:
            disease = observation['disease']
            if 'name' in disease:
                print(f"{Colors.BLACK}   → Disease: {disease['name']} ({disease.get('id', 'N/A')}){Colors.END}")
        
        # Generic fallback
        else:
            keys = list(observation.keys())[:3]
            print(f"{Colors.DIM}   → Response with keys: {', '.join(keys)}{Colors.END}")

def print_error(error_msg: str):
    """Print error messages only if they're user-relevant."""
    # Skip internal parsing errors
    if "JSON" in error_msg or "parsing" in error_msg:
        return
    print(f"{Colors.RED}❌ {error_msg}{Colors.END}")

def print_final_answer(answer: str):
    """Print the final answer in a clean format."""
    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Answer:{Colors.END}")
    wrapped = textwrap.fill(answer, width=80, initial_indent="   ", subsequent_indent="   ")
    print(f"{Colors.BLACK}{wrapped}{Colors.END}")

async def main():
    load_dotenv()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

    if not os.getenv("OPENAI_API_KEY"):
        print_error("OPENAI_API_KEY not found in .env file or environment.")
        sys.exit(1)

    api_client = OpenTargetsClient()
    await api_client._ensure_session()

    # Get tools and prepare for JSON serialization
    tools = []
    for tool in await mcp._tool_manager.list_tools():
        tool_dict = tool.model_dump(exclude={'fn', 'serializer'})
        # Convert sets to lists for JSON serialization
        if 'tags' in tool_dict and isinstance(tool_dict['tags'], set):
            tool_dict['tags'] = list(tool_dict['tags'])
        tools.append(tool_dict)

    tools_json_str = json.dumps(tools, indent=2)

    system_prompt = f"""
You are an expert bioinformatics assistant. Your goal is to answer the user's question by breaking it down into a series of steps. You will proceed in a loop of Thought, Action, and Observation.

At each step, you must first output your reasoning in a `Thought:` block. Then, you must specify your next move in an `Action:` block.

The `Action` must be a single JSON object with one of two formats:
1. To call a tool: `{{"tool_name": "function_to_call", "arguments": {{"arg1": "value1"}}}}`
2. To finish and give the final answer to the user: `{{"tool_name": "finish", "answer": "Your final answer here."}}`

**IMPORTANT RULES:**
- You **MUST** choose a tool from the "Available Tools" list. Do not invent a tool name.
- Your response must follow the `Thought:` then `Action:` format.

After your action, the system will provide an `Observation:` with the result of your tool call. Use the observation to inform your next thought. Continue this process until you have enough information to answer the user's question completely.

**Available Tools:**
{tools_json_str}
"""

    print_header("🧬 Open Targets ReAct Agent")
    print(f"{Colors.DIM}Ask a question. Type 'exit' to quit.{Colors.END}")

    try:
        while True:
            question = input(f"\n{Colors.BOLD}Question:{Colors.END} ")
            if question.lower() == 'exit':
                print(f"{Colors.DIM}Goodbye!{Colors.END}")
                break

            print(f"\n{Colors.DIM}Processing: {question}{Colors.END}")
            
            history = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
            
            step_count = 0
            for i in range(10):  # Limit to 10 steps
                # Get LLM response
                response = openai.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=history
                )
                response_text = response.choices[0].message.content
                
                # Skip empty or error responses
                if not response_text or "Thought:" not in response_text:
                    continue
                
                step_count += 1
                print(f"\n{Colors.DIM}Step {step_count}:{Colors.END}")
                
                # Print thought
                print_thought(response_text)
                
                history.append({"role": "assistant", "content": response_text})

                try:
                    # Extract and parse action
                    action_json_str = ""
                    if "Action:" in response_text:
                        action_part = response_text.split("Action:", 1)[1].strip()
                        json_start = action_part.find('{')
                        json_end = action_part.rfind('}') + 1
                        if json_start != -1 and json_end != -1 and json_end > json_start:
                            action_json_str = action_part[json_start:json_end]
                        
                    if not action_json_str:
                        history.append({"role": "user", "content": "Observation: Error parsing action. Please ensure the Action block contains valid JSON."})
                        continue

                    action = json.loads(action_json_str)
                    print_action(action)
                    
                    tool_name = action.get("tool_name")

                    if tool_name == "finish":
                        final_answer = action.get("answer", "I have finished the task.")
                        print_final_answer(final_answer)
                        break
                    if tool_name not in TOOL_DISPATCH:
                        history.append({"role": "user", "content": f"Observation: Invalid tool name '{tool_name}'."})
                        continue

                    arguments = action.get("arguments", {})
                    func_to_call = TOOL_DISPATCH[tool_name]
                    observation = await func_to_call(api_client, **arguments)

                    print_observation(observation)

                    observation_str = json.dumps(observation, indent=2)
                    history.append({"role": "user", "content": f"Observation:\n{observation_str}"})

                except json.JSONDecodeError:
                    history.append({"role": "user", "content": "Observation: Error parsing action JSON."})
                except Exception as e:
                    history.append({"role": "user", "content": f"Observation: An error occurred: {str(e)}"})
                    break

    except KeyboardInterrupt:
        print(f"\n{Colors.DIM}Interrupted.{Colors.END}")
    finally:
        await api_client.close()

if __name__ == "__main__":
    asyncio.run(main())
