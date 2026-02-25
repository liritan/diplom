from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)  # True if from user, False if from AI
    analysis_task_id = Column(String, ForeignKey("analysis_tasks.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", backref="chat_messages")
    analysis_task = relationship("AnalysisTask", backref="chat_messages")


class ChatAudio(Base):
    __tablename__ = "chat_audios"

    id = Column(Integer, primary_key=True, index=True)
    chat_message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, unique=True)
    content_type = Column(String, nullable=False, default="audio/webm")
    data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat_message = relationship("ChatMessage", backref="audio")
