# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup
- `uv sync` - Install dependencies to virtual environment
- `uv sync --dev` - Install dependencies including dev tools (pytest, ruff)
- Copy `.env.example` to `.env` and configure API keys
- `lk app env -w .env` - Auto-load LiveKit environment using CLI

### Running the Agent
- `uv run python src/agent.py download-files` - Download required models (Silero VAD, LiveKit turn detector) before first run
- `uv run python src/agent.py console` - Run agent in terminal for direct interaction
- `uv run python src/agent.py dev` - Run agent for frontend/telephony integration
- `uv run python src/agent.py start` - Production mode

### Code Quality
- `uv run ruff check .` - Run linter
- `uv run ruff format .` - Format code
- `uv run ruff check --output-format=github .` - Lint with GitHub Actions format
- `uv run ruff format --check --diff .` - Check formatting without applying changes

### Testing
- `uv run pytest` - Run full test suite including evaluations
- `uv run pytest tests/test_agent.py::test_offers_assistance` - Run specific test

## Architecture

### Core Components
- `src/agent.py` - Main agent implementation with `Assistant` class inheriting from `Agent`
- `Assistant` class contains agent instructions and function tools (e.g., `lookup_weather`)
- `entrypoint()` function sets up the voice AI pipeline with STT/LLM/TTS components

### Voice AI Pipeline
The agent uses a modular pipeline approach:
- **STT**: Deepgram Nova-3 model with multilingual support
- **LLM**: OpenAI GPT-4o-mini (easily swappable)
- **TTS**: Cartesia for voice synthesis
- **Turn Detection**: LiveKit's multilingual turn detection model
- **VAD**: Silero VAD for voice activity detection
- **Noise Cancellation**: LiveKit Cloud BVC (can be omitted for self-hosting)

### Testing Framework
Uses LiveKit Agents testing framework with evaluation-based tests:
- Tests use `AgentSession` with real LLM interactions
- `.judge()` method evaluates agent responses against intent descriptions
- Mock tools available for testing error conditions
- Supports both unit tests and end-to-end evaluations

### Configuration
- Environment variables loaded via `python-dotenv`
- Required API keys: LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, OPENAI_API_KEY, DEEPGRAM_API_KEY, CARTESIA_API_KEY
- Alternative providers can be swapped by modifying the session setup in `entrypoint()`

### Function Tools
Functions decorated with `@function_tool` are automatically passed to the LLM:
- Must be async methods on the Agent class
- Include docstrings with tool descriptions and argument specifications
- Example: `lookup_weather()` for weather information retrieval

### Metrics and Logging
- Integrated usage collection and metrics logging
- Metrics collected via `MetricsCollectedEvent` handlers
- Usage summaries logged on session shutdown
- Room context automatically included in log entries

## Key Patterns

### Agent Customization
To modify agent behavior:
1. Update `instructions` in `Assistant.__init__()`
2. Add new `@function_tool` methods for custom capabilities
3. Swap STT/LLM/TTS providers in the `AgentSession` setup

### Testing New Features
1. Add unit tests to `tests/test_agent.py`
2. Use `.judge()` evaluations for response quality
3. Mock external dependencies with `mock_tools()`
4. Test both success and error conditions

### Deployment
- Production-ready with included `Dockerfile`
- Uses `uv` for dependency management
- CI/CD workflows for linting (`ruff.yml`) and testing (`tests.yml`)

## LiveKit Documentation & Examples

The LiveKit documentation is comprehensive and provides detailed guidance for all aspects of agent development. **All documentation URLs support `.md` suffix for markdown format** and the docs follow the **llms.txt standard** for AI-friendly consumption.

**Core Documentation**: https://docs.livekit.io/agents/
- **Quick Start**: https://docs.livekit.io/agents/start/voice-ai/
- **Building Agents**: https://docs.livekit.io/agents/build/
- **Integrations**: https://docs.livekit.io/agents/integrations/
- **Operations & Deployment**: https://docs.livekit.io/agents/ops/

