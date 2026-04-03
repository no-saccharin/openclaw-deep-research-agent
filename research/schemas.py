"""所有 Pydantic 数据模型定义"""
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

Platform = Literal["instagram", "linkedin", "youtube", "x", "web"]


class URLBuckets(BaseModel):
    instagram: List[str] = Field(default_factory=list)
    linkedin: List[str] = Field(default_factory=list)
    youtube: List[str] = Field(default_factory=list)
    x: List[str] = Field(default_factory=list)
    web: List[str] = Field(default_factory=list)


class SpecialistOutput(BaseModel):
    platform: Platform
    url: str
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ResearchFlowState(BaseModel):
    query: str = ""
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    final_response: Optional[str] = None


class ResearchRequest(BaseModel):
    """API 请求模型"""
    query: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    requester_type: Optional[str] = None
    requester_user_id: Optional[int] = None
    requester_chat_id: Optional[int] = None
    requester_username: Optional[str] = None


class ResearchResponse(BaseModel):
    """API 响应模型"""
    success: bool
    result: str
    sources_count: int = 0
    error: Optional[str] = None


class ResearchHistoryItem(BaseModel):
    id: int
    query: str
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    requester_type: Optional[str] = None
    requester_user_id: Optional[int] = None
    requester_chat_id: Optional[int] = None
    requester_username: Optional[str] = None
    success: bool
    result: str
    sources_count: int = 0
    error: Optional[str] = None
    duration_ms: int = 0
    created_at: str


class ResearchHistoryResponse(BaseModel):
    items: List[ResearchHistoryItem]
    total: int