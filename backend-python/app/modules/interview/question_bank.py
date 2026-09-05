from dataclasses import dataclass
from uuid import UUID, uuid4

from app.modules.interview.context import InterviewContext
from app.modules.interview.domain import (
    InterviewQuestion,
    InterviewQuestionCitation,
    InterviewSession,
    utc_now,
)
from app.modules.knowledge.context import ContextCitation


@dataclass(frozen=True, slots=True)
class QuestionBankEntry:
    keywords: tuple[str, ...]
    content: str
    category: str
    expected_points: tuple[str, ...]


QUESTION_BANK = (
    QuestionBankEntry(
        ("fastapi",),
        "请说明 FastAPI 中异步接口的适用场景，以及如何避免阻塞事件循环。",
        "FASTAPI",
        ("区分 I/O 密集与 CPU 密集任务", "避免在 async 接口中执行阻塞调用"),
    ),
    QuestionBankEntry(
        ("redis",),
        "Redis 常见的数据结构分别适合哪些业务场景？请结合一个实际例子说明。",
        "REDIS",
        ("理解常用数据结构", "能够结合具体业务选择数据结构"),
    ),
    QuestionBankEntry(
        ("postgresql", "postgres"),
        "遇到 PostgreSQL 慢查询时，你会按照什么顺序进行定位和优化？",
        "DATABASE",
        ("能够使用执行计划定位问题", "理解索引、SQL 与数据分布的影响"),
    ),
    QuestionBankEntry(
        ("langgraph",),
        "在使用 LangGraph 编排 AI 工作流时，如何划分节点状态并保证失败后可恢复？",
        "AI_WORKFLOW",
        ("区分编排状态与持久化业务状态", "考虑幂等、重试与失败恢复"),
    ),
    QuestionBankEntry(
        ("rag", "retrieval augmented"),
        "请介绍一个 RAG 系统从检索到生成的完整链路，以及你会如何评估效果。",
        "RAG",
        ("理解检索、上下文组装与生成链路", "能够说明召回与回答质量指标"),
    ),
    QuestionBankEntry(
        ("docker",),
        "如何设计一个适合生产环境的 Docker 镜像，并控制镜像体积和运行权限？",
        "DEVOPS",
        ("理解多阶段构建", "遵循最小权限和可重复构建原则"),
    ),
)

FALLBACK_QUESTIONS = (
    QuestionBankEntry(
        (),
        "请选取简历中最有代表性的一个项目，说明你的职责、关键决策和最终结果。",
        "PROJECT",
        ("能够明确个人职责", "能够解释技术决策并量化结果"),
    ),
    QuestionBankEntry(
        (),
        "请描述一次你定位并解决复杂技术问题的经历，你如何验证问题已经解决？",
        "PROBLEM_SOLVING",
        ("问题定位过程清晰", "包含验证方法和结果"),
    ),
)


def select_question_buffer(
    session: InterviewSession,
    context: InterviewContext,
    *,
    count: int = 2,
) -> list[InterviewQuestion]:
    """Select a deterministic, resume-grounded initial question buffer."""

    normalized_context = context.prompt.casefold()
    matched = [
        entry
        for entry in QUESTION_BANK
        if any(keyword in normalized_context for keyword in entry.keywords)
    ]
    entries = (matched + list(FALLBACK_QUESTIONS))[:count]
    citation = context.citations[0]
    questions: list[InterviewQuestion] = []
    for sequence, entry in enumerate(entries, start=1):
        question_id = uuid4()
        questions.append(
            InterviewQuestion(
                id=question_id,
                session_id=session.id,
                sequence=sequence,
                content=entry.content,
                category=entry.category,
                difficulty=session.difficulty,
                expected_points=list(entry.expected_points),
                source_summary=f"{citation.document_name} p.{citation.page_number or 'unknown'}",
                created_at=utc_now(),
                citations=[_citation_for_question(question_id, citation)],
            )
        )
    return questions


def _citation_for_question(
    question_id: UUID, citation: ContextCitation
) -> InterviewQuestionCitation:
    return InterviewQuestionCitation(
        id=uuid4(),
        question_id=question_id,
        chunk_id=citation.chunk_id,
        document_id=citation.document_id,
        source_id=citation.source_id,
        page_number=citation.page_number,
        score=citation.score,
        excerpt=citation.excerpt,
        ordinal=0,
        created_at=utc_now(),
        document_name=citation.document_name,
    )
