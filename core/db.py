from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, BigInteger, String, Text, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
from core.config import settings

sync_engine = create_engine(settings.sync_database_url)
Session = sessionmaker(bind=sync_engine)

async_engine = create_async_engine(settings.async_database_url)
AsyncSessionLocal = sessionmaker(bind=async_engine, class_=AsyncSession)

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"
    id = Column(BigInteger, primary_key=True)
    filename = Column(Text, nullable=False)
    sha256 = Column(Text, nullable=False, unique=True)
    status = Column(Text, nullable=False, default="queued")
    topic_tags = Column(ARRAY(Text))
    ingested_at = Column(DateTime(timezone=True), server_default=func.now())
    
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")

class Chunk(Base):
    __tablename__ = "chunks"
    id = Column(BigInteger, primary_key=True)
    doc_id = Column(BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page = Column(Integer)
    heading = Column(Text)
    topic = Column(Text)
    text = Column(Text, nullable=False)
    embedding = Column(Vector(settings.EMBED_DIM))
    
    document = relationship("Document", back_populates="chunks")


class QuestionModel(Base):
    __tablename__ = "questions"
    id = Column(BigInteger, primary_key=True)
    chunk_id = Column(BigInteger, ForeignKey("chunks.id", ondelete="CASCADE"))
    type = Column(Text)         # 'mcq' | 'short'
    stem = Column(Text, nullable=False)
    options = Column(JSONB)     # JSON dict: {"A": "...", "B": "..."}
    answer = Column(Text, nullable=False)
    difficulty = Column(Text)   # 'easy' | 'medium' | 'hard'
    topic = Column(Text)


from sqlalchemy import Column, Integer, BigInteger, String, Text, ForeignKey, DateTime, Boolean

class AttemptModel(Base):
    __tablename__ = "attempts"
    id = Column(BigInteger, primary_key=True)
    question_id = Column(BigInteger, ForeignKey("questions.id"))
    topic = Column(Text)
    correct = Column(Boolean)    # True | False
    seconds_taken = Column(Integer)
    days_since_last_seen = Column(Integer)
    ts = Column(DateTime(timezone=True), server_default=func.now())

