"""
Скрипт для загрузки документов из ELMA365 и создания задач на обработку.

Запуск:
    python load_elma_documents.py

Или через cron:
    */5 * * * * cd /path/to/ocr_service && python load_elma_documents.py
"""
import asyncio
import logging
import sys

from app.core.config import settings
from app.repositories.database import init_db, close_db, async_session
from app.repositories.task_repository import TaskRepository
from app.services.elma_service import ElmaService
from app.schemas.schemas import State, CallType

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def load_elma_documents() -> int:
    """
    Загружает документы из ELMA365 и создает задачи на обработку.

    Returns:
        int: Количество созданных задач
    """
    await init_db()

    try:
        elma_service = ElmaService()
        documents = await elma_service.get_documents_list()
        logger.info(f"Найдено {len(documents)} документов в ELMA365")

        created_count = 0

        async with async_session() as session:
            task_repository = TaskRepository(session)

            for document in documents:
                if not document.url:
                    logger.warning(f"Документ {document.__id} не имеет URL, пропускаем")
                    continue

                try:
                    # Создаем задачу (base64 не нужен, воркер скачает сам по url)
                    task = await task_repository.add_task(
                        document_id=document.__id or "unknown",
                        base64_document=None,
                        document_type=document.__register_name,
                        state=State.WAITING,
                        call_type=CallType.FILL_RAG,
                        metadata={
                            "url": document.url,
                            "__id": document.__id,
                            "__name": document.__name,
                            "subject": document.subject,
                            "description": document.description,
                            "__createdAt": document.__createdAt,
                            "counterparty": document.counterparty,
                            "decisionMaker": document.decisionMaker,
                            "__register_name": document.__register_name,
                            "registrationDate": document.registrationDate,
                        },
                    )
                    logger.info(f"Создана задача {task.id} для документа {document.__id}")
                    created_count += 1

                except Exception as e:
                    logger.error(f"Ошибка обработки документа {document.__id}: {e}")
                    continue

            await session.commit()

        logger.info(f"Всего создано задач: {created_count}")
        return created_count

    finally:
        await close_db()


if __name__ == "__main__":
    try:
        count = asyncio.run(load_elma_documents())
        sys.exit(0 if count >= 0 else 1)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)