**Practical Examples Repository**: https://github.com/livekit-examples/python-agents-examples
- Contains dozens of real-world agent implementations
- Advanced patterns and use cases beyond the starter template
- Integration examples with various AI providers and tools
- Production-ready code samples

## Extending Agent Functionality

### Swapping AI Providers

#### LLM Providers ([docs](https://docs.livekit.io/agents/integrations/llm/))
Available providers with consistent interface:
- **OpenAI**: `openai.LLM(model="gpt-4o-mini")` ([docs](https://docs.livekit.io/agents/integrations/llm/openai/))
- **Anthropic**: `anthropic.LLM(model="claude-3-haiku")` ([docs](https://docs.livekit.io/agents/integrations/llm/anthropic/))
- **Google Gemini**: `google.LLM(model="gemini-1.5-flash")` ([docs](https://docs.livekit.io/agents/integrations/llm/google/))
- **Azure OpenAI**: `azure_openai.LLM(model="gpt-4o")` ([docs](https://docs.livekit.io/agents/integrations/llm/azure-openai/))
- **Groq**: ([docs](https://docs.livekit.io/agents/integrations/llm/groq/))
- **Fireworks**: ([docs](https://docs.livekit.io/agents/integrations/llm/fireworks/))
- **DeepSeek, Cerebras, Amazon Bedrock**, and others

#### STT Providers ([docs](https://docs.livekit.io/agents/integrations/stt/))
All support low-latency multilingual transcription:
- **Deepgram**: `deepgram.STT(model="nova-3", language="multi")` ([docs](https://docs.livekit.io/agents/integrations/stt/deepgram/))
- **AssemblyAI**: `assemblyai.STT()` ([docs](https://docs.livekit.io/agents/integrations/stt/assemblyai/))
- **Azure AI Speech**: `azure_ai_speech.STT()` ([docs](https://docs.livekit.io/agents/integrations/stt/azure-ai-speech/))
- **Google Cloud**: `google.STT()` ([docs](https://docs.livekit.io/agents/integrations/stt/google/))
- **OpenAI**: `openai.STT()` ([docs](https://docs.livekit.io/agents/integrations/stt/openai/))

#### TTS Providers ([docs](https://docs.livekit.io/agents/integrations/tts/))
High-quality, low-latency voice synthesis:
- **Cartesia**: `cartesia.TTS(model="sonic-english")` ([docs](https://docs.livekit.io/agents/integrations/tts/cartesia/))
- **ElevenLabs**: `elevenlabs.TTS()` ([docs](https://docs.livekit.io/agents/integrations/tts/elevenlabs/))
- **Azure AI Speech**: `azure_ai_speech.TTS()` ([docs](https://docs.livekit.io/agents/integrations/tts/azure-ai-speech/))
- **Amazon Polly**: `polly.TTS()` ([docs](https://docs.livekit.io/agents/integrations/tts/polly/))
- **Google Cloud**: `google.TTS()` ([docs](https://docs.livekit.io/agents/integrations/tts/google/))

### Alternative Pipeline Configurations

#### OpenAI Realtime API ([docs](https://docs.livekit.io/agents/integrations/realtime/openai))
Replace entire STT-LLM-TTS pipeline with single provider:
```python
session = AgentSession(
    llm=openai.realtime.RealtimeModel(
        model="gpt-4o-realtime-preview",
        voice="alloy",
        temperature=0.8,
    )
)
```
- Built-in VAD with server or semantic modes
- Lower latency than traditional pipeline
- Supports audio and text processing

#### Custom Turn Detection
**LiveKit Turn Detector** ([docs](https://docs.livekit.io/agents/build/turns/turn-detector/)):
- **English Model**: `EnglishModel()` (66MB, ~15-45ms per turn)
- **Multilingual Model**: `MultilingualModel()` (281MB, ~50-160ms, 14 languages)
- Adds conversational context to VAD for better end-of-turn detection

### Function Tools and Capabilities

#### Adding Custom Tools
Functions decorated with `@function_tool` become available to the LLM:
```python
@function_tool
async def get_stock_price(self, context: RunContext, symbol: str):
    """Get current stock price for a symbol.
    
    Args:
        symbol: Stock ticker symbol (e.g., AAPL, GOOGL)
    """
    # Implementation here
    return f"Stock price for {symbol}: $150.00"
```

#### Tool Integration Patterns
- Use `logger.info()` for debugging tool calls
- Return simple strings or structured data
- Handle errors gracefully with try/catch
- Tools run asynchronously and can access external APIs

### Testing and Evaluation ([docs](https://docs.livekit.io/agents/build/testing/))

#### Writing Agent Tests
Use LiveKit's evaluation framework with LLM-based judgment:
```python
@pytest.mark.asyncio
async def test_custom_feature():
    async with AgentSession(llm=openai.LLM()) as session:
        await session.start(Assistant())
        result = await session.run(user_input="Test query")
        
        await result.expect.next_event().is_message(role="assistant").judge(
            llm, intent="Expected behavior description"
        )
```

#### Mock Tools for Testing
Test error conditions and edge cases:
```python
with mock_tools(Assistant, {"tool_name": lambda: "mocked_response"}):
    result = await session.run(user_input="test")
```

#### Test Categories to Implement
- **Expected Behavior**: Core functionality works correctly
- **Tool Usage**: Function calls with proper arguments
- **Error Handling**: Graceful failure responses
- **Factual Grounding**: Accurate information, admits unknowns
- **Misuse Resistance**: Refuses inappropriate requests

### Metrics and Monitoring ([docs](https://docs.livekit.io/agents/build/metrics/))

#### Built-in Metrics Collection
Automatic tracking of:
- **STT Metrics**: Audio duration, transcript time, streaming mode
- **LLM Metrics**: Completion duration, token usage, TTFT
- **TTS Metrics**: Audio duration, character count, generation time

#### Custom Metrics Implementation
```python
@session.on("metrics_collected")
def _on_metrics_collected(ev: MetricsCollectedEvent):
    metrics.log_metrics(ev.metrics)
    # Add custom metric processing
    custom_usage_tracker.track(ev.metrics)
```

#### Usage Tracking
```python
usage_collector = metrics.UsageCollector()
# Collect throughout session
summary = usage_collector.get_summary()  # Get final usage stats
```

### Frontend Integration ([docs](https://docs.livekit.io/agents/start/frontend/))

#### Starter App Templates
Ready-to-use starter apps with full source code:
- **Web (React/Next.js)**: https://github.com/livekit-examples/agent-starter-react
- **iOS/macOS (Swift)**: https://github.com/livekit-examples/agent-starter-swift  
- **Android (Kotlin)**: https://github.com/livekit-examples/agent-starter-android
- **Flutter**: https://github.com/livekit-examples/agent-starter-flutter
- **React Native**: https://github.com/livekit-examples/voice-assistant-react-native
- **Web Embed Widget**: https://github.com/livekit-examples/agent-starter-embed

#### Custom Frontend Development
- Use LiveKit SDKs (JavaScript, Swift, Android, Flutter, React Native)
- Subscribe to audio/video tracks and transcription streams
- Implement WebRTC for realtime connectivity
- Add features like audio visualizers, virtual avatars, RPC calls

### Telephony Integration ([docs](https://docs.livekit.io/agents/start/telephony/))
Add inbound or outbound calling capabilities to your agent with SIP integration.

### Production Considerations

#### Environment Configuration
Required environment variables:
- `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`
- Provider-specific keys: `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`

#### Deployment Options ([docs](https://docs.livekit.io/agents/ops/deployment/))
- **LiveKit Cloud**: Managed hosting with enhanced features
- **Self-hosting**: Use provided `Dockerfile` 
- **Telephony**: SIP integration for phone calls
- **Scaling**: Handle multiple concurrent sessions

#### Key Files to Track in Production
- Commit `uv.lock` for reproducible builds
- Commit `livekit.toml` if using LiveKit Cloud
- Remove template-specific CI checks