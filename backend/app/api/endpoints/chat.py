from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.responses import Response
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.api import deps
from app.db.session import get_db
from app.models.chat import ChatMessage, ChatAudio
from app.models.user import User
from app.core.yandex_service import yandex_service
from app.services.analysis_service import analysis_service
from pydantic import BaseModel

router = APIRouter()

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    task_id: str
    status: str

@router.post("/send", response_model=ChatResponse)
async def chat_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a text message to the AI Trainer.
    Now triggers AI analysis in the background.
    
    Requirements: 1.1
    """
    try:
        # Get immediate AI response for user
        ai_response = await yandex_service.get_chat_response(request.message)
        
        # Trigger background analysis (saves ChatMessage and creates AnalysisTask)
        analysis_task = await analysis_service.analyze_chat_message(
            user_id=current_user.id,
            message=request.message,
            db=db,
            background_tasks=background_tasks
        )

        # Save AI response to chat history
        db.add(ChatMessage(
            user_id=current_user.id,
            message=ai_response,
            is_user=False,
            analysis_task_id=analysis_task.id
        ))
        await db.commit()
        
        return {
            "response": ai_response,
            "task_id": analysis_task.id,
            "status": "pending"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке сообщения: {str(e)}")

@router.post("/voice", response_model=dict)
async def voice_message(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Send a voice message (audio file) to the AI Trainer.
    Returns text response and triggers AI analysis in the background.
    
    Requirements: 1.2
    """
    try:
        audio_content = await file.read()

        user_voice_msg = ChatMessage(
            user_id=current_user.id,
            message="(voice)",
            is_user=True,
        )
        db.add(user_voice_msg)
        await db.flush()
        await db.refresh(user_voice_msg)

        db.add(
            ChatAudio(
                chat_message_id=user_voice_msg.id,
                content_type=file.content_type or "audio/webm",
                data=audio_content,
            )
        )
        
        # 1. Speech to Text
        user_text = await yandex_service.speech_to_text(audio_content)
        
        if not user_text:
            await db.commit()
            return {
                "response": "Извините, я не смог распознать ваше сообщение.",
                "user_text": "",
                "task_id": None,
                "status": "failed"
            }
        
        # 2. AI Processing
        ai_response = await yandex_service.get_chat_response(user_text)
        
        # 3. Trigger background analysis (saves ChatMessage and creates AnalysisTask)
        analysis_task = await analysis_service.analyze_chat_message(
            user_id=current_user.id,
            message=user_text,
            db=db,
            background_tasks=background_tasks
        )

        user_voice_msg.analysis_task_id = analysis_task.id

        # Save AI response to chat history
        db.add(ChatMessage(
            user_id=current_user.id,
            message=ai_response,
            is_user=False,
            analysis_task_id=analysis_task.id
        ))
        await db.commit()
        
        # 4. Text to Speech (Optional - could return audio url)
        # For this MVP, we return text response, frontend can request TTS if needed
        
        return {
            "response": ai_response, 
            "user_text": user_text,
            "task_id": analysis_task.id,
            "status": "pending"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обработке голосового сообщения: {str(e)}")

@router.get("/me/messages", response_model=list[dict])
async def get_my_chat_messages(
    limit: int = 100,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    messages = result.scalars().all()

    if not messages:
        return []

    audio_rows = await db.execute(
        select(ChatAudio).where(ChatAudio.chat_message_id.in_([m.id for m in messages]))
    )
    audios = {a.chat_message_id: a for a in audio_rows.scalars().all()}

    return [
        {
            "id": m.id,
            "message": m.message,
            "is_user": m.is_user,
            "created_at": m.created_at,
            "analysis_task_id": m.analysis_task_id,
            "audio_url": f"/chat/audio/{m.id}" if m.id in audios else None,
        }
        for m in messages
    ]


@router.get("/audio/{message_id}")
async def get_chat_audio(
    message_id: int,
    current_user: User = Depends(deps.get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    msg_row = await db.execute(
        select(ChatMessage).where(ChatMessage.id == message_id, ChatMessage.user_id == current_user.id)
    )
    msg = msg_row.scalar_one_or_none()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    audio_row = await db.execute(select(ChatAudio).where(ChatAudio.chat_message_id == message_id))
    audio = audio_row.scalar_one_or_none()
    if not audio:
        raise HTTPException(status_code=404, detail="Audio not found")

    return Response(content=audio.data, media_type=audio.content_type)
