from llama_index.core.llms import  ChatMessage, LLMMetadata
from llama_index.llms.openai import OpenAI
# from llama_index.agent import ReActAgent

from dotenv import load_dotenv
import os

load_dotenv()


model = os.environ.get("MODEL")
gateway_base_url = os.environ.get("GATEWAY_BASE_URL")
gateway_api_key = os.environ.get("GATEWAY_API_KEY")


llm = OpenAI(
  model=model,
  api_key=gateway_api_key,
  api_base=gateway_base_url, # api_base represents the endpoint the Llama-Index object will make a call to when invoked
  temperature=0.1,
  max_tokens=4096,
)
# Adjust the below parameters as per the model you've chosen
llm.__class__.metadata = LLMMetadata(
  context_window=4096, 
  num_output=4096,
  is_chat_model=True,
  is_function_calling_model=False, 
  model_name=model,
)
print(llm.chat([ChatMessage(role="user",content="write a thousand word essay on the sky")]).message.content)
# agent = ReActAgent.from_tools(tools=[],llm=llm) 