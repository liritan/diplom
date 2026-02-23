import json
from typing import Any, List
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, UploadFile, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from sqlalchemy.orm import selectinload

from app.api import deps
from app.db.session import get_db
from app.models.content import Test, Question, UserTestResult, CaseSolution
from app.models.user import User
from app.models.analysis import AnalysisTask
from app.schemas.content import (
    Test as TestSchema,
    TestCreate,
    UserTestSubmit,
    UserTestResult as UserTestResultSchema,
    CaseSolutionCreate,
    CaseSolution as CaseSolutionSchema,
    SimulationSubmit,
    SimulationReplyRequest,
)
from app.services.analysis_service import analysis_service
from app.core.yandex_service import yandex_service

router = APIRouter()

@router.get("/", response_model=List[TestSchema])
async def read_tests(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Retrieve tests.
    """
    # Use selectinload to fetch questions eagerly
    result = await db.execute(select(Test).options(selectinload(Test.questions)).offset(skip).limit(limit))
    tests = result.scalars().all()
    return tests

@router.post("/", response_model=TestSchema)
async def create_test(
    *,
    db: AsyncSession = Depends(get_db),
    test_in: TestCreate,
    current_user: User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Create new test (Admin only).
    """
    test = Test(
        title=test_in.title,
        description=test_in.description,
        type=test_in.type,
    )
    db.add(test)
    await db.commit()
    result = await db.execute(
        select(Test)
        .options(selectinload(Test.questions))
        .where(Test.id == test.id)
    )
    return result.scalars().first()

@router.post("/{test_id}/submit", response_model=dict)
async def submit_test(
    *,
    db: AsyncSession = Depends(get_db),
    test_id: int,
    result_in: UserTestSubmit,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Submit a test result and trigger AI analysis in the background.
    
    Requirements: 1.3
    """
    try:
        now_utc = datetime.now(timezone.utc)
        lookback = now_utc - timedelta(minutes=10)

        recent_results = await db.execute(
            select(UserTestResult)
            .where(
                UserTestResult.user_id == current_user.id,
                UserTestResult.test_id == test_id,
                UserTestResult.completed_at >= lookback,
            )
            .order_by(UserTestResult.completed_at.desc())
            .limit(20)
        )
        for existing in list(recent_results.scalars().all()):
            if (existing.details or {}) != (result_in.answers or {}):
                continue
            task_row = await db.execute(
                select(AnalysisTask)
                .where(
                    AnalysisTask.user_id == current_user.id,
                    AnalysisTask.response_type == "test",
                    AnalysisTask.response_id == existing.id,
                )
                .order_by(AnalysisTask.created_at.desc())
                .limit(1)
            )
            existing_task = task_row.scalars().first()
            if existing_task and str(existing_task.status).lower() in {"pending", "processing", "completed"}:
                return {
                    "result_id": existing.id,
                    "task_id": existing_task.id,
                    "status": existing_task.status,
                    "message": "Р­С‚РѕС‚ С‚РµСЃС‚ СѓР¶Рµ Р±С‹Р» РѕС‚РїСЂР°РІР»РµРЅ РЅР° Р°РЅР°Р»РёР·. Р’РѕР·РІСЂР°С‰Р°СЋ СЃСѓС‰РµСЃС‚РІСѓСЋС‰РёР№ СЂРµР·СѓР»СЊС‚Р°С‚.",
                }

        # 1. Save Raw Result
        db_result = UserTestResult(
            user_id=current_user.id,
            test_id=test_id,
            details=result_in.answers,
            score=0.0,  # Placeholder, will be calculated by AI
            ai_analysis=None  # Will be filled by background task
        )
        db.add(db_result)
        await db.commit()
        await db.refresh(db_result)
        
        # 2. Trigger background task for AI analysis
        analysis_task = await analysis_service.analyze_test_result(
            user_id=current_user.id,
            test_id=test_id,
            result_id=db_result.id,
            answers=result_in.answers,
            db=db,
            background_tasks=background_tasks
        )
        
        return {
            "result_id": db_result.id,
            "task_id": analysis_task.id,
            "status": "pending",
            "message": "РўРµСЃС‚ РѕС‚РїСЂР°РІР»РµРЅ РЅР° Р°РЅР°Р»РёР·. Р РµР·СѓР»СЊС‚Р°С‚С‹ Р±СѓРґСѓС‚ РґРѕСЃС‚СѓРїРЅС‹ С‡РµСЂРµР· РЅРµСЃРєРѕР»СЊРєРѕ СЃРµРєСѓРЅРґ."
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"РћС€РёР±РєР° РїСЂРё РѕС‚РїСЂР°РІРєРµ С‚РµСЃС‚Р°: {str(e)}")


@router.get("/me/results", response_model=List[UserTestResultSchema])
async def read_my_test_results(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(
        select(UserTestResult)
        .where(UserTestResult.user_id == current_user.id)
        .order_by(UserTestResult.completed_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.delete("/me/results")
async def delete_my_test_results(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(
        delete(UserTestResult).where(UserTestResult.user_id == current_user.id)
    )
    await db.commit()
    return {"status": "deleted", "deleted": int(result.rowcount or 0)}


@router.get("/me/case-solutions", response_model=List[CaseSolutionSchema])
async def read_my_case_solutions(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(
        select(CaseSolution)
        .where(CaseSolution.user_id == current_user.id)
        .order_by(CaseSolution.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


@router.post("/{test_id}/case/submit", response_model=dict)
async def submit_case_solution(
    *,
    db: AsyncSession = Depends(get_db),
    test_id: int,
    payload: CaseSolutionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    now_utc = datetime.now(timezone.utc)
    lookback = now_utc - timedelta(minutes=10)
    recent_solutions = await db.execute(
        select(CaseSolution)
        .where(
            CaseSolution.user_id == current_user.id,
            CaseSolution.test_id == test_id,
            CaseSolution.created_at >= lookback,
        )
        .order_by(CaseSolution.created_at.desc())
        .limit(20)
    )
    for existing in list(recent_solutions.scalars().all()):
        if (existing.solution or "").strip() != (payload.solution or "").strip():
            continue
        if existing.analysis_task_id:
            status_value = "pending"
            task_row = await db.execute(
                select(AnalysisTask).where(AnalysisTask.id == existing.analysis_task_id)
            )
            task_obj = task_row.scalars().first()
            if task_obj is not None:
                status_value = task_obj.status
            return {
                "solution_id": existing.id,
                "task_id": existing.analysis_task_id,
                "status": status_value,
            }

    solution_row = CaseSolution(
        user_id=current_user.id,
        test_id=test_id,
        solution=payload.solution,
    )
    db.add(solution_row)
    await db.commit()
    await db.refresh(solution_row)

    analysis_task = await analysis_service.analyze_case_solution(
        user_id=current_user.id,
        case_id=test_id,
        solution=payload.solution,
        solution_id=solution_row.id,
        db=db,
        background_tasks=background_tasks,
    )

    return {
        "solution_id": solution_row.id,
        "task_id": analysis_task.id,
        "status": "pending",
    }


@router.post("/simulations/{scenario}/submit", response_model=dict)
async def submit_simulation(
    *,
    db: AsyncSession = Depends(get_db),
    scenario: str,
    payload: SimulationSubmit,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    scenario_map = {
        "interview": "РЎРѕР±РµСЃРµРґРѕРІР°РЅРёРµ",
        "conflict": "РљРѕРЅС„Р»РёРєС‚ РІ РєРѕРјР°РЅРґРµ",
        "negotiation": "РџРµСЂРµРіРѕРІРѕСЂС‹",
        "time-management": "Тайм-менеджмент",
        "leadership": "Лидерство",
    }
    title = scenario_map.get(scenario)
    if not title:
        raise HTTPException(status_code=404, detail="Unknown simulation")

    result = await db.execute(
        select(Test).where(Test.type == "simulation", Test.title == title)
    )
    test = result.scalars().first()
    if not test:
        test = Test(title=title, description="", type="simulation")
        db.add(test)
        await db.commit()
        await db.refresh(test)

    now_utc = datetime.now(timezone.utc)
    lookback = now_utc - timedelta(minutes=10)
    recent_solutions = await db.execute(
        select(CaseSolution)
        .where(
            CaseSolution.user_id == current_user.id,
            CaseSolution.test_id == test.id,
            CaseSolution.created_at >= lookback,
        )
        .order_by(CaseSolution.created_at.desc())
        .limit(20)
    )
    for existing in list(recent_solutions.scalars().all()):
        if (existing.solution or "").strip() != (payload.conversation or "").strip():
            continue
        if existing.analysis_task_id:
            status_value = "pending"
            task_row = await db.execute(
                select(AnalysisTask).where(AnalysisTask.id == existing.analysis_task_id)
            )
            task_obj = task_row.scalars().first()
            if task_obj is not None:
                status_value = task_obj.status
            return {
                "test_id": test.id,
                "solution_id": existing.id,
                "task_id": existing.analysis_task_id,
                "status": status_value,
            }

    solution_row = CaseSolution(
        user_id=current_user.id,
        test_id=test.id,
        solution=payload.conversation,
    )
    db.add(solution_row)
    await db.commit()
    await db.refresh(solution_row)

    analysis_task = await analysis_service.analyze_case_solution(
        user_id=current_user.id,
        case_id=test.id,
        solution=payload.conversation,
        solution_id=solution_row.id,
        db=db,
        background_tasks=background_tasks,
    )

    return {
        "test_id": test.id,
        "solution_id": solution_row.id,
        "task_id": analysis_task.id,
        "status": "pending",
    }


@router.post("/simulations/{scenario}/reply", response_model=dict)
async def simulation_reply(
    *,
    scenario: str,
    payload: SimulationReplyRequest,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    scenario_map = {
        "interview": "РЎРѕР±РµСЃРµРґРѕРІР°РЅРёРµ",
        "conflict": "РљРѕРЅС„Р»РёРєС‚ РІ РєРѕРјР°РЅРґРµ",
        "negotiation": "РџРµСЂРµРіРѕРІРѕСЂС‹",
        "time-management": "Тайм-менеджмент",
        "leadership": "Лидерство",
    }
    title = scenario_map.get(scenario)
    if not title:
        raise HTTPException(status_code=404, detail="Unknown simulation")

    transcript_lines = []
    for m in payload.messages:
        speaker = "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ" if m.role == "user" else "РЎРѕР±РµСЃРµРґРЅРёРє"
        transcript_lines.append(f"{speaker}: {m.text}")

    transcript = "\n".join(transcript_lines)
    prompt = (
        f"РўС‹ СѓС‡Р°СЃС‚РІСѓРµС€СЊ РІ СЃРёРјСѓР»СЏС†РёРё '{title}'. "
        "РўС‹ РёРіСЂР°РµС€СЊ СЂРѕР»СЊ СЃРѕР±РµСЃРµРґРЅРёРєР° (РІС‚РѕСЂР°СЏ СЃС‚РѕСЂРѕРЅР°). "
        "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїРёС€РµС‚ С‚РѕР»СЊРєРѕ СЃРІРѕРё СЂРµРїР»РёРєРё. "
        "РўРІРѕСЏ Р·Р°РґР°С‡Р° вЂ” РѕС‚РІРµС‚РёС‚СЊ РѕРґРЅРѕР№ СЂРµРїР»РёРєРѕР№ СЃРѕР±РµСЃРµРґРЅРёРєР° РЅР° СЂСѓСЃСЃРєРѕРј (1-3 РїСЂРµРґР»РѕР¶РµРЅРёСЏ). "
        "РќРµ РѕРїРёСЃС‹РІР°Р№ РґРµР№СЃС‚РІРёСЏ, РЅРµ РґРѕР±Р°РІР»СЏР№ РїСЂРµС„РёРєСЃС‹ РІСЂРѕРґРµ 'РРЅС‚РµСЂРІСЊСЋРµСЂ:' вЂ” РІРµСЂРЅРё С‚РѕР»СЊРєРѕ С‚РµРєСЃС‚ СЂРµРїР»РёРєРё.\n\n"
        f"Р”РёР°Р»РѕРі:\n{transcript}\n\nРЎРѕР±РµСЃРµРґРЅРёРє:"
    )

    reply = await yandex_service.get_chat_response(prompt)
    return {"reply": reply}


@router.post("/simulations/{scenario}/voice", response_model=dict)
async def simulation_voice_message(
    *,
    scenario: str,
    file: UploadFile = File(...),
    messages: str = Form("[]"),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    scenario_map = {
        "interview": "РЎРѕР±РµСЃРµРґРѕРІР°РЅРёРµ",
        "conflict": "РљРѕРЅС„Р»РёРєС‚ РІ РєРѕРјР°РЅРґРµ",
        "negotiation": "РџРµСЂРµРіРѕРІРѕСЂС‹",
        "time-management": "Тайм-менеджмент",
        "leadership": "Лидерство",
    }
    title = scenario_map.get(scenario)
    if not title:
        raise HTTPException(status_code=404, detail="Unknown simulation")

    audio_content = await file.read()
    user_text = await yandex_service.speech_to_text(audio_content)
    if not user_text:
        return {
            "response": "РР·РІРёРЅРёС‚Рµ, СЏ РЅРµ СЃРјРѕРі СЂР°СЃРїРѕР·РЅР°С‚СЊ РІР°С€Рµ СЃРѕРѕР±С‰РµРЅРёРµ.",
            "user_text": "",
            "status": "failed",
        }

    try:
        history = json.loads(messages) if messages else []
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    transcript_lines = []
    for m in history:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        text = m.get("text")
        if not role or not text:
            continue
        speaker = "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ" if role == "user" else "РЎРѕР±РµСЃРµРґРЅРёРє"
        transcript_lines.append(f"{speaker}: {text}")

    transcript_lines.append(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: {user_text}")
    transcript = "\n".join(transcript_lines)

    prompt = (
        f"РўС‹ СѓС‡Р°СЃС‚РІСѓРµС€СЊ РІ СЃРёРјСѓР»СЏС†РёРё '{title}'. "
        "РўС‹ РёРіСЂР°РµС€СЊ СЂРѕР»СЊ СЃРѕР±РµСЃРµРґРЅРёРєР° (РІС‚РѕСЂР°СЏ СЃС‚РѕСЂРѕРЅР°). "
        "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїРёС€РµС‚ С‚РѕР»СЊРєРѕ СЃРІРѕРё СЂРµРїР»РёРєРё. "
        "РўРІРѕСЏ Р·Р°РґР°С‡Р° вЂ” РѕС‚РІРµС‚РёС‚СЊ РѕРґРЅРѕР№ СЂРµРїР»РёРєРѕР№ СЃРѕР±РµСЃРµРґРЅРёРєР° РЅР° СЂСѓСЃСЃРєРѕРј (1-3 РїСЂРµРґР»РѕР¶РµРЅРёСЏ). "
        "РќРµ РѕРїРёСЃС‹РІР°Р№ РґРµР№СЃС‚РІРёСЏ, РЅРµ РґРѕР±Р°РІР»СЏР№ РїСЂРµС„РёРєСЃС‹ РІСЂРѕРґРµ 'РРЅС‚РµСЂРІСЊСЋРµСЂ:' вЂ” РІРµСЂРЅРё С‚РѕР»СЊРєРѕ С‚РµРєСЃС‚ СЂРµРїР»РёРєРё.\n\n"
        f"Р”РёР°Р»РѕРі:\n{transcript}\n\nРЎРѕР±РµСЃРµРґРЅРёРє:"
    )

    reply = await yandex_service.get_chat_response(prompt)
    return {
        "response": reply,
        "user_text": user_text,
        "status": "ok",
    }


@router.post("/{test_id}/simulation/reply", response_model=dict)
async def simulation_reply_by_test(
    *,
    test_id: int,
    payload: SimulationReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    if not test or str(test.type).lower() != "simulation":
        raise HTTPException(status_code=404, detail="Simulation not found")

    transcript_lines = []
    for m in payload.messages:
        speaker = "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ" if m.role == "user" else "РЎРѕР±РµСЃРµРґРЅРёРє"
        transcript_lines.append(f"{speaker}: {m.text}")

    transcript = "\n".join(transcript_lines)
    prompt = (
        f"РўС‹ СѓС‡Р°СЃС‚РІСѓРµС€СЊ РІ СЃРёРјСѓР»СЏС†РёРё '{test.title}'. "
        "РўС‹ РёРіСЂР°РµС€СЊ СЂРѕР»СЊ СЃРѕР±РµСЃРµРґРЅРёРєР° (РІС‚РѕСЂР°СЏ СЃС‚РѕСЂРѕРЅР°). "
        "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїРёС€РµС‚ С‚РѕР»СЊРєРѕ СЃРІРѕРё СЂРµРїР»РёРєРё. "
        "РўРІРѕСЏ Р·Р°РґР°С‡Р° вЂ” РѕС‚РІРµС‚РёС‚СЊ РѕРґРЅРѕР№ СЂРµРїР»РёРєРѕР№ СЃРѕР±РµСЃРµРґРЅРёРєР° РЅР° СЂСѓСЃСЃРєРѕРј (1-3 РїСЂРµРґР»РѕР¶РµРЅРёСЏ). "
        "РќРµ РѕРїРёСЃС‹РІР°Р№ РґРµР№СЃС‚РІРёСЏ, РЅРµ РґРѕР±Р°РІР»СЏР№ РїСЂРµС„РёРєСЃС‹ РІСЂРѕРґРµ 'РРЅС‚РµСЂРІСЊСЋРµСЂ:' вЂ” РІРµСЂРЅРё С‚РѕР»СЊРєРѕ С‚РµРєСЃС‚ СЂРµРїР»РёРєРё.\n\n"
        f"Р”РёР°Р»РѕРі:\n{transcript}\n\nРЎРѕР±РµСЃРµРґРЅРёРє:"
    )

    reply = await yandex_service.get_chat_response(prompt)
    return {"reply": reply}


@router.post("/{test_id}/simulation/voice", response_model=dict)
async def simulation_voice_message_by_test(
    *,
    test_id: int,
    file: UploadFile = File(...),
    messages: str = Form("[]"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    if not test or str(test.type).lower() != "simulation":
        raise HTTPException(status_code=404, detail="Simulation not found")

    audio_content = await file.read()
    user_text = await yandex_service.speech_to_text(audio_content)
    if not user_text:
        return {
            "response": "РР·РІРёРЅРёС‚Рµ, СЏ РЅРµ СЃРјРѕРі СЂР°СЃРїРѕР·РЅР°С‚СЊ РІР°С€Рµ СЃРѕРѕР±С‰РµРЅРёРµ.",
            "user_text": "",
            "status": "failed",
        }

    try:
        history = json.loads(messages) if messages else []
        if not isinstance(history, list):
            history = []
    except Exception:
        history = []

    transcript_lines = []
    for m in history:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        text = m.get("text")
        if not role or not text:
            continue
        speaker = "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ" if role == "user" else "РЎРѕР±РµСЃРµРґРЅРёРє"
        transcript_lines.append(f"{speaker}: {text}")

    transcript_lines.append(f"РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ: {user_text}")
    transcript = "\n".join(transcript_lines)

    prompt = (
        f"РўС‹ СѓС‡Р°СЃС‚РІСѓРµС€СЊ РІ СЃРёРјСѓР»СЏС†РёРё '{test.title}'. "
        "РўС‹ РёРіСЂР°РµС€СЊ СЂРѕР»СЊ СЃРѕР±РµСЃРµРґРЅРёРєР° (РІС‚РѕСЂР°СЏ СЃС‚РѕСЂРѕРЅР°). "
        "РџРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїРёС€РµС‚ С‚РѕР»СЊРєРѕ СЃРІРѕРё СЂРµРїР»РёРєРё. "
        "РўРІРѕСЏ Р·Р°РґР°С‡Р° вЂ” РѕС‚РІРµС‚РёС‚СЊ РѕРґРЅРѕР№ СЂРµРїР»РёРєРѕР№ СЃРѕР±РµСЃРµРґРЅРёРєР° РЅР° СЂСѓСЃСЃРєРѕРј (1-3 РїСЂРµРґР»РѕР¶РµРЅРёСЏ). "
        "РќРµ РѕРїРёСЃС‹РІР°Р№ РґРµР№СЃС‚РІРёСЏ, РЅРµ РґРѕР±Р°РІР»СЏР№ РїСЂРµС„РёРєСЃС‹ РІСЂРѕРґРµ 'РРЅС‚РµСЂРІСЊСЋРµСЂ:' вЂ” РІРµСЂРЅРё С‚РѕР»СЊРєРѕ С‚РµРєСЃС‚ СЂРµРїР»РёРєРё.\n\n"
        f"Р”РёР°Р»РѕРі:\n{transcript}\n\nРЎРѕР±РµСЃРµРґРЅРёРє:"
    )

    reply = await yandex_service.get_chat_response(prompt)
    return {
        "response": reply,
        "user_text": user_text,
        "status": "ok",
    }


@router.post("/{test_id}/simulation/submit", response_model=dict)
async def submit_simulation_by_test(
    *,
    db: AsyncSession = Depends(get_db),
    test_id: int,
    payload: SimulationSubmit,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(select(Test).where(Test.id == test_id))
    test = result.scalars().first()
    if not test or str(test.type).lower() != "simulation":
        raise HTTPException(status_code=404, detail="Simulation not found")

    now_utc = datetime.now(timezone.utc)
    lookback = now_utc - timedelta(minutes=10)
    recent_solutions = await db.execute(
        select(CaseSolution)
        .where(
            CaseSolution.user_id == current_user.id,
            CaseSolution.test_id == test.id,
            CaseSolution.created_at >= lookback,
        )
        .order_by(CaseSolution.created_at.desc())
        .limit(20)
    )
    for existing in list(recent_solutions.scalars().all()):
        if (existing.solution or "").strip() != (payload.conversation or "").strip():
            continue
        if existing.analysis_task_id:
            status_value = "pending"
            task_row = await db.execute(
                select(AnalysisTask).where(AnalysisTask.id == existing.analysis_task_id)
            )
            task_obj = task_row.scalars().first()
            if task_obj is not None:
                status_value = task_obj.status
            return {
                "test_id": test.id,
                "solution_id": existing.id,
                "task_id": existing.analysis_task_id,
                "status": status_value,
            }

    solution_row = CaseSolution(
        user_id=current_user.id,
        test_id=test.id,
        solution=payload.conversation,
    )
    db.add(solution_row)
    await db.commit()
    await db.refresh(solution_row)

    analysis_task = await analysis_service.analyze_case_solution(
        user_id=current_user.id,
        case_id=test.id,
        solution=payload.conversation,
        solution_id=solution_row.id,
        db=db,
        background_tasks=background_tasks,
    )

    return {
        "test_id": test.id,
        "solution_id": solution_row.id,
        "task_id": analysis_task.id,
        "status": "pending",
    }


@router.get("/{test_id}", response_model=TestSchema)
async def read_test(
    test_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> Any:
    result = await db.execute(
        select(Test).options(selectinload(Test.questions)).where(Test.id == test_id)
    )
    test = result.scalars().first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")
    return test


