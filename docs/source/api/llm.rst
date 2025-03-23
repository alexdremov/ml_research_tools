LLM API
=======

The LLM API provides utilities for interacting with Large Language Models (LLMs) such as OpenAI's GPT models.

LLM Client
----------

.. py:class:: ml_research_tools.core.llm_tools.LLMClient

   A client for interacting with large language models that provides unified interface, 
   retry handling, and streaming capabilities.

   .. py:method:: __init__(api_key=None, base_url=None, model="gpt-3.5-turbo", max_tokens=1000, temperature=0.7, top_p=1.0, retry_attempts=3, retry_delay=5, logger=None)

      Initialize the LLM client with API configuration.

      :param api_key: API key for authentication
      :type api_key: str, optional
      :param base_url: Base URL for the API
      :type base_url: str
      :param model: Model identifier
      :type model: str
      :param max_tokens: Maximum tokens to generate
      :type max_tokens: int
      :param temperature: Sampling temperature (0.0 to 2.0)
      :type temperature: float
      :param top_p: Top-p sampling parameter
      :type top_p: float
      :param retry_attempts: Number of retry attempts for failed requests
      :type retry_attempts: int
      :param retry_delay: Base delay between retries (in seconds)
      :type retry_delay: int
      :param logger: Logger instance
      :type logger: logging.Logger, optional

   .. py:method:: complete(messages, stream=False)

      Generate a completion for the given prompt messages.

      :param messages: List of message dictionaries with "role" and "content"
      :type messages: list
      :param stream: Whether to stream the response
      :type stream: bool
      :return: Complete response or generator for streaming
      :rtype: str or generator

   .. py:method:: chat(system_prompt=None, max_turns=10)

      Start an interactive chat session with the LLM.

      :param system_prompt: System message to set context
      :type system_prompt: str, optional
      :param max_turns: Maximum conversation turns
      :type max_turns: int
      :return: Exit code
      :rtype: int

Factory Function
---------------

.. py:function:: ml_research_tools.core.llm_tools.create_llm_client(config)

   Create an LLM client from a configuration object.

   :param config: Configuration object
   :type config: ml_research_tools.core.config.Config
   :return: Configured LLM client
   :rtype: LLMClient

Example
-------

Here's an example of how to use the LLM API:

.. code-block:: python

   from ml_research_tools.core.llm_tools import create_llm_client
   from ml_research_tools.core.config import Config
   
   # Create config with LLM settings
   config = Config(llm={
       "api_key": "your-api-key",
       "model": "gpt-4",
       "temperature": 0.5
   })
   
   # Create the client
   llm_client = create_llm_client(config)
   
   # Generate a completion
   messages = [
       {"role": "user", "content": "Explain the advantages of caching in ML pipelines"}
   ]
   response = llm_client.complete(messages)
   print(response)
   
   # Or use streaming for real-time responses
   for chunk in llm_client.complete(messages, stream=True):
       print(chunk, end="", flush=True) 