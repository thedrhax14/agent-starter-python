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


async def fetch_instruction(instruction_id: int, metaverse_id: int = 1) -> str:
    """Fetch instruction text from the API"""
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
                    # Assuming the API returns the instruction text in a specific field
                    # Adjust this based on the actual API response structure
                    return data.get("instruction", "You are a helpful voice AI assistant.")
                else:
                    logger.error(f"Failed to fetch instruction: HTTP {response.status}")
                    return "You are a helpful voice AI assistant."
    except Exception as e:
        logger.error(f"Error fetching instruction: {e}")
        return "You are a helpful voice AI assistant."


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
    def __init__(self, instructions: str = None) -> None:
        # Use custom instructions if provided, otherwise use default
        default_instructions = """You are a helpful voice AI assistant.
            You eagerly assist users with their questions by providing information from your extensive knowledge.
            Your responses are concise, to the point, and without any complex formatting or punctuation including emojis, asterisks, or other symbols.
            You are curious, friendly, and have a sense of humor."""
        
        super().__init__(
            instructions=instructions or default_instructions,
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
    
    # Fetch custom instructions from API
    custom_instructions = await fetch_instruction(instruction_id, metaverse_id)
    
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
        agent=Assistant(instructions=custom_instructions),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # LiveKit Cloud enhanced noise cancellation
            # - If self-hosting, omit this parameter
            # - For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
