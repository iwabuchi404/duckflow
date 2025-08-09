class MockLLM:
    """
    Simple mock LLM for E2E tests.
    Returns predefined responses based on the input prompt.
    """

    @staticmethod
    def generate(prompt: str) -> str:
        # Simple deterministic responses for testing
        if "hallucination" in prompt.lower():
            # Simulate a hallucination by returning unrelated text
            return "This is a hallucinated response unrelated to the prompt."
        if "context" in prompt.lower():
            # Return a response that includes the context keyword
            return "I remember the previous context: user asked about file reading."
        if "prompt quality" in prompt.lower():
            # Return a well‑formed answer
            return "The prompt is clear and the answer is correct."
        # Default fallback
        return "Default response."