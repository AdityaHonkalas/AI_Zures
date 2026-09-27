from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.schema import HumanMessage

from dotenv import load_dotenv
import os

load_dotenv()


model = os.environ.get("MODEL")
gateway_base_url = os.environ.get("GATEWAY_BASE_URL")
gateway_api_key = os.environ.get("GATEWAY_API_KEY")


messages = [
  HumanMessage(content="What is agentic ai?"),
]
llm = ChatOpenAI(
  model_name=model,
  temperature=0.1,
  max_tokens=4096,
  openai_api_base=gateway_base_url,
  openai_api_key=gateway_api_key,
)
print(llm.invoke(messages).content)