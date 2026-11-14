from collections.abc import Callable, Iterable
from importlib import resources
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from support_agent.agent import SupportAgent
from support_agent.db import make_engine, make_session_factory
from support_agent.knowledge import HashingEmbedder, KnowledgeIndex, policy_chunks
from support_agent.llm import ModelResponse, ScriptedModel, ToolCall
from support_agent.service import SupportService
from support_agent.store import MockStore

POLICIES = Path(str(resources.files("support_agent.demo").joinpath("policies")))


def call(name: str, **arguments: str) -> ModelResponse:
    return ModelResponse(
        "", tool_calls=(ToolCall(id=f"id-{name}", name=name, arguments=arguments),)
    )


def answer(text: str) -> ModelResponse:
    return ModelResponse(text)


@pytest.fixture(scope="session")
def knowledge() -> KnowledgeIndex:
    index = KnowledgeIndex(HashingEmbedder())
    index.add(policy_chunks(POLICIES))
    return index


@pytest.fixture
def sessions() -> sessionmaker[Session]:
    return make_session_factory(make_engine("sqlite://"))


ServiceFactory = Callable[[Iterable[ModelResponse]], tuple[SupportService, ScriptedModel]]


@pytest.fixture
def make_service(knowledge: KnowledgeIndex, sessions: sessionmaker[Session]) -> ServiceFactory:
    def factory(responses: Iterable[ModelResponse]) -> tuple[SupportService, ScriptedModel]:
        model = ScriptedModel(responses)
        agent = SupportAgent(model, MockStore(), knowledge, min_score=0.2)
        return SupportService(agent, sessions), model

    return factory
