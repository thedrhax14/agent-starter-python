import logging
import json
import aiohttp

from dotenv import load_dotenv
from livekit.agents import (
    NOT_GIVEN,
    Agent,
    AgentFalseInterruptionEvent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.plugins import noise_cancellation, openai, silero
from livekit.plugins.turn_detector.english import EnglishModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


async def fetch_room_metadata(room_name: str) -> dict:
    """Fetch room metadata from the API"""
    url = f"https://api.builder.holofair.io/api/livekit/rooms/metadata"
    params = {"roomName": room_name}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Fetched metadata for room {room_name}: {data}")
                    return data
                else:
                    logger.error(f"Failed to fetch metadata for room {room_name}: HTTP {response.status}")
                    return {}
    except Exception as e:
        logger.error(f"Error fetching metadata for room {room_name}: {e}")
        return {}


async def fetch_instruction(instruction_id: int, metaverse_id: int = 1) -> tuple[str, list]:
    """
    Fetch instruction text and MCP servers from the API
    Returns (instruction_text, mcp_servers_config)
    """
    url = f"https://api.builder.holofair.io/api/agents/instruction"
    params = {
        "instruction_id": instruction_id,
        "metaverse_id": metaverse_id
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract instruction text
                    instruction_text = data.get("instruction", "You are a helpful voice AI assistant.")
                    
                    # Extract MCP servers configuration
                    mcp_servers_config = data.get("mcp_servers", [])
                    logger.info(f"Fetched instruction and {len(mcp_servers_config)} MCP servers for instruction_id: {instruction_id}")
                    
                    return instruction_text, mcp_servers_config
                else:
                    logger.error(f"Failed to fetch instruction: HTTP {response.status}")
                    return "You are a helpful voice AI assistant.", []
    except Exception as e:
        logger.error(f"Error fetching instruction: {e}")
        return "You are a helpful voice AI assistant.", []


def create_mcp_servers(mcp_servers_config: list) -> list:
    """
    Create MCP server instances from configuration
    Expected config format: [{"name": "server1", "transport": "websocket", "url": "wss://..."}]
    """
    mcp_servers = []
    
    for config in mcp_servers_config:
        try:
            name = config.get("name")
            transport = config.get("transport", "websocket")
            url = config.get("url")
            
            if not name or not url:
                logger.warning(f"Invalid MCP server config: {config}")
                continue
            
            # Create MCP server configuration
            # Note: The exact implementation depends on the LiveKit Agents MCP API
            # This is a placeholder structure that should be adapted to the actual API
            mcp_server_config = {
                "name": name,
                "transport": transport,
                "url": url,
            }
            
            # Add additional config fields if present
            if "headers" in config:
                mcp_server_config["headers"] = config["headers"]
            if "env" in config:
                mcp_server_config["env"] = config["env"]
            
            mcp_servers.append(mcp_server_config)
            logger.info(f"Added MCP server: {name} ({transport}): {url}")
            
        except Exception as e:
            logger.error(f"Error creating MCP server from config {config}: {e}")
            continue
    
    return mcp_servers


def should_join_room(metadata: dict) -> tuple[bool, int, int]:
    """
    Check if the agent should join the room based on metadata.
    Returns (should_join, instruction_id, metaverse_id)
    """
    try:
        instruction_id = metadata.get("instruction_id")
        metaverse_id = metadata.get("metaverse_id", 1)  # Default to 1 if not specified
        
        # Check if instruction_id exists and is greater than 0
        if instruction_id is not None:
            instruction_id = int(instruction_id)
            if instruction_id > 0:
                return True, instruction_id, int(metaverse_id)
        
        return False, 0, 1
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing metadata: {e}")
        return False, 0, 1


class Assistant(Agent):
    def __init__(self, instructions: str = None, mcp_servers: list = None) -> None:
        # Use custom instructions if provided, otherwise use default
        default_instructions = """You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor."""
        
        super().__init__(
            instructions=instructions or default_instructions,
            mcp_servers=mcp_servers,
        )

    # all functions annotated with @function_tool will be passed to the LLM when this
    # agent is active
    @function_tool
    async def lookup_weather(self, context: RunContext, location: str):
        """Use this tool to look up current weather information in the given location.

        If the location is not supported by the weather service, the tool will indicate this. You must tell the user the location's weather is unavailable.

        Args:
            location: The location to look up weather information for (e.g. city name)
        """

        logger.info(f"Looking up weather for {location}")

        return "sunny with a temperature of 70 degrees."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Fetch room metadata from API using room name
    room_name = ctx.room.name
    logger.info(f"Fetching metadata for room: {room_name}")
    
    metadata = await fetch_room_metadata(room_name)
    
    # Check if agent should join this room
    should_join, instruction_id, metaverse_id = should_join_room(metadata)
    
    if not should_join:
        logger.info(f"Skipping room {room_name} - no valid instruction_id in metadata")
        return
    
    logger.info(f"Joining room {room_name} with instruction_id: {instruction_id}, metaverse_id: {metaverse_id}")
    
    # Fetch custom instructions and MCP servers from API
    custom_instructions, mcp_servers_config = await fetch_instruction(instruction_id, metaverse_id)
    
    # Create MCP server instances
    mcp_servers = create_mcp_servers(mcp_servers_config)
    
    logger.info(f"Using {len(mcp_servers)} MCP servers for this session")
    
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # To use a realtime model instead of a voice pipeline, use the following session setup instead:
    session = AgentSession(
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=EnglishModel(),
        vad=silero.VAD.load(),
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
        # See all providers at https://docs.livekit.io/agents/integrations/realtime/
        llm=openai.realtime.RealtimeModel(voice="marin")
    )

    # sometimes background noise could interrupt the agent session, these are considered false positive interruptions
    # when it's detected, you may resume the agent's speech
    @session.on("agent_false_interruption")
    def _on_agent_false_interruption(ev: AgentFalseInterruptionEvent):
        logger.info("false positive interruption, resuming")
        session.generate_reply(instructions=ev.extra_instructions or NOT_GIVEN)

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/integrations/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/integrations/avatar/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(instructions=custom_instructions, mcp_servers=mcp_servers),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.generate_reply(
        instructions="Greet the user and introduce yourself in English only. Then proceed with the goal of the primary instruction.",
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
