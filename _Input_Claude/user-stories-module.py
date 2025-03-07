# src/nodes/user_stories.py
"""
Nodes for the user story generation and review phase.
"""
from typing import Dict, Any, List
from datetime import datetime
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.language_models import BaseChatModel

# Import prompt templates
from config.prompts.user_stories import (
    USER_STORIES_SYSTEM_PROMPT, 
    PRODUCT_OWNER_REVIEW_PROMPT
)

# Models for this node
class UserStory(BaseModel):
    """Model representing a user story."""
    id: str = Field(description="Unique identifier for the user story (US-XXX)")
    user_type: str = Field(description="Type of user")
    action: str = Field(description="What the user wants to do")
    benefit: str = Field(description="The benefit or value to the user")
    acceptance_criteria: List[str] = Field(description="List of acceptance criteria")
    priority: str = Field(description="Priority (High, Medium, Low)")

class UserStoriesOutput(BaseModel):
    """Model for the output of user story generation."""
    user_stories: List[UserStory] = Field(description="List of user stories")

class ReviewResult(BaseModel):
    """Model for product owner review results."""
    approved: bool = Field(description="Whether the stories are approved overall")
    feedback: Dict[str, str] = Field(description="Feedback for each story by ID")
    revision_needed: List[str] = Field(description="IDs of stories that need revision")

def add_to_history(state: Dict, actor: str, message: str) -> Dict:
    """Add a message to the conversation history."""
    state["history"].append({
        "actor": actor,
        "message": message,
        "timestamp": datetime.now().isoformat()
    })
    return state

def generate_user_stories(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate user stories based on requirements.
    
    Args:
        state: Current workflow state with requirements document
        
    Returns:
        Updated workflow state with generated user stories
    """
    # Get the requirements document from the state
    requirements = state["user_inputs"].get("requirements_document", "")
    
    # Construct the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", USER_STORIES_SYSTEM_PROMPT),
        ("human", f"Generate user stories based on these requirements: {requirements}")
    ])
    
    # Create the parser
    parser = JsonOutputParser(pydantic_object=UserStoriesOutput)
    
    # Get the LLM from the state
    llm = state.get("llm")
    
    # Create and execute the chain
    chain = prompt | llm | parser
    
    # Invoke the chain
    result = chain.invoke({})
    
    # Update the state
    state["user_stories"] = [story.dict() for story in result.user_stories]
    state = add_to_history(
        state, 
        "ai", 
        f"Generated {len(result.user_stories)} user stories"
    )
    state["current_step"] = "product_owner_review"
    
    return state

def product_owner_review(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate a product owner review of user stories.
    
    Args:
        state: Current workflow state with user stories
        
    Returns:
        Updated workflow state with review feedback
    """
    # Get the user stories from the state
    user_stories = state["user_stories"]
    
    # Construct the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", PRODUCT_OWNER_REVIEW_PROMPT),
        ("human", f"Review these user stories: {user_stories}")
    ])
    
    # Create the parser
    parser = JsonOutputParser(pydantic_object=ReviewResult)
    
    # Get the LLM from the state
    llm = state.get("llm")
    
    # Create and execute the chain
    chain = prompt | llm | parser
    
    # Invoke the chain
    result = chain.invoke({})
    
    # Update the state
    state["feedback"]["product_owner"] = result.dict()
    state = add_to_history(
        state, 
        "ai", 
        f"Product owner review: {'Approved' if result.approved else 'Needs revision'}"
    )
    
    # Determine next step based on approval
    if result.approved:
        state["current_step"] = "create_design_documents"
    else:
        state["current_step"] = "revise_user_stories"
    
    return state

def revise_user_stories(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Revise user stories based on product owner feedback.
    
    Args:
        state: Current workflow state with user stories and feedback
        
    Returns:
        Updated workflow state with revised user stories
    """
    # Get the user stories and feedback from the state
    user_stories = state["user_stories"]
    feedback = state["feedback"]["product_owner"]
    
    # Construct the prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a product analyst revising user stories based on feedback.
        Update each story to address the specific feedback provided.
        Ensure all stories are clear, complete, and align with project goals."""),
        ("human", f"Revise these user stories: {user_stories}\n\nBased on this feedback: {feedback}")
    ])
    
    # Create the parser for the revised user stories
    parser = JsonOutputParser(pydantic_object=UserStoriesOutput)
    
    # Get the LLM from the state
    llm = state.get("llm")
    
    # Create and execute the chain
    chain = prompt | llm | parser
    
    # Invoke the chain
    result = chain.invoke({})
    
    # Update the state with the revised user stories
    state["user_stories"] = [story.dict() for story in result.user_stories]
    state = add_to_history(state, "ai", "User stories revised based on feedback")
    state["current_step"] = "product_owner_review"
    
    return state
