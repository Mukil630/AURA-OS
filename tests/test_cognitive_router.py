import pytest
from brain.cognitive_router import CognitiveRouter, CognitiveRoute


def test_fast_conversation_greetings():
    router = CognitiveRouter()
    res = router.route("Hi maapla eppadi irukka?")
    assert res.track == "FAST_CONVERSATION"
    assert res.requires_pc is False


def test_fast_conversation_tech_doubt():
    router = CognitiveRouter()
    res = router.route("Java-la HashSet vs TreeSet difference enna?")
    assert res.track == "FAST_CONVERSATION"
    assert res.requires_pc is False


def test_status_query():
    router = CognitiveRouter()
    res = router.route("Andha task enna aachu mapla?")
    assert res.track == "STATUS_OR_MEMORY_QUERY"


def test_device_presentation():
    router = CognitiveRouter()
    res = router.route("Open panni kaatu mapla screen-la")
    assert res.track == "DEVICE_PRESENTATION"
    assert res.requires_pc is True
    assert res.target_swarm_agent == "PCPilot"


def test_heavy_scraping_task():
    router = CognitiveRouter()
    res = router.route("Karur spinning mills 5 scrape panni Excel podu")
    assert res.track == "AUTONOMOUS_HEAVY_TASK"
    assert res.target_swarm_agent == "WebScout"
