# agent_app.py

import json
import os
import sys
import openai
from dotenv import load_dotenv
import asyncio

# --- Directly import the client and tools ---
from opentargets_mcp.queries import OpenTargetsClient
from opentargets_mcp.tools import TOOLS

# --- Main Application Logic ---
async def main():
    load_dotenv()
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo")

    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in .env file or environment.")
        sys.exit(1)

    api_client = OpenTargetsClient()
    
    tools_json_str = json.dumps([tool.model_dump() for tool in TOOLS], indent=2)

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

    print("\n--- Open Targets ReAct Agent ---")
    print("Ask a complex question. Type 'exit' to quit.")

    try:
        while True:
            question = input("\n> ")
            if question.lower() == 'exit':
                break

            history = [{"role": "system", "content": system_prompt}, {"role": "user", "content": question}]
            
            for i in range(10): 
                print(f"\n--- Step {i+1}: Reasoning ---")
                
                response = openai.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=history
                )
                response_text = response.choices[0].message.content
                
                print(response_text)
                history.append({"role": "assistant", "content": response_text})

                try:
                    try:
                        action = json.loads(response_text)
                    except json.JSONDecodeError:
                        action_part = response_text.split("Action:")[1]
                        json_start = action_part.find('{')
                        json_end = action_part.rfind('}') + 1
                        action_json_str = action_part[json_start:json_end]
                        action = json.loads(action_json_str)
                    
                    tool_name = action.get("tool_name")

                    if tool_name == "finish":
                        final_answer = action.get("answer", "I have finished the task.")
                        print(f"\n✅ Final Answer:\n{final_answer}")
                        break
                    
                    if hasattr(api_client, tool_name):
                        arguments = action.get("arguments", {})
                        print(f"--- Step {i+1}: Action ---")
                        print(f"Calling function: api_client.{tool_name}(**{arguments})")
                        
                        func_to_call = getattr(api_client, tool_name)
                        observation = await func_to_call(**arguments)
                        
                        observation_str = json.dumps(observation, indent=2)
                        
                        history.append({"role": "user", "content": f"Observation:\n{observation_str}"})
                        print(f"--- Step {i+1}: Observation ---")
                        print(observation_str[:1000] + "..." if len(observation_str) > 1000 else observation_str)
                    else:
                        # This else block will now catch the hallucinated tool name
                        print(f"Error: The chosen tool '{tool_name}' is not a valid function.")
                        # We add the error observation to the history to allow the agent to self-correct
                        history.append({"role": "user", "content": f"Observation: Invalid tool name '{tool_name}'. You must choose from the available tools list."})

                except (json.JSONDecodeError, IndexError) as e:
                    print(f"Error: Could not parse Action JSON from LLM response. Error: {e}")
                    break
            else:
                print("\nWarning: Agent reached maximum steps without finishing.")

    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        await api_client.close()
        print("API client session closed.")

if __name__ == "__main__":
    asyncio.run(main())