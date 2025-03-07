# src/main.py
"""
Entry point for the Agentic Development Workflow application.
"""
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.workflows.dev_workflow import create_development_workflow
from src.models.schema import WorkflowState

# Load environment variables
load_dotenv()

def main():
    """
    Initialize and run the development workflow.
    """
    # Configure the language model
    llm = ChatOpenAI(
        model="gpt-4", 
        temperature=0.2,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Create the workflow
    workflow = create_development_workflow(llm)
    
    # Initialize state
    initial_state = WorkflowState(
        current_step="collect_requirements",
    )
    
    # Execute the workflow (interactive mode)
    for event in workflow.stream(initial_state.dict()):
        # Process and display the intermediate states
        if "current_step" in event and event.get("current_step"):
            current_step = event.get("current_step")
            print(f"Current step: {current_step}")


if __name__ == "__main__":
    main()


# src/workflows/dev_workflow.py
"""
Main development workflow definition.
"""
from typing import Dict, Any
from langgraph.graph import StateGraph
from langchain_core.language_models import BaseChatModel
from src.models.schema import WorkflowState
from src.nodes import (
    requirements, user_stories, design, 
    code, testing, deployment
)

def create_development_workflow(llm: BaseChatModel) -> StateGraph:
    """
    Create the development workflow graph.
    
    Args:
        llm: Language model to use for the workflow
        
    Returns:
        A StateGraph representing the full development workflow
    """
    # Create a new graph
    workflow = StateGraph(WorkflowState)
    
    # Register all nodes with the graph
    # Requirements phase
    workflow.add_node("collect_requirements", requirements.collect_requirements)
    workflow.add_node("generate_user_stories", user_stories.generate_user_stories)
    workflow.add_node("product_owner_review", user_stories.product_owner_review)
    workflow.add_node("revise_user_stories", user_stories.revise_user_stories)
    
    # Design phase
    workflow.add_node("create_design_documents", design.create_design_documents)
    workflow.add_node("design_review", design.design_review)
    workflow.add_node("revise_design_documents", design.revise_design_documents)
    
    # Implementation phase
    workflow.add_node("generate_code", code.generate_code)
    workflow.add_node("code_review", code.code_review)
    workflow.add_node("fix_code_after_review", code.fix_code_after_review)
    workflow.add_node("security_review", code.security_review)
    workflow.add_node("fix_code_after_security", code.fix_code_after_security)
    
    # Testing phase
    workflow.add_node("write_test_cases", testing.write_test_cases)
    workflow.add_node("test_cases_review", testing.test_cases_review)
    workflow.add_node("fix_test_cases", testing.fix_test_cases)
    workflow.add_node("qa_testing", testing.qa_testing)
    workflow.add_node("fix_code_after_qa", code.fix_code_after_qa)
    
    # Deployment phase
    workflow.add_node("deployment", deployment.deployment)
    workflow.add_node("monitoring", deployment.monitoring)
    workflow.add_node("maintenance", deployment.maintenance)
    
    # Define edges (transitions between nodes)
    # Requirements flow
    workflow.add_edge("collect_requirements", "generate_user_stories")
    workflow.add_edge("generate_user_stories", "product_owner_review")
    
    # Product owner review decision
    workflow.add_conditional_edges(
        "product_owner_review",
        lambda state: "create_design_documents" if state["feedback"].get("product_owner", {}).get("approved", False) else "revise_user_stories"
    )
    workflow.add_edge("revise_user_stories", "product_owner_review")
    
    # Design flow
    workflow.add_edge("create_design_documents", "design_review")
    
    # Design review decision
    workflow.add_conditional_edges(
        "design_review",
        lambda state: "generate_code" if state["feedback"].get("design_review", {}).get("approved", False) else "revise_design_documents"
    )
    workflow.add_edge("revise_design_documents", "design_review")
    
    # Implementation flow
    workflow.add_edge("generate_code", "code_review")
    
    # Code review decision
    workflow.add_conditional_edges(
        "code_review",
        lambda state: "security_review" if state["feedback"].get("code_review", {}).get("approved", False) else "fix_code_after_review"
    )
    workflow.add_edge("fix_code_after_review", "code_review")
    
    # Security review decision
    workflow.add_conditional_edges(
        "security_review",
        lambda state: "write_test_cases" if state["feedback"].get("security_review", {}).get("approved", False) else "fix_code_after_security"
    )
    workflow.add_edge("fix_code_after_security", "security_review")
    
    # Testing flow
    workflow.add_edge("write_test_cases", "test_cases_review")
    
    # Test case review decision
    workflow.add_conditional_edges(
        "test_cases_review",
        lambda state: "qa_testing" if state["feedback"].get("test_cases_review", {}).get("approved", False) else "fix_test_cases"
    )
    workflow.add_edge("fix_test_cases", "test_cases_review")
    
    # QA testing decision
    workflow.add_conditional_edges(
        "qa_testing",
        lambda state: "deployment" if state["qa_results"].get("passed", False) else "fix_code_after_qa"
    )
    workflow.add_edge("fix_code_after_qa", "qa_testing")
    
    # Deployment and maintenance flow
    workflow.add_edge("deployment", "monitoring")
    workflow.add_edge("monitoring", "maintenance")
    
    # Feedback loops from maintenance back to requirements
    workflow.add_edge("maintenance", "collect_requirements")
    
    # Set the entry point
    workflow.set_entry_point("collect_requirements")
    
    return workflow


# src/models/schema.py
"""
Schema definitions for the workflow state.
"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime

class WorkflowState(BaseModel):
    """State for the development workflow agent."""
    user_inputs: Dict[str, Any] = Field(default_factory=dict, 
                                       description="User requirements and inputs")
    user_stories: List[Dict] = Field(default_factory=list, 
                                   description="Generated user stories")
    design_documents: Dict = Field(default_factory=dict, 
                                 description="Design documents")
    code: Dict = Field(default_factory=dict, 
                     description="Generated code")
    test_cases: List[Dict] = Field(default_factory=list, 
                                 description="Test cases")
    qa_results: Dict = Field(default_factory=dict, 
                           description="QA testing results")
    maintenance_notes: List[str] = Field(default_factory=list, 
                                       description="Maintenance and update notes")
    current_step: str = Field(default="collect_requirements", 
                            description="Current step in the workflow")
    history: List[Dict] = Field(default_factory=list, 
                              description="Conversation history")
    feedback: Dict = Field(default_factory=dict, 
                         description="Feedback for various stages")
    
    class Config:
        arbitrary_types_allowed = True


# src/nodes/requirements.py
"""
Nodes for the requirements gathering phase.
"""
from typing import Dict, Any
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from config.prompts.requirements import REQUIREMENTS_SYSTEM_PROMPT

def add_to_history(state: Dict, actor: str, message: str) -> Dict:
    """Add a message to the conversation history."""
    state["history"].append({
        "actor": actor,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })
    return state

def collect_requirements(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Collect user requirements and inputs.
    
    Args:
        state: Current workflow state
        
    Returns:
        Updated workflow state
    """
    # Implementation for collecting requirements
    # This would interact with the LLM to gather requirements
    
    # Example implementation:
    # 1. Use a prompt template
    # 2. Invoke the LLM
    # 3. Parse the response
    # 4. Update the state
    
    # Return the updated state
    state["user_inputs"]["requirements_document"] = "Sample requirements document"
    state = add_to_history(state, "ai", "Requirements collected")
    state["current_step"] = "generate_user_stories"
    
    return state
