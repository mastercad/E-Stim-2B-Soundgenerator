"""
Session management for E-Stim 2B.

A Session is a complete stimulation program consisting of
ordered PatternSegments with transitions between them.
Sessions can be saved/loaded as JSON files.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

from .patterns import PatternSegment, TransitionType


@dataclass
class Session:
    """
    A complete E-Stim session consisting of multiple segments.

    The session defines a timeline of patterns that are played
    sequentially with configurable transitions between them.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Neue Session"
    description: str = ""
    author: str = ""
    created: str = field(default_factory=lambda: datetime.now().isoformat())
    modified: str = field(default_factory=lambda: datetime.now().isoformat())

    # Session settings
    sample_rate: int = 44100
    master_volume: float = 0.8  # Master volume [0.0, 1.0]
    loop: bool = False          # Loop the entire session

    # Segments
    segments: List[PatternSegment] = field(default_factory=list)

    @property
    def total_duration(self) -> float:
        """Total session duration in seconds."""
        return sum(seg.duration for seg in self.segments)

    @property
    def total_duration_formatted(self) -> str:
        """Total duration formatted as HH:MM:SS or MM:SS."""
        total = self.total_duration
        hours = int(total // 3600)
        minutes = int((total % 3600) // 60)
        seconds = int(total % 60)
        if hours > 0:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def add_segment(self, segment: PatternSegment, index: int = -1):
        """Add a segment to the session."""
        if index < 0:
            self.segments.append(segment)
        else:
            self.segments.insert(index, segment)
        self.modified = datetime.now().isoformat()

    def remove_segment(self, segment_id: str):
        """Remove a segment by ID."""
        self.segments = [s for s in self.segments if s.id != segment_id]
        self.modified = datetime.now().isoformat()

    def move_segment(self, segment_id: str, new_index: int):
        """Move a segment to a new position."""
        segment = next((s for s in self.segments if s.id == segment_id), None)
        if segment:
            self.segments.remove(segment)
            self.segments.insert(min(new_index, len(self.segments)), segment)
            self.modified = datetime.now().isoformat()

    def duplicate_segment(self, segment_id: str) -> Optional[PatternSegment]:
        """Duplicate a segment and insert it after the original."""
        for i, seg in enumerate(self.segments):
            if seg.id == segment_id:
                new_seg = PatternSegment.from_dict(seg.to_dict())
                new_seg.id = str(uuid.uuid4())[:8]
                new_seg.name = f"{seg.name} (Kopie)"
                self.segments.insert(i + 1, new_seg)
                self.modified = datetime.now().isoformat()
                return new_seg
        return None

    def get_segment_at_time(self, time_seconds: float) -> Optional[PatternSegment]:
        """Get the segment playing at a specific time position."""
        elapsed = 0.0
        for segment in self.segments:
            if elapsed + segment.duration > time_seconds:
                return segment
            elapsed += segment.duration
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "created": self.created,
            "modified": self.modified,
            "sample_rate": self.sample_rate,
            "master_volume": self.master_volume,
            "loop": self.loop,
            "segments": [seg.to_dict() for seg in self.segments],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Deserialize session from dictionary."""
        session = cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Session"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            created=data.get("created", datetime.now().isoformat()),
            modified=data.get("modified", datetime.now().isoformat()),
            sample_rate=data.get("sample_rate", 44100),
            master_volume=data.get("master_volume", 0.8),
            loop=data.get("loop", False),
        )
        for seg_data in data.get("segments", []):
            session.segments.append(PatternSegment.from_dict(seg_data))
        return session

    def save(self, filepath: str):
        """Save session to a JSON file."""
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls, filepath: str) -> "Session":
        """Load session from a JSON file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


class SessionLibrary:
    """Manages a collection of saved sessions."""

    def __init__(self, sessions_dir: str = "sessions"):
        self.sessions_dir = sessions_dir
        os.makedirs(sessions_dir, exist_ok=True)

    def list_sessions(self) -> List[Dict[str, str]]:
        """List all saved sessions with basic info."""
        sessions = []
        for filename in sorted(os.listdir(self.sessions_dir)):
            if filename.endswith(".json"):
                filepath = os.path.join(self.sessions_dir, filename)
                try:
                    session = Session.load(filepath)
                    sessions.append({
                        "filename": filename,
                        "filepath": filepath,
                        "name": session.name,
                        "description": session.description,
                        "duration": session.total_duration_formatted,
                        "segments": len(session.segments),
                        "modified": session.modified,
                    })
                except (json.JSONDecodeError, KeyError):
                    continue
        return sessions

    def save_session(self, session: Session, filename: str = None) -> str:
        """Save a session. Returns the filepath."""
        if filename is None:
            filename = f"{session.name.replace(' ', '_').lower()}_{session.id}.json"
        filepath = os.path.join(self.sessions_dir, filename)
        session.save(filepath)
        return filepath

    def load_session(self, filename: str) -> Session:
        """Load a session by filename."""
        filepath = os.path.join(self.sessions_dir, filename)
        return Session.load(filepath)

    def delete_session(self, filename: str):
        """Delete a session file."""
        filepath = os.path.join(self.sessions_dir, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
