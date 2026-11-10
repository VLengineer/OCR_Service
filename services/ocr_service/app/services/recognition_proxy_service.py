"""
Сервис-прокси для распознавания документов через n8n webhook.
Принимает RecognitionRequest, определяет тип документа внутри,
отправляет на распознавание и возвращает распознанный текст.
"""

import logging
from uuid import uuid4

from app.schemas.schemas import Document, RecognitionRequest
from app.services.document_converter import DocumentConverter
from app.services.request_service import RequestService

logger = logging.getLogger(__name__)


class RecognitionProxyService:
    """Сервис для проксирования запросов распознавания документов."""

    def __init__(
        self,
        request_service: RequestService,
        document_converter: DocumentConverter,
    ) -> None:
        """
        Инициализация сервиса проксирования распознавания.

        Args:
            request_service: Сервис HTTP-запросов к n8n
            document_converter: Конвертер документов для определения типа
        """
        self._request_service = request_service
        self._document_converter = document_converter

    async def recognize(self, request: RecognitionRequest) -> str:
        """
        Распознаёт документ и возвращает распознанный текст.

        Тип документа определяется автоматически из base64.

        Args:
            request: Запрос с документом в base64

        Returns:
            str: Распознанный текст из документа

        Raises:
            ValueError: При некорректном ответе от webhook
            Exception: При ошибке HTTP-запроса
        """
        try:
            # Определяем тип документа из base64
            document_type_str = self._document_converter.detect_document_type(
                request.document_base64
            )

            # Формируем Document для отправки в webhook
            document = Document(
                document_id=str(uuid4()),
                document_base64=request.document_base64,
                document_type=document_type_str,
            )

            logger.info(
                f"Запрос распознавания документа: "
                f"document_id={document.document_id}, "
                f"document_type={document_type_str}"
            )

            response_data = await self._request_service.recognize_document(document)

            # Извлекаем текст из ответа
            extracted_text = response_data.get("raw_text", "")
            if not extracted_text:
                raise ValueError("Ответ не содержит raw_text")

            logger.info(
                f"Распознавание документа завершено: "
                f"document_id={document.document_id}, "
                f"text_length={len(extracted_text)}"
            )

            return extracted_text

        except ValueError as e:
            logger.error(
                f"Некорректный формат ответа распознавания: error={e}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Ошибка распознавания документа: error={e}"
            )
            raise
