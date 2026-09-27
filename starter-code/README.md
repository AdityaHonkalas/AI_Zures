# GenAI Hub Starter

A collection of test scripts for validating connectivity and functionality of various LLM models through an enterprise AI gateway infrastructure.

## Overview

This folder contains scripts to test different AI frameworks and models:

- **[openai_test.py](openai_test.py)** - Tests OpenAI API-compatible endpoints
- **[chatopenai_test_llm.py](chatopenai_test_llm.py)** - Tests using LangChain's ChatOpenAI wrapper
- **[llama_chat.py](llama_chat.py)** - Tests using Llama-Index framework
- **[embedding.py](embedding.py)** - Tests embedding model functionality
- **[Cert-Solution.ps1](Cert-Solution.ps1)** - PowerShell script for SSL certificate setup in Zscaler environments
- **[cert.py](cert.py)** - Alternative Python-based SSL certificate helper

## Prerequisites

- Python 3.7 or higher
- Access to an AI gateway endpoint with valid API credentials
- Network connectivity to the gateway

## Installation

Install the required Python packages:

```bash
pip install openai python-dotenv
```

For other test scripts, you may need additional dependencies:

```bash
pip install langchain llama-index
```

## Configuration

Create a `.env` file in the `GenAI Hub Starter` directory with the following variables:

```env
MODEL=gpt-4o
GATEWAY_BASE_URL=https://your-gateway-endpoint.com/v1
GATEWAY_API_KEY=your-api-key-here
```

### Environment Variables

- **`MODEL`** - The model name to use for completions
- **`GATEWAY_BASE_URL`** - The base URL endpoint for the API gateway
- **`GATEWAY_API_KEY`** - API key for authenticating with the gateway

## Usage: openai_test.py

The [openai_test.py](openai_test.py) script is a simple test to verify OpenAI API-compatible gateway connectivity.

### What It Does

- Connects to the configured AI gateway
- Sends a chat completion request asking for a thousand-word essay about the sky
- Prints the generated response to the console

### Running the Script

```bash
python openai_test.py
```

### Expected Output

The script will print a generated essay about the sky (up to 4096 tokens) to the console. A successful run indicates:
- ✅ Gateway connectivity is working
- ✅ API key is valid
- ✅ Selected model is available and responding

## Troubleshooting

### SSL Certificate Errors

If you encounter SSL certificate errors (common in Zscaler environments), run the PowerShell certificate setup script first:

```powershell
.\Cert-Solution.ps1
```

**If PowerShell execution is blocked**, you may need to bypass the execution policy:

```powershell
# Option 1: Run with bypass for this session only (recommended)
powershell -ExecutionPolicy Bypass -File .\Cert-Solution.ps1

# Option 2: Change execution policy for current user (requires restart of PowerShell)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\Cert-Solution.ps1
```

This script will:
- Export all root certificates from your local machine
- Create a certificate bundle file (`generated-cert-bundle.pem`) in your home directory
- Set the `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` environment variables

**Important for Python 3.13+:** If you're using Python 3.13 or greater, the standard `Cert-Solution.ps1` won't fully resolve certificate issues with Zscaler. This is because Zscaler doesn't mark the basic constraints of its certificate as critical, which causes validation failures in Python 3.13+.

**Solution:** The [openai_test.py](openai_test.py) script includes a custom SSL context that disables this specific check. If you encounter certificate errors even after running `Cert-Solution.ps1`, check that your script uses a similar SSL context configuration:

```python
import os
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=os.getenv("SSL_CERT_FILE", os.getenv("REQUESTS_CA_BUNDLE")))
ssl_context.verify_flags &= ~ssl.VERIFY_X509_STRICT
```

**Alternative:** You can also use the Python-based helper:
```bash
python cert.py
```

### Common Issues

1. **Authentication Error**: Verify your `GATEWAY_API_KEY` is correct in the `.env` file
2. **Connection Timeout**: Ensure you have network access to the `GATEWAY_BASE_URL`
3. **Module Not Found**: Run `pip install openai python-dotenv` to install dependencies

## Testing Other Frameworks

### LangChain Test

```bash
python chatopenai_test_llm.py
```

### Llama-Index Test

```bash
python llama_chat.py
```

### Embedding Test

```bash
python embedding.py
```

All scripts use the same `.env` configuration file.

## Additional Resources

- Review [langgraph-multitool-agent 2.ipynb](langgraph-multitool-agent%202.ipynb) for advanced agent examples
