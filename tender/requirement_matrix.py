"""
Requirement Matrix data structures and persistence helpers.
"""
from typing import Dict, Any, List
from database import save_tender_requirements, list_tender_requirements, update_requirement_status

class RequirementMatrix:
    """Manages the tender checklist linking requirements to source documents and pages."""

    @classmethod
    def save_matrix(cls, project_id: int, requirements: List[Dict[str, Any]]):
        """Persists the extracted requirements list to SQLite."""
        save_tender_requirements(project_id, requirements)

    @classmethod
    def get_matrix(cls, project_id: int) -> List[Dict[str, Any]]:
        """Retrieves requirements for a tender project."""
        return list_tender_requirements(project_id)

    @classmethod
    def update_status(cls, req_id: int, status: str):
        """Updates requirement fulfillment status."""
        update_requirement_status(req_id, status)
